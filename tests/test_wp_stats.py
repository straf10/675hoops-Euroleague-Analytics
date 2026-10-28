"""The game-page win-probability export (stats/wp.py): line shape, chain start and result, swings,
control parts and the season file. A synthetic game and a small fitted model stand in for the
cache, so the tests need no play-by-play."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.models import wp as wpm
from eurohoops.models.wp import Calibrated
from eurohoops.parse.wp_pbp import ParsedGame, PlayRow
from eurohoops.stats import wp as export


def _model() -> Calibrated:
    rng = np.random.default_rng(7)
    n = 4000
    m = rng.normal(0.0, 9.0, n)
    t = rng.uniform(0.0, 2400.0, n)
    ot = np.zeros(n)
    logit_pre = rng.normal(0.0, 0.4, n)
    neutral = np.zeros(n)
    y = (m + rng.normal(0.0, 6.0, n) > 0).astype(float)
    state = (m, t, ot, logit_pre, neutral)
    fam = wpm.fit_family("logit", None, state, y)
    iso = wpm.fit_isotonic(fam.predict_raw(*state), y)
    return Calibrated(fam, iso)


MODEL = _model()

# (elapsed seconds, play code, home points, away points)
PLAYS = [
    (40, "D", 0, 0),
    (95, "2FGM", 2, 0),
    (130, "FTM", 0, 1),
    (300, "3FGM", 0, 3),
    (620, "2FGM", 2, 0),
    (900, "2FGM", 0, 2),
    (1210, "3FGM", 3, 0),
    (1500, "FTM", 1, 0),
    (2000, "LAYUPMD", 0, 2),
    (2395, "3FGM", 3, 0),
]


def _regulation_game(plays: list[tuple[int, str, int, int]]) -> tuple[ParsedGame, bool]:
    """A regulation game from plays; the score is carried forward and a final marker ends it."""
    rows: list[PlayRow] = []
    home = away = 0
    for elapsed, code, dh, da in plays:
        home += dh
        away += da
        period = min(elapsed // 600 + 1, 4)
        clock = 600.0 - (elapsed - (period - 1) * 600)
        t = (4 - period) * 600.0 + clock
        rows.append(PlayRow(period, 0, clock, float(elapsed), t, code, home, away))
    rows.append(PlayRow(4, 0, 0.0, 2400.0, 0.0, "EG", home, away))
    return ParsedGame(True, tuple(rows), False, 0, home, away), home > away


def _line(pre: float = 0.62, plays: list[tuple[int, str, int, int]] | None = None) -> dict:
    parsed, home_won = _regulation_game(PLAYS if plays is None else plays)
    line = export.game_line(parsed, pre, False, MODEL, home_won)
    assert line is not None
    return line


def test_the_chain_starts_at_the_published_pre_game_probability() -> None:
    line = _line(pre=0.62)
    assert line["pre"] == 6200
    assert line["line"][0] == [0, 0, 0, 6200]


def test_the_line_ends_at_the_result_and_the_final_score() -> None:
    parsed, won = _regulation_game(PLAYS)
    line = export.game_line(parsed, 0.5, False, MODEL, won)
    assert line is not None
    assert line["line"][-1] == [2400, parsed.final_home, parsed.final_away, 10000]

    away_wins = [(elapsed, code, da, dh) for elapsed, code, dh, da in PLAYS]
    parsed, won = _regulation_game(away_wins)
    line = export.game_line(parsed, 0.5, False, MODEL, won)
    assert line is not None
    assert line["line"][-1][1:] == [parsed.final_home, parsed.final_away, 0]
    assert line["line"][-1][3] == 0


def test_every_scoring_change_is_kept_and_the_grid_is_thirty_seconds() -> None:
    points = _line()["line"]
    times = [p[0] for p in points]
    assert times == sorted(times)
    for elapsed, _code, dh, da in PLAYS:
        if dh or da:
            assert any(p[0] == elapsed for p in points), elapsed
    # A play every 20 s: each 30 s mark reads the last play at or before it, so every window of
    # 30 s holds a point.
    plays = [(s, "D", 0, 0) for s in range(20, 2400, 20)]
    plays[40] = (820, "2FGM", 2, 0)
    grid_points = _line(plays=plays)["line"]
    for grid in range(30, 2400, 30):
        assert any(grid - 30 < p[0] <= grid for p in grid_points), grid


def test_the_line_stays_inside_the_display_clip_until_the_result() -> None:
    for _elapsed, _home, _away, wp in _line()["line"][1:-1]:
        assert 10 <= wp <= 9990


def test_swings_are_the_largest_scoring_changes_read_at_the_same_clock() -> None:
    swings = _line()["swings"]
    assert len(swings) == 5
    magnitudes = [abs(s[7]) for s in swings]
    assert magnitudes == sorted(magnitudes, reverse=True)
    scoring_times = {elapsed for elapsed, _c, dh, da in PLAYS if dh or da}
    for elapsed, period, clock, home_scored, code, _home, _away, delta in swings:
        assert elapsed in scoring_times
        assert code in ("2FGM", "3FGM", "FTM", "LAYUPMD")
        assert period == min(elapsed // 600 + 1, 4)
        assert clock == round(600 - (elapsed - (period - 1) * 600))
        assert home_scored in (0, 1)
        assert delta != 0
        gain = delta if home_scored == 1 else -delta
        assert gain > 0, "a scoring team's win chance rises in this model"


def test_control_parts_are_one_view_per_team() -> None:
    control = _line()["control"]
    assert set(control) == {"home", "away"}
    assert all(len(v) == 5 for v in control.values())
    assert control["home"][0] == pytest.approx(-control["away"][0], abs=1e-4)
    assert control["home"][2] == pytest.approx(control["away"][2], abs=1e-4)  # drama is shared
    assert 0.0 <= control["home"][1] <= 1.0
    assert 0.0 <= control["away"][3] <= 1.0


def test_overtime_adds_five_minutes_per_period_on_the_game_time_axis() -> None:
    rows = [
        PlayRow(4, 0, 5.0, 2395.0, 5.0, "3FGM", 0, 3),  # regulation, 5 s left
        PlayRow(5, 1, 280.0, 2420.0, 280.0, "2FGM", 2, 3),  # OT1 at 4:40
        PlayRow(5, 1, 100.0, 2600.0, 100.0, "FTM", 2, 4),  # OT1 at 1:40
        PlayRow(6, 1, 290.0, 2710.0, 290.0, "2FGM", 4, 4),  # OT2 at 4:50
        PlayRow(6, 1, 0.0, 3000.0, 0.0, "EG", 4, 4),
    ]
    parsed = ParsedGame(True, tuple(rows), True, 0, 4, 4)
    line = export.game_line(parsed, 0.5, False, MODEL, False)
    assert line is not None
    assert line["ot"] == 2
    assert line["line"][-1] == [3000, 4, 4, 0]
    assert any(p[0] == 2420 for p in line["line"])
    assert all(s[1] >= 5 for s in line["swings"] if s[0] >= 2400)


def test_the_season_file_keeps_the_played_games_and_its_shape() -> None:
    lines = export.WpLines(
        version="0.2.0+wp.test",
        family="logit",
        games={"E2025_1": _line(), "E2025_2": _line()},
    )
    payload = export.wp_payload(2025, ["E2025_1", "E2025_9"], lines)
    assert list(payload["games"]) == ["E2025_1"]
    assert payload["model"] == "logit"
    assert payload["point_fields"] == ["elapsed", "home", "away", "wp"]
    body = json.dumps(payload["games"]["E2025_1"], separators=(",", ":"))
    assert len(body) < 8000, len(body)  # about 2.7 KB a game on the cache


def test_logged_pre_takes_the_elo_row_in_force_at_tip_off(tmp_path: Path) -> None:
    path = tmp_path / "log.csv"
    frame = pd.DataFrame(
        [
            ["E2026_1", "elo", "2026-09-01T16:00:00Z", "2026-09-01T10:00:00Z", 0.55],
            ["E2026_1", "elo", "2026-09-01T16:00:00Z", "2026-09-01T15:00:00Z", 0.60],
            ["E2026_1", "elo", "2026-09-01T16:00:00Z", "2026-09-01T17:00:00Z", 0.99],
            ["E2026_1", "m1", "2026-09-01T16:00:00Z", "2026-09-01T12:00:00Z", 0.10],
            ["E2026_2", "elo", "2026-09-02T16:00:00Z", "2026-09-02T12:00:00Z", 0.41],
        ],
        columns=["game_id", "model", "tipoff_utc", "predicted_at_utc", "p_home"],
    )
    frame.to_csv(path, index=False)
    assert export.logged_pre(path) == {"E2026_1": 0.60, "E2026_2": 0.41}
    assert export.logged_pre(tmp_path / "missing.csv") == {}
