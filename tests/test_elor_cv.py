"""ELOR CV harness (``eval/elor_cv.py``): leakage, selection, bootstrap and the report.

Leakage guarantee: a game's ELOR difference uses only games tipped off before its round cutoff
(``minutes.round_cutoffs``) and roster rows stamped before it. Removing or editing later games
(results and box rows) or later roster rows (new signings, later end dates) leaves every game
at or before that cutoff unchanged. The control tests make the same kind of edit earlier and
show it does move later games, so the comparison can fail.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.config import ELOR_CV
from eurohoops.eval import elor_cv
from eurohoops.eval.m7_backtest import cluster_bootstrap_ci
from eurohoops.models.elor import ElorSetting, elor_diff
from eurohoops.models.minutes import round_cutoffs
from tests import elor_synthetic as syn

SETTING = ElorSetting(0.5, 4)  # largest weight, every 2026 round still blended


def _diffs(inputs: elor_cv.ElorInputs) -> pd.Series:
    ctx = elor_cv.build_context(inputs, syn.spec())
    values = elor_diff(ctx.elo_diff, ctx.rounds, ctx.offsets, SETTING)
    return pd.Series(values, index=ctx.games["game_id"].astype(str))


def _cutoff(rnd: int) -> float:
    games, _ = syn.games_and_box()
    part = games[(games["season"] == 2026) & (games["round"] == rnd)]
    return float(part["tipoff_utc"].min().timestamp())


def _upto(games: pd.DataFrame, cutoff: float) -> list[str]:
    ordered = games.sort_values("tipoff_utc").reset_index(drop=True)
    cut = round_cutoffs(ordered).to_numpy()
    return ordered.loc[cut <= cutoff, "game_id"].astype(str).tolist()


def _later_edits(cutoff: float) -> elor_cv.ElorInputs:
    """Results, box rows and roster rows at or after ``cutoff`` changed or added."""
    games, box = syn.games_and_box()
    late = games["tipoff_utc"].map(pd.Timestamp.timestamp).to_numpy() >= cutoff
    games.loc[late, ["home_score", "away_score"]] = games.loc[
        late, ["away_score", "home_score"]
    ].to_numpy() + np.array([0, 9])
    late_ids = set(games.loc[late, "game_id"])
    rows = box["game_id"].isin(late_ids).to_numpy()
    box.loc[rows, "sec"] = box.loc[rows, "sec"] * 2 + 50
    extra_box = pd.DataFrame(
        [{"game_id": g, "team": "D", "player_id": "D7", "sec": 2400} for g in sorted(late_ids)]
    )
    rosters = syn.roster()
    open_end = rosters["end"].isna() | (rosters["end"] > cutoff)
    rosters.loc[open_end & (rosters["season"] == 2026), "end"] = cutoff + 3e6
    signings = pd.DataFrame(
        [
            {"season": 2026, "club": "D", "player_id": "D7", "start": cutoff, "end": np.nan},
            {"season": 2026, "club": "A", "player_id": "B1", "start": cutoff + 1, "end": np.nan},
        ]
    )
    return syn.inputs(
        games,
        pd.concat([box, extra_box], ignore_index=True),
        pd.concat([rosters, signings], ignore_index=True),
    )


@pytest.mark.parametrize("rnd", [1, 2, 3, 4])
def test_later_edits_leave_games_up_to_the_cutoff_unchanged(rnd: int) -> None:
    cutoff = _cutoff(rnd)
    base = _diffs(syn.inputs())
    moved = _diffs(_later_edits(cutoff))
    ids = _upto(syn.games_and_box()[0], cutoff)
    assert len(ids) == 24 + 2 * rnd  # 2023 to 2025 and 2026 up to round rnd
    np.testing.assert_array_equal(moved[ids].to_numpy(), base[ids].to_numpy())


@pytest.mark.parametrize("rnd", [1, 2, 3])
def test_removing_later_games_and_roster_rows_leaves_earlier_games_unchanged(rnd: int) -> None:
    cutoff = _cutoff(rnd)
    games, box = syn.games_and_box()
    keep = games["tipoff_utc"].map(pd.Timestamp.timestamp).to_numpy() < _cutoff(rnd + 1)
    rosters = syn.roster()
    rosters = rosters[rosters["start"] < cutoff].reset_index(drop=True)
    cut_games = games[keep].reset_index(drop=True)
    cut = syn.inputs(cut_games, box[box["game_id"].isin(set(cut_games["game_id"]))], rosters)
    base = _diffs(syn.inputs())
    moved = _diffs(cut)
    ids = _upto(games, cutoff)
    np.testing.assert_array_equal(moved[ids].to_numpy(), base[ids].to_numpy())


def test_control_an_earlier_box_edit_moves_later_games() -> None:
    games, box = syn.games_and_box()
    rows = (box["game_id"] == "E2026_10") & (box["player_id"] == "A1")
    box.loc[rows, "sec"] = 2390
    base = _diffs(syn.inputs())
    moved = _diffs(syn.inputs(games, box))
    r2 = ["E2026_20", "E2026_21"]
    assert not np.array_equal(moved[r2].to_numpy(), base[r2].to_numpy())
    r1 = _upto(games, _cutoff(1))
    np.testing.assert_array_equal(moved[r1].to_numpy(), base[r1].to_numpy())


def test_control_an_earlier_roster_row_moves_later_games() -> None:
    rosters = syn.roster()
    star = pd.DataFrame(
        [{"season": 2026, "club": "C", "player_id": "A1", "start": _cutoff(2) - 10, "end": np.nan}]
    )
    base = _diffs(syn.inputs())
    moved = _diffs(syn.inputs(rosters=pd.concat([rosters, star], ignore_index=True)))
    assert not np.array_equal(moved[["E2026_20"]].to_numpy(), base[["E2026_20"]].to_numpy())


def test_a_round1_stamp_never_reaches_round1() -> None:
    """The approved strict rule: a stamp made during round 1 (after its cutoff) leaves round 1's
    own predictions unchanged and moves later rounds."""
    stamp = pd.DataFrame(
        [{"season": 2026, "club": "C", "player_id": "A1", "start": _cutoff(1) + 3600 * 30}]
    ).assign(end=np.nan)
    rosters = pd.concat([syn.roster(), stamp], ignore_index=True)
    base = _diffs(syn.inputs())
    moved = _diffs(syn.inputs(rosters=rosters))
    r1, r2 = ["E2026_10", "E2026_11"], ["E2026_20", "E2026_21"]
    np.testing.assert_array_equal(moved[r1].to_numpy(), base[r1].to_numpy())
    assert not np.array_equal(moved[r2].to_numpy(), base[r2].to_numpy())


def test_a_fold_without_newcomer_history_stops_the_build() -> None:
    with pytest.raises(ValueError, match="no newcomer history"):
        elor_cv.build_context(syn.inputs(), syn.spec(elo_warmup=(2023,), folds=(2024, 2025)))


def test_mismatched_club_codes_stop_the_build() -> None:
    rosters = syn.roster().replace({"club": {"D": "DD"}})
    with pytest.raises(ValueError, match="roster club codes"):
        elor_cv.build_context(syn.inputs(rosters=rosters), syn.spec())


# --- selection and bootstrap -------------------------------------------------------------------


def test_grid_is_twelve_settings_in_simplicity_order() -> None:
    settings = elor_cv.grid_settings(ELOR_CV)
    assert len(settings) == 12
    first = ["w0.2|n4", "w0.2|n8", "w0.2|n16", "w0.2|n24", "w0.35|n4"]
    assert [s.key() for s in settings[:5]] == first
    assert settings[-1].key() == "w0.5|n24"
    assert ELOR_CV.folds == tuple(range(2015, 2024))
    assert ELOR_CV.elo_warmup[0] == 2007
    assert ELOR_CV.bootstrap_seed == 20261015
    assert ELOR_CV.bootstrap_resamples == 10000
    assert ELOR_CV.shadow_log_loss_margin == 0.002
    assert (ELOR_CV.elo_params.k, ELOR_CV.elo_params.hca, ELOR_CV.elo_params.reversion) == (
        20.0,
        90.0,
        0.25,
    )


def test_one_se_rule_picks_the_simplest_setting_within_its_se() -> None:
    settings = [ElorSetting(0.2, 4), ElorSetting(0.2, 8), ElorSetting(0.5, 4)]
    losses = {"w0.2|n4": 0.6100, "w0.2|n8": 0.6040, "w0.5|n4": 0.6000}
    se = {"w0.2|n4": 0.0050, "w0.2|n8": 0.0050, "w0.5|n4": 0.0}
    assert elor_cv.select(losses, se, settings) == ElorSetting(0.2, 8)
    se["w0.2|n8"] = 0.0030
    assert elor_cv.select(losses, se, settings) == ElorSetting(0.5, 4)


def test_bootstrap_sd_is_game_weighted_over_whole_seasons() -> None:
    rng = np.random.default_rng(0)
    gap = rng.normal(0.0, 0.1, 30)
    cluster = np.repeat([0, 1, 2], [5, 10, 15])
    draw = elor_cv.season_draws(3, 500, 11)
    sums = np.array([gap[cluster == c].sum() for c in range(3)])
    counts = np.array([5.0, 10.0, 15.0])
    manual = [sums[d].sum() / counts[d].sum() for d in draw]
    assert elor_cv.bootstrap_gap_sd(gap, cluster, draw) == pytest.approx(np.std(manual, ddof=1))
    # Same draws as the CI helper for the same seed.
    _, low, high = cluster_bootstrap_ci(gap, cluster, 500, 11)
    assert (low, high) == tuple(np.percentile(manual, [2.5, 97.5]))


# --- the run and the check ---------------------------------------------------------------------


def test_run_cv_report_and_games(tmp_path: Path) -> None:
    report, detail = elor_cv.run_cv(syn.inputs(), spec=syn.spec(tmp_path), git_head="abc")
    assert report["scored_games"] == 16 == len(detail)
    assert report["per_fold_games"] == {"2025": 8, "2026": 8}
    assert len(report["settings"]) == 12
    assert report["settings_within_one_se"] == len(report["within_one_se"]) >= 1
    assert report["selected"]["key"] in report["within_one_se"]
    assert set(report["shadow_criteria"]) == {
        "below_elo",
        "non_inferior",
        "worth_a_version",
        "all",
    }
    low, high = report["selected_minus_elo"]["ci95"]
    assert low <= report["selected_minus_elo"]["mean"] <= high
    per = report["settings"]["w0.2|n4"]["per_season"]
    assert set(per) == {"2025", "2026"} and per["2025"]["games"] == 8
    assert {"log_loss", "brier"} <= set(report["elo"])
    assert report["first_round_rule"] == "strict"
    priors = report["newcomer_priors"]
    assert set(priors) == {"2025", "2026"}
    assert priors["2026"]["history"] == [2024, 2025] and priors["2026"]["share"] > 0
    assert {"p_elo", "p_w0.5|n24", "round_index", "prior_available"} <= set(detail.columns)
    assert detail["prior_available"].all()


def test_run_cv_w0_zero_column_equals_elo(tmp_path: Path) -> None:
    _, detail = elor_cv.run_cv(syn.inputs(), spec=syn.spec(tmp_path, w0=(0.0, 0.2)), git_head="abc")
    for n in ELOR_CV.n_rounds:
        np.testing.assert_array_equal(detail[f"p_w0|n{n}"], detail["p_elo"])


def test_scored_games_skip_neutral_forfeit_and_unplayed() -> None:
    games, box = syn.games_and_box()
    games.loc[games["game_id"] == "E2026_10", "neutral"] = True
    games.loc[games["game_id"] == "E2026_11", "forfeit"] = True
    games.loc[games["game_id"] == "E2026_20", "played"] = False
    ctx = elor_cv.build_context(syn.inputs(games, box), syn.spec())
    assert int(ctx.scored.sum()) == 13


def test_cv_check_reports_counts_coverage_and_start_dates() -> None:
    out = elor_cv.cv_check(syn.inputs(), spec=syn.spec(min_rostered=4))
    assert out["per_fold_games"] == {"2025": 8, "2026": 8}
    cov = out["roster_coverage"]
    # 2026: A has 3 players after A4 left (its 4 games); every other side has 4 or more.
    assert cov["both_sides_min_rostered"] == 12
    assert cov["prior_available_games"] == 16
    # Slots on the prior: A5 in 2025 round 1, D5 in D games of 2026 rounds 1-3, B9 in rounds 3-4.
    assert cov["share_prior_slots"] == 6 and cov["rating_prior_slots"] == 6
    assert 0 < cov["share_prior_slots_share"] < 1
    assert set(out["newcomer_priors"]) == {"2025", "2026"}
    assert out["newcomer_priors_live"] == {}
    assert out["start_dates"]["2026"]["start_after_round1"] == 1  # B9
    assert out["start_dates"]["2026"]["start_after_round1_played_before_stamp"] == 0
    assert out["start_dates"]["2025"]["start_after_round1_began"] == 0
    assert set(out["prior"]["margin_scale"]) == {"2025", "2026"}
    assert out["prior"]["round1_offset_sd"] > 0


def test_cv_check_counts_a_stamp_that_lags_the_debut() -> None:
    rosters = syn.roster()
    late = (rosters["season"] == 2026) & (rosters["player_id"] == "D1")
    rosters.loc[late, "start"] = _cutoff(1) + 3600 * 30  # during round 1, after D1's debut
    rosters.loc[(rosters["season"] == 2026) & (rosters["player_id"] == "D2"), "start"] = (
        _cutoff(3) + 3600 * 30
    )
    out = elor_cv.cv_check(syn.inputs(rosters=rosters), spec=syn.spec())
    counts = out["start_dates"]["2026"]
    assert counts["start_during_round1"] == 1
    assert counts["start_during_round1_played_before_stamp"] == 1
    assert counts["start_after_round1_played_before_stamp"] == 1
