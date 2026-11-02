"""The win-probability line builder of stats/wp.py on the synthetic WP league of test_wp_run: the
frozen model must reproduce the report before any line is written, a game's line runs from its
pre-game probability to its result, and the exclusions (a forfeit, a score that does not match the
play-by-play, a live game without a logged pre-game probability) leave a game out."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval import wp_backtest as wb
from eurohoops.parse.wp_pbp import ParsedGame
from eurohoops.stats import wp as export
from tests.test_wp_run import _game_file, _league
from tests.test_wp_stats import MODEL

pytestmark = pytest.mark.slow

LIVE = wb.LAST_SEASON + 1


@pytest.fixture(scope="module")
def league(tmp_path_factory: pytest.TempPathFactory) -> tuple[pd.DataFrame, Path, dict]:
    raw = tmp_path_factory.mktemp("wp_lines")
    games = _league(raw)
    report, _ = wb.run(games, raw)
    return games, raw, report


def _row(game_id: str, home: int, away: int, *, forfeit: bool = False) -> dict:
    return {
        "game_id": game_id,
        "season": LIVE,
        "phase": "RS",
        "tipoff_utc": pd.Timestamp(f"{LIVE}-10-01", tz="UTC"),
        "home": "H",
        "away": "A",
        "home_score": home,
        "away_score": away,
        "played": True,
        "forfeit": forfeit,
        "neutral": False,
    }


def test_fit_frozen_reproduces_the_report_and_refuses_another(
    league: tuple[pd.DataFrame, Path, dict],
) -> None:
    games, raw, report = league
    model, table = export.fit_frozen(games, raw, report)
    historic = games.loc[games["season"] <= wb.LAST_SEASON, "game_id"]
    assert set(historic) <= set(table["game_id"])
    p = model.predict(
        np.zeros(3), np.array([0.0, 1200.0, 2400.0]), np.zeros(3), np.zeros(3), np.zeros(3)
    )
    assert ((p >= 0.0) & (p <= 1.0)).all()
    wrong = json.loads(json.dumps(report))
    wrong["families"][wrong["chosen"]["family"]]["calibrated"]["logloss"] += 0.01
    with pytest.raises(RuntimeError, match="does not reproduce the report"):
        export.fit_frozen(games, raw, wrong)


def test_a_line_runs_from_the_pre_game_probability_to_the_result(
    league: tuple[pd.DataFrame, Path, dict],
) -> None:
    games, raw, report = league
    lines = export.wp_lines(games, raw, report, {})
    historic = games.loc[games["season"] <= wb.LAST_SEASON]
    assert set(lines.games) == set(historic["game_id"])
    assert lines.family == report["chosen"]["family"]
    assert lines.version == str(report["version"])
    for row in historic.head(3).itertuples():
        line = lines.games[row.game_id]
        first, last = line["line"][0], line["line"][-1]
        assert first[:3] == [0, 0, 0] and first[3] == line["pre"]
        assert last[1:3] == [row.home_score, row.away_score]
        assert last[3] == (export.BP if row.home_score > row.away_score else 0)
        assert all(0 <= point[3] <= export.BP for point in line["line"])


def test_wp_lines_keeps_the_live_games_that_pass_the_exclusions(
    league: tuple[pd.DataFrame, Path, dict],
) -> None:
    games, raw, report = league
    rng = np.random.default_rng(3)
    one = _game_file(raw, LIVE, 1, rng)  # passes: the row carries the file's score
    two = _game_file(raw, LIVE, 2, rng)  # the row's score is off by one point
    three = _game_file(raw, LIVE, 3, rng)  # passes, but the row is a forfeit
    _game_file(raw, LIVE, 4, rng)  # passes, but no pre-game probability is logged for it
    live = pd.DataFrame(
        [
            _row("E2026_1", one[0], one[1]),
            _row("E2026_2", two[0] + 1, two[1]),
            _row("E2026_3", three[0], three[1], forfeit=True),
            _row("E2026_4", 0, 0),
        ]
    )
    pre = {"E2026_1": 0.6, "E2026_2": 0.7, "E2026_3": 0.4}
    lines = export.wp_lines(pd.concat([games, live], ignore_index=True), raw, report, pre)
    assert lines.games["E2026_1"]["pre"] == 6000
    assert lines.games["E2026_1"]["line"][-1][1:3] == [one[0], one[1]]
    assert "E2026_2" not in lines.games  # its result does not match the play-by-play
    assert "E2026_3" not in lines.games  # a forfeit
    assert "E2026_4" not in lines.games  # no logged pre-game probability


def test_a_game_with_no_plays_has_no_line() -> None:
    assert export.game_line(ParsedGame(True, (), False, 0, 0, 0), 0.5, False, MODEL, True) is None


def test_line_for_needs_the_worker_model_and_skips_an_unusable_game(
    league: tuple[pd.DataFrame, Path, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    games, raw, _ = league
    row = SimpleNamespace(**{**games.iloc[0].to_dict(), "forfeit": True})
    item = (raw, row, 0.5)
    monkeypatch.setattr(export, "_MODEL", None)
    with pytest.raises(RuntimeError, match="needs _set_model first"):
        export._line_for(item)
    monkeypatch.setattr(export, "_MODEL", MODEL)
    assert export._line_for(item) == (str(row.game_id), None)
