import math
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from eurohoops.eval.backtest import TunedModel
from eurohoops.eval.forecasts import build_forecasts
from eurohoops.live_m1 import M1_LOG_COLUMNS
from eurohoops.models.elo import EloParams
from eurohoops.predict import LOG_COLUMNS

LABELS = {"elo": "Elo", "m1": "M1", "m5": "M5"}
EARLY = "2026-10-01T18:00:00Z"
MID = "2026-10-08T18:00:00Z"
LATE = "2026-10-15T18:00:00Z"

# game, round, phase, tipoff, home score, away score (G6 is unplayed, G8 is a forfeit)
GAMES = [
    ("G1", 1, "RS", EARLY, 90, 80),  # +10
    ("G2", 1, "RS", EARLY, 82, 80),  # +2
    ("G3", 2, "RS", MID, 70, 75),  # -5
    ("G4", 2, "RS", MID, 100, 90),  # +10
    ("G5", 3, "PO", LATE, 80, 70),  # +10
    ("G6", 3, "PO", LATE, None, None),
    ("G7", 3, "PO", LATE, 60, 50),  # only ever logged late
    ("G8", 2, "RS", MID, 20, 0),  # forfeit
]
STAMP = {EARLY: "2026-10-01T08:00:00Z", MID: "2026-10-07T08:00:00Z", LATE: "2026-10-14T08:00:00Z"}
NOW_PUSH = datetime(2026, 10, 2, tzinfo=UTC)  # after the round-1 rows' tip-off, before the rest


def games() -> pd.DataFrame:
    rows = [
        {
            "game_id": g,
            "season": 2026,
            "round": r,
            "phase": ph,
            "tipoff_utc": pd.Timestamp(t),
            "home": f"H{g}",
            "away": f"A{g}",
            "home_score": hs,
            "away_score": a,
            "played": hs is not None,
            "forfeit": g == "G8",
            "neutral": False,
        }
        for g, r, ph, t, hs, a in GAMES
    ]
    return pd.DataFrame(rows)


def elo_rows() -> list[list[object]]:
    tip = {g: (r, ph, t) for g, r, ph, t, _, _ in GAMES}
    calls = [
        ("G1", 0.8, 5.0, None),
        ("G2", 0.4, -3.0, None),
        ("G2", 0.1, -9.0, "2026-10-01T09:00:00Z"),  # a re-log: the earlier row counts
        ("G3", 0.5, 0.0, None),  # exactly 50%: no pick
        ("G4", 0.7, 4.0, None),
        ("G5", 0.6, 2.0, None),
        ("G6", 0.6, 2.0, None),  # not played yet
        ("G7", 0.9, 9.0, "2026-10-15T18:00:00Z"),  # stamped at tip-off: late, never scored
        ("G8", 0.9, 9.0, None),  # forfeit
    ]
    rows = []
    for g, p, m, stamp in calls:
        r, ph, t = tip[g]
        rows.append([g, 2026, r, ph, t, f"H{g}", f"A{g}", p, m, "elo", "v1", stamp or STAMP[t]])
    return rows


def m1_rows() -> list[list[object]]:
    tip = {g: (r, ph, t) for g, r, ph, t, _, _ in GAMES}
    calls = [("G3", 0.3, -4.0, 150.0), ("G4", 0.6, 12.0, 180.0), ("G5", 0.4, -2.0, 160.0)]
    rows = []
    for g, p, m, total in calls:
        r, ph, t = tip[g]
        rows.append(
            [g, 2026, r, ph, t, f"H{g}", f"A{g}", p, m, total, 10.0, 7, 16.0, "m1", "v1", STAMP[t]]
        )
    return rows


@pytest.fixture
def logs(tmp_path: Path) -> dict[str, Path | None]:
    elo, m1 = tmp_path / "elo.csv", tmp_path / "m1.csv"
    pd.DataFrame(elo_rows(), columns=list(LOG_COLUMNS)).to_csv(elo, index=False)
    pd.DataFrame(m1_rows(), columns=list(M1_LOG_COLUMNS)).to_csv(m1, index=False)
    return {"elo": elo, "m1": m1, "m5": None}


def ll(*probs: float) -> float:
    return -sum(math.log(p) for p in probs) / len(probs)


def test_season_metrics_by_hand(logs: dict[str, Path | None]) -> None:
    fc = build_forecasts(logs, LABELS, games(), 2026)
    assert [m["key"] for m in fc["models"]] == ["elo", "m1"]  # m5 has no log
    assert [m["first_round"] for m in fc["models"]] == [1, 2]  # no backfill: M1 starts at round 2
    elo, m1 = fc["season"]
    # Elo: G1-G5 scored (G6 unplayed, G7 late, G8 forfeit); margins +10 +2 -5 +10 +10.
    assert elo["n"] == 5
    assert (elo["picks"], elo["right"]) == (4, 3)  # G3 at exactly 50% is no pick; G2 wrong
    assert elo["right_pct"] == 0.75
    assert elo["log_loss"] == pytest.approx(ll(0.8, 0.4, 0.5, 0.7, 0.6), abs=1e-6)
    assert elo["brier"] == pytest.approx((0.04 + 0.36 + 0.25 + 0.09 + 0.16) / 5, abs=1e-6)
    assert elo["margin_mae"] == pytest.approx((5 + 5 + 5 + 6 + 8) / 5)
    assert elo["within"] == {"5": 0.6, "10": 1.0}
    assert elo["totals_mae"] is None
    # M1: G3 (away won), G4, G5.
    assert m1["n"] == 3
    assert (m1["picks"], m1["right"]) == (3, 2)
    assert m1["right_pct"] == pytest.approx(2 / 3, abs=1e-6)
    assert m1["log_loss"] == pytest.approx(ll(0.7, 0.6, 0.4), abs=1e-6)
    assert m1["brier"] == pytest.approx((0.09 + 0.16 + 0.36) / 3, abs=1e-6)
    assert m1["margin_mae"] == pytest.approx((1 + 2 + 12) / 3)
    assert m1["within"] == {
        "5": pytest.approx(2 / 3, abs=1e-6),
        "10": pytest.approx(2 / 3, abs=1e-6),
    }
    assert m1["totals_mae"] == pytest.approx((5 + 10 + 10) / 3)  # totals 145, 190, 150


def test_shared_games_are_the_intersection(logs: dict[str, Path | None]) -> None:
    shared = build_forecasts(logs, LABELS, games(), 2026)["shared"]
    assert shared["n"] == 3  # G3, G4, G5: M1's three games, which Elo also called
    elo, m1 = shared["rows"]
    assert (elo["model"], m1["model"]) == ("elo", "m1")
    assert elo["n"] == m1["n"] == 3
    assert (elo["picks"], elo["right"]) == (2, 2)  # G3 no pick; G4, G5 right
    assert elo["log_loss"] == pytest.approx(ll(0.5, 0.7, 0.6), abs=1e-6)
    assert elo["brier"] == pytest.approx((0.25 + 0.09 + 0.16) / 3, abs=1e-6)
    assert elo["margin_mae"] == pytest.approx((5 + 6 + 8) / 3)
    assert elo["within"] == {"5": pytest.approx(1 / 3, abs=1e-6), "10": 1.0}
    assert m1["log_loss"] == pytest.approx(ll(0.7, 0.6, 0.4), abs=1e-6)


def test_provable_filter_drops_rows_that_went_public_after_tip_off(
    logs: dict[str, Path | None],
) -> None:
    # Pushed at Oct 2: the round-1 rows (stamped Oct 1, tip-off Oct 1) became public after tip-off.
    fc = build_forecasts(logs, LABELS, games(), 2026, manual_pushes=(NOW_PUSH,))
    elo = fc["season"][0]
    assert elo["n"] == 3  # G1, G2 gone; G3-G5 remain
    assert [m["first_round"] for m in fc["models"]] == [2, 2]
    assert {g["game_id"] for g in fc["games"]} == {"G3", "G4", "G5"}


def test_rounds_group_regular_season_by_round_and_postseason_by_phase(
    logs: dict[str, Path | None],
) -> None:
    rounds = build_forecasts(logs, LABELS, games(), 2026)["rounds"]
    assert [(r["phase"], r["round"], r["games"]) for r in rounds] == [
        ("RS", 1, 2),
        ("RS", 2, 2),
        ("PO", None, 1),
    ]
    assert list(rounds[0]["models"]) == ["elo"]  # M1 has no entries before its first round
    assert rounds[0]["models"]["elo"]["right"] == 1  # G1 right, G2 wrong
    assert rounds[0]["models"]["elo"]["log_loss"] == pytest.approx(ll(0.8, 0.4), abs=1e-6)
    r2 = rounds[1]["models"]
    assert (r2["elo"]["n"], r2["elo"]["picks"], r2["elo"]["right"]) == (2, 1, 1)
    assert (r2["m1"]["n"], r2["m1"]["right"]) == (2, 2)
    assert r2["m1"]["margin_mae"] == pytest.approx(1.5)
    assert rounds[2]["models"]["m1"]["totals_mae"] == pytest.approx(10.0)


def test_games_list_is_newest_first_with_each_models_call(logs: dict[str, Path | None]) -> None:
    listed = build_forecasts(logs, LABELS, games(), 2026)["games"]
    assert [g["game_id"] for g in listed] == ["G5", "G4", "G3", "G2", "G1"]
    g3 = listed[2]
    assert (g3["round"], g3["home_score"], g3["away_score"]) == (2, 70, 75)
    assert (g3["home"], g3["away"]) == ("HG3", "AG3")  # source codes; the site maps them
    assert g3["models"]["elo"] == {"p_home": 0.5, "exp_margin": 0.0, "right": None}
    assert g3["models"]["m1"] == {"p_home": 0.3, "exp_margin": -4.0, "right": True}
    g1 = listed[4]
    assert list(g1["models"]) == ["elo"]  # no M1 entry before its first logged round
    assert g1["models"]["elo"]["right"] is True
    assert g1["tipoff_utc"] == EARLY


def test_empty_and_missing_logs(tmp_path: Path) -> None:
    fc = build_forecasts({"elo": tmp_path / "none.csv", "m1": None}, LABELS, games(), 2026)
    assert fc["models"] == [{"key": "elo", "label": "Elo", "first_round": None}]
    assert fc["season"][0]["n"] == 0 and fc["season"][0]["log_loss"] is None
    assert fc["shared"] == {"n": 0, "rows": []}
    assert fc["rounds"] == [] and fc["games"] == []


def odds_file(tmp_path: Path) -> Path:
    """Bookmaker fetches: G1 has an early and a closing fetch, G2 only one stamped after tip-off,
    G3 has none, G4 and G5 one each; G9 is a game the model never called."""
    cols = ["game_id", "season", "round", "tipoff_utc", "fetched_at_utc", "p_home"]
    rows = [
        ["G1", 2026, 1, EARLY, "2026-09-30T08:00:00Z", 0.60],
        ["G1", 2026, 1, EARLY, "2026-10-01T16:00:00Z", 0.90],  # the closing line
        ["G2", 2026, 1, EARLY, "2026-10-01T19:00:00Z", 0.30],  # after tip-off: no call
        ["G4", 2026, 2, MID, "2026-10-07T12:00:00Z", 0.5],  # exactly 50%: no pick
        ["G5", 2026, 3, LATE, "2026-10-14T12:00:00Z", 0.20],  # wrong
    ]
    path = tmp_path / "odds.csv"
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    return path


def test_market_is_the_closing_line_scored_on_finished_games(
    logs: dict[str, Path | None], tmp_path: Path
) -> None:
    fc = build_forecasts(logs, LABELS, games(), 2026, odds_log=odds_file(tmp_path))
    assert fc["published"] == "elo"
    market = fc["market"]
    assert market["label"] == "Bookmakers"
    season = market["season"]
    assert (season["n"], season["picks"], season["right"]) == (3, 2, 1)  # G1 right, G5 wrong
    assert season["right_pct"] == 0.5
    assert season["brier"] == pytest.approx((0.01 + 0.25 + 0.64) / 3, abs=1e-6)  # closing 0.90
    assert season["log_loss"] == pytest.approx(ll(0.9, 0.5, 0.2), abs=1e-6)


def test_accuracy_compares_both_on_the_games_both_called(
    logs: dict[str, Path | None], tmp_path: Path
) -> None:
    fc = build_forecasts(logs, LABELS, games(), 2026, odds_log=odds_file(tmp_path))
    acc = fc["accuracy"]
    assert [(a["phase"], a["round"], a["games"]) for a in acc] == [
        ("RS", 1, 1),  # G1 only: G2's only fetch came after tip-off
        ("RS", 2, 1),  # G4
        ("PO", None, 1),  # G5
    ]
    r1, r2, po = acc
    assert r1["model"]["right_pct"] == 1.0 and r1["market"]["right_pct"] == 1.0
    assert r1["model"]["brier"] == pytest.approx(0.04, abs=1e-6)  # Elo 0.8 on G1
    assert r1["market"]["brier"] == pytest.approx(0.01, abs=1e-6)
    assert r2["model"]["right_pct"] == 1.0  # Elo 0.7 on G4: right
    assert r2["market"]["picks"] == 0 and r2["market"]["right_pct"] is None
    assert po["model"]["brier"] == pytest.approx(0.16, abs=1e-6)  # Elo 0.6 on G5
    assert po["market"]["brier"] == pytest.approx(0.64, abs=1e-6)
    last = acc[-1]["to_date"]
    assert last["games"] == 3
    assert last["model"]["brier"] == pytest.approx((0.04 + 0.09 + 0.16) / 3, abs=1e-6)
    assert last["market"]["brier"] == pytest.approx((0.01 + 0.25 + 0.64) / 3, abs=1e-6)
    assert acc[0]["to_date"]["games"] == 1 and acc[1]["to_date"]["games"] == 2


def test_no_odds_means_no_market(logs: dict[str, Path | None], tmp_path: Path) -> None:
    for odds in (None, tmp_path / "missing.csv"):
        fc = build_forecasts(logs, LABELS, games(), 2026, odds_log=odds)
        assert fc["market"] is None and fc["accuracy"] == []


def test_published_defaults_to_the_first_model_and_must_be_present(
    logs: dict[str, Path | None],
) -> None:
    assert build_forecasts(logs, LABELS, games(), 2026)["published"] == "elo"
    assert build_forecasts(logs, LABELS, games(), 2026, published="m1")["published"] == "m1"
    assert build_forecasts(logs, LABELS, games(), 2026, published="m5")["published"] == "elo"


def baseline() -> TunedModel:
    """B0 at a constant 60% home-win rate (no neutral games in the fixture)."""
    return TunedModel(EloParams(k=20.0, hca=90.0, reversion=0.3), 1.0, 0.6, 3.0)


def test_round_headline_is_the_latest_completed_round(logs: dict[str, Path | None]) -> None:
    # PO has G6 still to play, so round 2 is the latest completed group.
    head = build_forecasts(logs, LABELS, games(), 2026, baseline=baseline())["headline"]
    assert (head["phase"], head["round"], head["games"]) == ("RS", 2, 2)
    assert head["called"] == 1  # G3 at exactly 50% is not called; G4 right
    assert head["brier"] == pytest.approx((0.25 + 0.09) / 2, abs=1e-6)
    assert head["baseline_brier"] == pytest.approx((0.36 + 0.16) / 2, abs=1e-6)
    # Lowest pre-game probability of the winner: G3, the away side at 50%.
    assert head["biggest_miss"] == {"winner": "AG3", "loser": "HG3", "p_winner": 0.5}


def test_round_headline_skips_a_round_still_to_play(logs: dict[str, Path | None]) -> None:
    unplayed = games()
    unplayed.loc[unplayed["game_id"] == "G4", "played"] = False  # round 2 is not finished
    unplayed.loc[unplayed["game_id"] == "G4", "home_score"] = None
    unplayed.loc[unplayed["game_id"] == "G4", "away_score"] = None
    head = build_forecasts(logs, LABELS, unplayed, 2026, baseline=baseline())["headline"]
    assert (head["round"], head["games"]) == (1, 2)
    assert head["called"] == 1  # G1 right; G2 (40%) called away and was wrong
    assert head["brier"] == pytest.approx((0.04 + 0.36) / 2, abs=1e-6)
    assert head["biggest_miss"] == {"winner": "HG2", "loser": "AG2", "p_winner": 0.4}


def test_round_headline_needs_the_baseline_and_a_finished_round(
    logs: dict[str, Path | None],
) -> None:
    assert build_forecasts(logs, LABELS, games(), 2026)["headline"] is None
    none_done = games()
    none_done["played"] = False
    none_done["home_score"] = None
    none_done["away_score"] = None
    none_done["forfeit"] = False
    fc = build_forecasts(logs, LABELS, none_done, 2026, baseline=baseline())
    assert fc["headline"] is None


def test_calibration_bins_are_equal_width_and_empty_bins_are_dropped(
    logs: dict[str, Path | None],
) -> None:
    cal = build_forecasts(logs, LABELS, games(), 2026)["calibration"]
    assert cal["games"] == 5  # Elo's scored games
    # Predicted 0.4 and 0.5 share [0.4, 0.6); 0.6 and 0.7 share [0.6, 0.8); 0.8 is [0.8, 1.0].
    assert [(b["lo"], b["hi"], b["n"]) for b in cal["bins"]] == [
        (0.4, 0.6, 2),
        (0.6, 0.8, 2),
        (0.8, 1.0, 1),
    ]
    low, mid, top = cal["bins"]
    assert low["predicted"] == pytest.approx(0.45) and low["observed"] == pytest.approx(0.5)
    assert mid["predicted"] == pytest.approx(0.65) and mid["observed"] == pytest.approx(1.0)
    assert top["predicted"] == pytest.approx(0.8) and top["observed"] == pytest.approx(1.0)
    # Wilson 95%: 2 of 2 wins gives [0.342, 1.0]; 1 of 1 gives [0.207, 1.0].
    assert mid["low"] == pytest.approx(0.3423, abs=1e-3) and mid["high"] == 1.0
    assert top["low"] == pytest.approx(0.2065, abs=1e-3) and top["high"] == 1.0
    assert low["low"] == pytest.approx(0.0945, abs=1e-3)  # 1 of 2
    assert low["high"] == pytest.approx(0.9055, abs=1e-3)


def test_calibration_without_games(tmp_path: Path) -> None:
    fc = build_forecasts({"elo": tmp_path / "none.csv"}, LABELS, games(), 2026)
    assert fc["calibration"] == {"games": 0, "bins": []}
