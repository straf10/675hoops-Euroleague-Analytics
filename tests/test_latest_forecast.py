"""The scored row of a game is its latest forecast stamped before tip-off (per model version)."""

import pandas as pd

from eurohoops.api.readmodel import _ordered
from eurohoops.eval.backtest import TunedModel
from eurohoops.eval.forecasts import _provable
from eurohoops.eval.scorecard import _scored, latest_per_model_game
from eurohoops.predict import LOG_COLUMNS
from tests.conftest import make_games

TIPOFF = "2026-10-01T18:00:00Z"  # round 1's first game in make_games


def row(game_id: str, stamp: str, p_home: str, version: str = "v1") -> dict[str, str]:
    return {
        "game_id": game_id,
        "season": "2026",
        "round": "1",
        "phase": "RS",
        "tipoff_utc": TIPOFF,
        "home": "AAA",
        "away": "BBB",
        "p_home": p_home,
        "exp_margin": "1.00",
        "model": "elo",
        "model_version": version,
        "predicted_at_utc": stamp,
    }


def log_of(rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(LOG_COLUMNS))


def test_latest_per_model_game_keeps_the_latest_row_of_each_version() -> None:
    log = log_of(
        [
            row("G1", "2026-10-01T10:00:00Z", "0.6000"),
            row("G1", "2026-10-01T12:00:00Z", "0.7000"),
            row("G1", "2026-10-01T11:00:00Z", "0.5000", version="v2"),
        ]
    )
    kept = latest_per_model_game(log)
    assert sorted(zip(kept["model_version"], kept["p_home"], strict=True)) == [
        ("v1", "0.7000"),
        ("v2", "0.5000"),
    ]


def test_provable_takes_the_latest_row_before_tipoff_and_ignores_later_ones() -> None:
    log = log_of(
        [
            row("G1", "2026-10-01T10:00:00Z", "0.6000"),
            row("G1", "2026-10-01T17:30:00Z", "0.7000"),
            row("G1", "2026-10-01T19:00:00Z", "0.9000"),  # stamped after tip-off: never counts
        ]
    )
    (kept,) = _provable(log, manual_pushes=[]).to_dict("records")
    assert kept["p_home"] == "0.7000"


def test_scored_row_is_the_latest_forecast_before_tipoff(tuned: TunedModel) -> None:
    games = make_games({2026: True})
    rows = pd.DataFrame(
        [
            row("E2026_1", "2026-10-01T09:00:00Z", "0.4000"),
            row("E2026_1", "2026-10-01T17:00:00Z", "0.8000"),
        ]
    ).astype({"p_home": float, "exp_margin": float})
    scored = _scored(rows, games, tuned)
    assert scored["p_home"].tolist() == [0.8]


def test_the_readmodel_counts_the_latest_row_before_tipoff_first() -> None:
    log = log_of(
        [
            row("G1", "2026-10-01T10:00:00Z", "0.6000"),
            row("G1", "2026-10-01T17:30:00Z", "0.7000"),
            row("G1", "2026-10-01T19:00:00Z", "0.9000"),  # late: sorts after every on-time row
        ]
    )
    ordered = _ordered(log)
    assert ordered["p_home"].tolist() == ["0.7000", "0.6000", "0.9000"]
    assert ordered["late"].tolist() == [False, False, True]
