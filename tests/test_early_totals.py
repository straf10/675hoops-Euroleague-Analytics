"""Early-season totals diagnostic (B2) on tests/fixtures/early_totals only.

Expected values are worked out by hand from the fixture rows (see the comments in each test).
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from eurohoops.eval.early_totals import (
    _verdict,
    bucket_of,
    build_report,
    excludes_zero,
    line_by_game,
    m1_total_by_game,
)

FIXTURES = Path(__file__).parent / "fixtures" / "early_totals"


@pytest.fixture
def games() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "games.csv", dtype={"game_id": str})


@pytest.fixture
def odds() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "odds.csv", dtype={"game_id": str})


@pytest.fixture
def m1_log() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "m1_log.csv", dtype={"game_id": str})


def test_bucket_boundaries() -> None:
    assert bucket_of(1) == "1-5"
    assert bucket_of(5) == "1-5"
    assert bucket_of(6) == "6-10"
    assert bucket_of(10) == "6-10"
    assert bucket_of(11) == "11+"
    assert bucket_of(34) == "11+"
    assert bucket_of(0) is None


def test_snapshot_fetched_after_tipoff_is_ignored(games: pd.DataFrame, odds: pd.DataFrame) -> None:
    # G1 has a 999 snapshot at 18:00 and G2 a 1.0 snapshot at 17:30, both after the 17:00 tip-off.
    lines, late = line_by_game(odds, games)
    lines_by_game = dict(zip(lines["game_id"], lines["total"], strict=True))
    assert lines_by_game["G1"] == pytest.approx(160.5)  # latest pre-tip snapshot (15:00)
    assert lines_by_game["G2"] == pytest.approx(170.5)  # the only pre-tip snapshot (12:00)
    assert late == 2


def test_latest_pre_tipoff_snapshot_without_total_gives_no_line(
    games: pd.DataFrame, odds: pd.DataFrame
) -> None:
    # G3's latest pre-tip snapshot (16:00) has no total, so G3 has no line; an earlier snapshot
    # (09:00, 150.5) is not used as a fallback. G7 is the same case.
    lines, _ = line_by_game(odds, games)
    assert "G3" not in set(lines["game_id"])
    assert "G7" not in set(lines["game_id"])


def test_m1_scored_row_is_latest_pre_tipoff_and_post_tipoff_rows_never_count(
    m1_log: pd.DataFrame,
) -> None:
    # G1: 156.00 (stamped 09-30) beats 155.00 (09-28); the 999 row stamped after tip-off is out.
    # G2: 160.00 (stamped 10-06); the 1.00 row stamped after tip-off is out.
    totals = m1_total_by_game(m1_log).set_index("game_id")["m1_total"]
    assert totals["G1"] == pytest.approx(156.0)
    assert totals["G2"] == pytest.approx(160.0)


def test_m1_row_made_public_after_tipoff_by_manual_push_is_not_scored(
    m1_log: pd.DataFrame,
) -> None:
    # A push on 10-07 12:00 makes every row stamped before it public then. G1's tip-off (10-01)
    # is before that, so G1 has no scored row. G2's row (stamped 10-06) is public before its
    # 10-08 tip-off, so it still counts.
    push = [datetime(2026, 10, 7, 12, tzinfo=UTC)]
    totals = m1_total_by_game(m1_log, manual_pushes=push)
    assert "G1" not in set(totals["game_id"])
    assert totals.set_index("game_id").loc["G2", "m1_total"] == pytest.approx(160.0)


def test_report_matches_hand_computed_buckets(
    games: pd.DataFrame, odds: pd.DataFrame, m1_log: pd.DataFrame
) -> None:
    report = build_report(games, odds, m1_log, season=2026)
    assert report["games"] == {
        "scored": 9,  # G10 playoff, G11 forfeit and G12 unplayed are out
        "no_line": 2,  # G3, G7
        "no_m1": 1,  # G13
        "odds_snapshots_after_tipoff_ignored": 2,
    }
    early, mid, late = report["buckets"]["1-5"], report["buckets"]["6-10"], report["buckets"]["11+"]
    # 1-5: G1, G2, G3, G13. Common sample (line and M1) is G1, G2.
    assert (early["games"], early["with_line"], early["with_m1"], early["n"]) == (4, 3, 3, 2)
    # line - actual: G1 160.5 - 150 = 10.5, G2 170.5 - 165 = 5.5. M1 - actual: G1 6, G2 -5.
    assert early["line"]["mean"] == pytest.approx(8.0)
    assert early["m1"]["mean"] == pytest.approx(0.5)
    # 6-10: G4 and G5. line: -9.5 and -0.5. M1: -5 and -2.
    assert (mid["games"], mid["n"]) == (2, 2)
    assert mid["line"]["mean"] == pytest.approx(-5.0)
    assert mid["m1"]["mean"] == pytest.approx(-3.5)
    # 11+: G6, G7, G9. Common sample is G6, G9. line: 2.5 and -0.5. M1: 1 and -5.
    assert (late["games"], late["with_line"], late["with_m1"], late["n"]) == (3, 2, 3, 2)
    assert late["line"]["mean"] == pytest.approx(1.0)
    assert late["m1"]["mean"] == pytest.approx(-2.0)


def test_each_ci_brackets_its_mean(
    games: pd.DataFrame, odds: pd.DataFrame, m1_log: pd.DataFrame
) -> None:
    report = build_report(games, odds, m1_log, season=2026)
    for bucket in report["buckets"].values():
        for metric in ("line", "m1"):
            lo, hi = bucket[metric]["ci95"]
            assert lo <= bucket[metric]["mean"] <= hi


def test_report_is_deterministic(
    games: pd.DataFrame, odds: pd.DataFrame, m1_log: pd.DataFrame
) -> None:
    assert build_report(games, odds, m1_log, 2026) == build_report(games, odds, m1_log, 2026)


def test_fixture_verdicts(games: pd.DataFrame, odds: pd.DataFrame, m1_log: pd.DataFrame) -> None:
    report = build_report(games, odds, m1_log, season=2026)
    # Line: early values {10.5, 5.5} give a CI entirely above 0; late {2.5, -0.5} a CI through 0.
    assert report["verdict"]["line"] == {
        "early_bias_present": True,
        "early_shift_opposite": False,
    }
    # M1: early values {6, -5} give a CI through 0, so no declaration and no opposite shift.
    assert report["verdict"]["m1"] == {
        "early_bias_present": False,
        "early_shift_opposite": False,
    }


def _buckets(early: list[float] | None, late: list[float] | None) -> dict[str, Any]:
    """A minimal bucket table for ``_verdict``: one metric, CIs given for rounds 1-5 and 11+."""
    return {
        "1-5": {"n": 5 if early else 0, "m": {"ci95": early}},
        "11+": {"n": 5 if late else 0, "m": {"ci95": late}},
    }


def test_verdict_positive_early_ci_and_null_late_ci_declares_bias() -> None:
    verdict = _verdict(_buckets([1.0, 3.0], [-1.0, 1.0]), "m")
    assert verdict == {"early_bias_present": True, "early_shift_opposite": False}


def test_verdict_negative_early_ci_is_opposite_shift_not_bias() -> None:
    verdict = _verdict(_buckets([-3.0, -1.0], [-1.0, 1.0]), "m")
    assert verdict == {"early_bias_present": False, "early_shift_opposite": True}


def test_verdict_null_early_ci_declares_nothing() -> None:
    verdict = _verdict(_buckets([-1.0, 1.0], [-1.0, 1.0]), "m")
    assert verdict == {"early_bias_present": False, "early_shift_opposite": False}


def test_verdict_late_ci_excluding_zero_blocks_declaration() -> None:
    verdict = _verdict(_buckets([1.0, 3.0], [1.0, 2.0]), "m")
    assert verdict["early_bias_present"] is False


def test_verdict_empty_bucket_declares_nothing() -> None:
    verdict = _verdict(_buckets(None, [-1.0, 1.0]), "m")
    assert verdict == {"early_bias_present": False, "early_shift_opposite": False}


def test_excludes_zero() -> None:
    assert excludes_zero([0.1, 2.0])
    assert excludes_zero([-2.0, -0.1])
    assert not excludes_zero([-0.1, 2.0])
    assert not excludes_zero(None)
