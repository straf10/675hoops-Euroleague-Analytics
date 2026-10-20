import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from eurohoops.eval.backtest import TunedModel
from eurohoops.inputs import INPUT_COLUMNS, backfill_rows, elo_strings
from eurohoops.models.elo import prepare, replay_with_ratings, win_probability
from eurohoops.predict import logged_keys, predict_upcoming
from tests.conftest import make_games

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)  # round 1 tips off 18:00-18:30 the same day
ROUND_LEAD = timedelta(hours=48)


def fixed(t: datetime):
    return lambda: t


def predict(
    games: pd.DataFrame, model: TunedModel, log: Path, inputs: Path | None, at: datetime = NOW
) -> int:
    return predict_upcoming(
        games,
        model,
        log_path=log,
        season=2026,
        replay_from=2024,
        round_lead=ROUND_LEAD,
        clock=fixed(at),
        inputs_log=inputs,
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def expected_ratings(
    games: pd.DataFrame, model: TunedModel
) -> dict[str, tuple[float, float, float]]:
    """game_id -> (diff, home_rating, away_rating) from one replay over the same frame."""
    frame = games[games["season"] >= 2024]
    diffs, home, away = replay_with_ratings(prepare(frame), model.params)
    return {
        gid: (float(diffs[i]), float(home[i]), float(away[i]))
        for i, gid in enumerate(frame["game_id"])
    }


@pytest.fixture
def games() -> pd.DataFrame:
    return make_games({2024: True, 2025: True, 2026: False})


def test_snapshot_rows_match_elo_rows_and_the_model(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    elo, inputs = tmp_path / "elo.csv", tmp_path / "inputs.csv"
    assert predict(games, tuned, elo, inputs) == 3
    elo_rows, snap = read_rows(elo), read_rows(inputs)
    assert tuple(snap[0]) == INPUT_COLUMNS
    assert [r["game_id"] for r in snap] == [r["game_id"] for r in elo_rows]
    expected = expected_ratings(games, tuned)
    for e, s in zip(elo_rows, snap, strict=True):
        diff, home, away = expected[s["game_id"]]
        assert s["p_home"] == e["p_home"] == f"{win_probability(diff):.4f}"
        assert s["exp_margin"] == e["exp_margin"] == f"{diff / tuned.margin_scale:.2f}"
        assert s["home_rating"] == f"{home:.1f}"
        assert s["away_rating"] == f"{away:.1f}"
        assert s["hca"] == "90.0"
        assert s["neutral"] == "false"
        assert s["diff"] == f"{diff:.1f}"
        assert s["margin_scale"] == "25.0000"
        assert s["model_version"] == e["model_version"] == tuned.version()
        assert s["predicted_at_utc"] == e["predicted_at_utc"] == "2026-10-01T08:00:00Z"
        assert s["source"] == "logged"


def test_snapshot_is_written_only_for_rows_the_elo_log_appends(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    elo, inputs = tmp_path / "elo.csv", tmp_path / "inputs.csv"
    predict(games, tuned, elo, None)  # Elo logged before snapshots existed
    assert predict(games, tuned, elo, inputs) == 0
    assert not inputs.exists() or read_rows(inputs) == []


def test_second_run_adds_no_snapshot_rows(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    elo, inputs = tmp_path / "elo.csv", tmp_path / "inputs.csv"
    predict(games, tuned, elo, inputs)
    prefix = inputs.read_bytes()
    assert predict(games, tuned, elo, inputs, at=NOW + timedelta(hours=1)) == 0
    assert inputs.read_bytes() == prefix


def test_neutral_game_has_no_home_court_advantage(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    games = games.copy()
    games.loc[games["game_id"] == "E2026_2", "neutral"] = True
    elo, inputs = tmp_path / "elo.csv", tmp_path / "inputs.csv"
    predict(games, tuned, elo, inputs)
    snap = {r["game_id"]: r for r in read_rows(inputs)}
    assert snap["E2026_2"]["neutral"] == "true"
    assert snap["E2026_2"]["hca"] == "0.0"
    assert snap["E2026_1"]["neutral"] == "false"
    assert snap["E2026_1"]["hca"] == "90.0"
    diff = float(snap["E2026_2"]["diff"])
    assert diff == pytest.approx(
        float(snap["E2026_2"]["home_rating"]) - float(snap["E2026_2"]["away_rating"]), abs=0.05
    )


def test_backfill_reproduces_logged_snapshots_and_masks_later_games(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    elo, inputs = tmp_path / "elo.csv", tmp_path / "inputs.csv"
    predict(games, tuned, elo, inputs)
    logged = read_rows(inputs)
    elo_rows = read_rows(elo)
    # The mart now holds every 2026 result, tipping off after the stamp (NOW) as well.
    played = make_games({2024: True, 2025: True, 2026: True})
    rows, report = backfill_rows(played, elo_rows, set(), tuned, 2024)
    assert report.matched == 3
    assert report.skipped == []
    for replayed, original in zip(rows, logged, strict=True):
        assert replayed | {"source": "logged"} == original | {"source": "logged"}
        assert replayed["source"] == "replayed"


def test_backfill_skips_a_row_whose_logged_string_differs(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    elo = tmp_path / "elo.csv"
    predict(games, tuned, elo, None)
    elo_rows = read_rows(elo)
    elo_rows[1]["p_home"] = "0.9999"
    rows, report = backfill_rows(games, elo_rows, set(), tuned, 2024)
    assert [r["game_id"] for r in rows] == [elo_rows[0]["game_id"], elo_rows[2]["game_id"]]
    assert report.matched == 2
    assert len(report.skipped) == 1
    assert "E2026_2" in report.skipped[0]


def test_backfill_skips_rows_of_another_model_version(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    elo = tmp_path / "elo.csv"
    predict(games, tuned, elo, None)
    elo_rows = read_rows(elo)
    for row in elo_rows:
        row["model_version"] = "0.1.0+other"
    rows, report = backfill_rows(games, elo_rows, set(), tuned, 2024)
    assert rows == []
    assert report.matched == 0
    assert len(report.skipped) == 3


def test_backfill_leaves_logged_rows_alone(
    games: pd.DataFrame, tuned: TunedModel, tmp_path: Path
) -> None:
    elo, inputs = tmp_path / "elo.csv", tmp_path / "inputs.csv"
    predict(games, tuned, elo, inputs)
    existing = logged_keys(inputs)
    rows, report = backfill_rows(games, read_rows(elo), existing, tuned, 2024)
    assert rows == []
    assert report.already == 3
    assert report.skipped == []


def test_elo_strings_round_like_the_log() -> None:
    assert elo_strings(100.0, 25.0) == (f"{win_probability(100.0):.4f}", "4.00")
