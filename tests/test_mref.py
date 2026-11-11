"""Market-referenced diagnostic (mref) on small frames built in each test.

Expected values are worked out by hand in the comments of each test.
"""

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval.forecasts import _market_calls
from eurohoops.eval.mref import build_report, cross_entropy, paired_table, verdict

SEASON = 2026


def games_frame(specs: list[tuple[str, int, bool]]) -> pd.DataFrame:
    """Regular-season games from (game_id, round, played). Round r tips off 2026-10-r, 17:00."""
    return pd.DataFrame(
        {
            "game_id": [s[0] for s in specs],
            "season": SEASON,
            "round": [s[1] for s in specs],
            "phase": "RS",
            "tipoff_utc": [f"2026-10-{s[1]:02d}T17:00:00Z" for s in specs],
            "home": "AAA",
            "away": "BBB",
            "neutral": False,
            "played": [s[2] for s in specs],
            "forfeit": False,
            "home_score": [80.0 if s[2] else np.nan for s in specs],
            "away_score": [70.0 if s[2] else np.nan for s in specs],
        }
    )


def scored(probs: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({"game_id": list(probs), "p_home": list(probs.values())})


def market_of(games: pd.DataFrame, probs: dict[str, float]) -> pd.DataFrame:
    """MKT rows: the games' own tip-off, phase and round, with the given p_home."""
    rows = games[games["game_id"].isin(probs)].copy()
    return rows.assign(p_home=rows["game_id"].map(probs))


def test_cross_entropy_and_paired_gap_match_hand_values() -> None:
    # With q = 1, the cross-entropy is -ln p. With q = 0 it is -ln(1 - p). With q = 0.5 and
    # p = 0.5 it is ln 2.
    # G1: q 1.0; model p 0.5 -> ln 2; Elo p 0.25 -> ln 4; gap -ln 2.
    # G2: q 0.0; model p 0.5 -> ln 2; Elo p 0.8 -> -ln 0.2; gap ln 2 + ln 0.2.
    # G3: q 0.5; model p 0.5 and Elo p 0.5 -> gap 0.
    games = games_frame([("G1", 1, True), ("G2", 2, True), ("G3", 3, True)])
    market = market_of(games, {"G1": 1.0, "G2": 0.0, "G3": 0.5})
    model = scored({"G1": 0.5, "G2": 0.5, "G3": 0.5})
    elo = scored({"G1": 0.25, "G2": 0.8, "G3": 0.5})
    table = paired_table(market, model, elo).set_index("game_id")
    assert table.loc["G1", "ce_model"] == pytest.approx(math.log(2))
    assert table.loc["G1", "ce_elo"] == pytest.approx(math.log(4))
    assert table.loc["G1", "gap"] == pytest.approx(-math.log(2))
    assert table.loc["G2", "ce_model"] == pytest.approx(math.log(2))
    assert table.loc["G2", "ce_elo"] == pytest.approx(-math.log(0.2))
    assert table.loc["G2", "gap"] == pytest.approx(math.log(2) + math.log(0.2))
    assert table.loc["G3", "gap"] == pytest.approx(0.0)


def test_cross_entropy_clips_probabilities() -> None:
    # p = 0 is clipped to 1e-6, so the loss with q = 1 is -ln(1e-6); p = 1 with q = 0 likewise.
    ce = cross_entropy(np.array([1.0, 0.0]), np.array([0.0, 1.0]))
    assert ce == pytest.approx([-math.log(1e-6), -math.log(1e-6)])


def test_odds_row_fetched_at_or_after_tipoff_is_ignored(tmp_path: Path) -> None:
    # G1 tips off at 17:00. Its 15:00 snapshot (0.6) is used. Its 17:00 snapshot (0.95, exactly
    # at tip-off) and its 18:00 snapshot (0.9) are both after the pre-tip cut, so they are not.
    # G2 has only a 18:00 snapshot, so it has no market row.
    games = games_frame([("G1", 1, True), ("G2", 1, True)])
    odds_path = tmp_path / "odds.csv"
    pd.DataFrame(
        {
            "game_id": ["G1", "G1", "G1", "G2"],
            "season": SEASON,
            "p_home": [0.6, 0.95, 0.9, 0.7],
            "fetched_at_utc": [
                "2026-10-01T15:00:00Z",
                "2026-10-01T17:00:00Z",
                "2026-10-01T18:00:00Z",
                "2026-10-01T18:00:00Z",
            ],
            "tipoff_utc": "2026-10-01T17:00:00Z",
        }
    ).to_csv(odds_path, index=False)
    market = _market_calls(odds_path, games, SEASON)
    assert list(market["game_id"]) == ["G1"]
    assert market["p_home"].iloc[0] == pytest.approx(0.6)


def test_before_checkpoint_only_n_and_sd_are_reported() -> None:
    # Look 1 needs round 19. Round 19 is unplayed, so look 1 is not due.
    games = games_frame([("G1", 1, True), ("G2", 2, True), ("G3", 19, False)])
    market = market_of(games, {"G1": 0.6, "G2": 0.5})
    probs = {"G1": 0.7, "G2": 0.4}
    report = build_report(
        games, SEASON, 1, market, {"m1": scored(probs)}, scored({"G1": 0.5, "G2": 0.5})
    )
    block = report["models"]["m1"]
    assert block["n"] == 2
    assert block["gap_sd"] is not None
    assert not {"gap_mean", "ci", "verdict"} & set(block)
    assert "not due" in report["status"]


def test_complete_checkpoint_with_fewer_than_100_games_is_not_testable() -> None:
    # Look 1 is complete: round 19 is played. Two shared games are far below 100.
    games = games_frame([("G1", 1, True), ("G2", 19, True)])
    market = market_of(games, {"G1": 0.6, "G2": 0.5})
    report = build_report(
        games,
        SEASON,
        1,
        market,
        {"m1": scored({"G1": 0.7, "G2": 0.4})},
        scored({"G1": 0.5, "G2": 0.5}),
    )
    block = report["models"]["m1"]
    assert block["n"] == 2
    assert "gap_mean" in block
    assert block["verdict"] == "not testable"


def test_verdict_rules() -> None:
    ci = [-0.03, -0.01]
    assert verdict(100, -0.02, ci) == "closer"
    assert verdict(99, -0.02, ci) == "not testable"
    assert verdict(100, 0.01, ci) == "not closer"
    assert verdict(100, -0.02, [-0.03, 0.001]) == "not closer"


def test_later_game_changes_no_earlier_game_value() -> None:
    # G3 tips off after G1 and G2. Adding it must leave their per-game values unchanged.
    games = games_frame([("G1", 1, True), ("G2", 2, True)])
    market = market_of(games, {"G1": 0.6, "G2": 0.5})
    model = scored({"G1": 0.7, "G2": 0.4})
    elo = scored({"G1": 0.5, "G2": 0.5})
    before = paired_table(market, model, elo).set_index("game_id")

    later = games_frame([("G1", 1, True), ("G2", 2, True), ("G3", 3, True)])
    market_later = market_of(later, {"G1": 0.6, "G2": 0.5, "G3": 0.1})
    model_later = scored({"G1": 0.7, "G2": 0.4, "G3": 0.99})
    elo_later = scored({"G1": 0.5, "G2": 0.5, "G3": 0.01})
    after = paired_table(market_later, model_later, elo_later).set_index("game_id")

    for col in ("ce_model", "ce_elo", "gap"):
        assert after.loc[["G1", "G2"], col].tolist() == pytest.approx(
            before.loc[["G1", "G2"], col].tolist()
        )


def test_game_without_market_row_or_in_one_log_is_not_counted() -> None:
    # G1: in all three. G2: no pre-tip odds row. G3: missing from Elo's log.
    games = games_frame([("G1", 1, True), ("G2", 2, True), ("G3", 3, True)])
    market = market_of(games, {"G1": 0.6, "G3": 0.5})
    model = scored({"G1": 0.7, "G2": 0.4, "G3": 0.5})
    elo = scored({"G1": 0.5, "G2": 0.5})
    table = paired_table(market, model, elo)
    assert list(table["game_id"]) == ["G1"]


def test_look_one_caps_regular_season_at_round_19() -> None:
    # G1 (round 1) gap 0; G2 (round 19) gap -ln 2; both count at look 1.
    # G3 (round 20, regular season) gap about 6.21: excluded at look 1, counted at look 2.
    # G4 (playoff, round 5) gap about 6.21: excluded at look 1 by phase, counted at look 2.
    # Model p 0.5 / Elo p 0.5 on G1 gives gap 0. q = 1, so each cross-entropy is -ln p.
    games = games_frame([("G1", 1, True), ("G2", 19, True), ("G3", 20, True), ("G4", 5, True)])
    games.loc[games["game_id"] == "G4", "phase"] = "PO"
    market = market_of(games, {"G1": 1.0, "G2": 1.0, "G3": 1.0, "G4": 1.0})
    model = scored({"G1": 0.5, "G2": 0.5, "G3": 0.001, "G4": 0.001})
    elo = scored({"G1": 0.5, "G2": 0.25, "G3": 0.5, "G4": 0.5})
    look1 = build_report(games, SEASON, 1, market, {"m1": model}, elo)["models"]["m1"]
    assert look1["n"] == 2
    assert look1["gap_sd"] == pytest.approx(math.log(2) / math.sqrt(2))
    look2 = build_report(games, SEASON, 2, market, {"m1": model}, elo)["models"]["m1"]
    assert look2["n"] == 4


def test_scored_path_complete_checkpoint_small_n_is_not_testable() -> None:
    # q = 1, so each cross-entropy is -ln p. Gaps: G1 0 (0.5 vs 0.5); G2 -ln 2 (0.5 vs 0.25);
    # G3 ln 2 - ln 8 = -2 ln 2 (0.5 vs 0.125). Mean = -3 ln 2 / 3 = -ln 2.
    games = games_frame([("G1", 1, True), ("G2", 10, True), ("G3", 19, True)])
    market = market_of(games, {"G1": 1.0, "G2": 1.0, "G3": 1.0})
    model = scored({"G1": 0.5, "G2": 0.5, "G3": 0.5})
    elo = scored({"G1": 0.5, "G2": 0.25, "G3": 0.125})
    block = build_report(games, SEASON, 1, market, {"m1": model}, elo)["models"]["m1"]
    assert block["n"] == 3
    assert block["gap_mean"] == pytest.approx(-math.log(2))
    assert len(block["ci"]) == 2
    assert all(isinstance(x, float) for x in block["ci"])
    assert block["ci"][0] <= block["gap_mean"] <= block["ci"][1]
    assert block["verdict"] == "not testable"


def _scored_path_block(model_p: float, elo_p: float) -> Any:
    """A complete look 1 with 100 shared games, all in the same pair of probabilities (q = 1)."""
    specs = [(f"G{i}", 1, True) for i in range(99)] + [("G99", 19, True)]
    games = games_frame(specs)
    ids = [s[0] for s in specs]
    market = market_of(games, dict.fromkeys(ids, 1.0))
    model = scored(dict.fromkeys(ids, model_p))
    elo = scored(dict.fromkeys(ids, elo_p))
    return build_report(games, SEASON, 1, market, {"m1": model}, elo)["models"]["m1"]


def test_scored_path_closer_when_every_gap_is_negative() -> None:
    # Model 0.5, Elo 0.25: every gap is -ln 2 < 0, so the CI is degenerate and below 0.
    block = _scored_path_block(0.5, 0.25)
    assert block["n"] == 100
    assert block["verdict"] == "closer"


def test_scored_path_not_closer_when_every_gap_is_positive() -> None:
    # Model 0.25, Elo 0.5: every gap is +ln 2 > 0.
    block = _scored_path_block(0.25, 0.5)
    assert block["n"] == 100
    assert block["verdict"] == "not closer"
    assert block["gap_mean"] > 0
