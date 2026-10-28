"""POOL3 screen (experiments/pool3.md): member selection, the game set, the Elo-ELOR rule and the
two matrices. Fixtures in tests/fixtures/pool3/ (games G1-G7, four member logs)."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval.pool3 import (
    MEMBERS,
    RULE_THRESHOLD,
    SPEC_COMMITTED_AT,
    finished_games,
    member_rows,
    screen,
)
from eurohoops.eval.scorecard import read_log
from eurohoops.models.pool import logit

FIXTURES = Path(__file__).parent / "fixtures" / "pool3"
ELO_V = "0.2.0+425e6393"
ELOR_V = "0.2.0+elor.59b43f20"
M1_V = "0.2.0+m1.cbd9aaa3"
M5_V = "0.2.0+m5.d4848a7e"
VERSIONS = {"elo": ELO_V, "elor": ELOR_V, "m1": M1_V, "m5": M5_V}


def _members() -> dict[str, pd.DataFrame]:
    return {
        name: member_rows(read_log(FIXTURES / f"{name}.csv"), VERSIONS[name]) for name in MEMBERS
    }


def _games() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "games.csv", dtype={"game_id": str})


def _frame(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": pd.Series([g for g, _ in rows], dtype=object),
            "p_home": pd.Series([p for _, p in rows], dtype=float),
        }
    )


def test_member_rows_pick_pinned_version_and_latest_row_before_tip_off() -> None:
    elo = member_rows(read_log(FIXTURES / "elo.csv"), ELO_V).set_index("game_id")["p_home"]
    assert set(elo.index) == {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    assert elo["G1"] == pytest.approx(0.70)  # the 0.1.0 row is another version
    assert elo["G2"] == pytest.approx(0.40)  # the 18:00 row is stamped after tip-off
    assert elo["G3"] == pytest.approx(0.60)  # the later of two valid stamps


def test_member_rows_hide_rows_public_only_after_tip_off() -> None:
    log = pd.DataFrame(
        {
            "game_id": ["G1"],
            "tipoff_utc": ["2026-10-10T17:00:00Z"],
            "p_home": [0.6],
            "model_version": [ELO_V],
            "predicted_at_utc": ["2026-10-10T10:00:00Z"],
        }
    )
    assert member_rows(log, ELO_V, manual_pushes=[]).shape[0] == 1
    late_push = [datetime(2026, 10, 10, 18, 0, tzinfo=UTC)]
    assert member_rows(log, ELO_V, manual_pushes=late_push).empty


def test_finished_games_drop_forfeits_unplayed_and_late_tip_offs() -> None:
    kept = finished_games(_games(), SPEC_COMMITTED_AT, 2026)
    assert kept["game_id"].tolist() == ["G1", "G2", "G3", "G7"]


def test_screen_uses_only_games_every_member_logged() -> None:
    report = screen(_members(), _games())
    assert report["n_games"] == 3  # G7 has no ELOR or M5 row; G4 forfeit; G5 after the cutoff
    assert report["games"] == ["G1", "G2", "G3"]
    assert report["pair_elo_elor"]["n_games"] == 3
    assert report["cutoff_utc"] == "2026-10-28T09:49:14Z"


def test_rule_is_the_pearson_correlation_of_the_logits() -> None:
    elo = np.array([0.70, 0.40, 0.60])
    elor = np.array([0.72, 0.38, 0.58])
    expected = float(np.corrcoef(logit(elo), logit(elor))[0, 1])
    report = screen(_members(), _games())
    assert report["rule"]["value"] == pytest.approx(expected)
    assert report["rule"]["threshold"] == RULE_THRESHOLD
    assert report["rule"]["declared"] is (expected > RULE_THRESHOLD)


def test_identical_members_declare_the_rule_and_correlate_perfectly() -> None:
    members = {name: _frame([("G1", 0.7), ("G2", 0.4), ("G3", 0.6)]) for name in MEMBERS}
    report = screen(members, _games())
    assert report["rule"]["value"] == pytest.approx(1.0)
    assert report["rule"]["declared"] is True
    assert report["corr_logit"]["m1"]["m5"] == pytest.approx(1.0)


def test_log_loss_values_and_matrices() -> None:
    report = screen(_members(), _games())
    # Elo's per-game log loss: G1 home won at 0.70, G2 away won at 0.40, G3 home won at 0.60.
    expected = -(np.log(0.70) + np.log(0.60) + np.log(0.60)) / 3
    assert report["mean_log_loss"]["elo"] == pytest.approx(expected)
    matrix = report["corr_log_loss"]
    assert set(matrix) == set(MEMBERS)
    for name in MEMBERS:
        assert matrix[name][name] == pytest.approx(1.0)
        for other in MEMBERS:
            assert matrix[name][other] == pytest.approx(matrix[other][name])
    assert len(report["per_game"]) == 3
    assert report["per_game"][0]["log_loss"]["elo"] == pytest.approx(-np.log(0.70))


def test_no_common_games_gives_no_rule_value() -> None:
    members = {name: _frame([]) for name in MEMBERS}
    report = screen(members, _games())
    assert report["n_games"] == 0
    assert report["rule"]["value"] is None
    assert report["rule"]["declared"] is False
    assert report["mean_log_loss"] == {}
