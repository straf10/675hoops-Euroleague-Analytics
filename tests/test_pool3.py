"""POOL3 (experiments/pool3.md, docs/models/pool3.md): the screen's member selection, game set,
Elo-ELOR rule and matrices (fixtures in tests/fixtures/pool3/), and the live shadow's pooling,
gate, files and no-lookahead rule."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops import config, live_pool
from eurohoops.eval.pool3 import (
    MEMBERS,
    RULE_THRESHOLD,
    SPEC_COMMITTED_AT,
    finished_games,
    member_rows,
    screen,
)
from eurohoops.eval.scorecard import read_log
from eurohoops.logs import append_rows
from eurohoops.models.pool import logit, pool_probabilities
from eurohoops.predict import LOG_COLUMNS

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


# -- POOL3 live shadow (docs/models/pool3.md): the POOL code path over ELOR, M1 and M5 -----------

LIVE_NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)  # the write time: before TIP, after stamps
TIP = "2026-10-20T17:00:00Z"
MEMBERS3 = ("elor", "m1", "m5")
PROBS3 = {"elor": 0.6, "m1": 0.7, "m5": 0.8}


def _live_row(
    game_id: str, version: str, p: float, stamp: str, *, tip: str = TIP
) -> dict[str, str]:
    return {
        "game_id": game_id,
        "season": "2026",
        "round": "7",
        "phase": "RS",
        "tipoff_utc": tip,
        "home": "BAR",
        "away": "MAD",
        "p_home": f"{p:.4f}",
        "exp_margin": "2.00",
        "model": "x",
        "model_version": version,
        "predicted_at_utc": stamp,
    }


def _game(
    game_id: str, stamp: str, probs: dict[str, float], tip: str = TIP
) -> dict[str, list[dict[str, str]]]:
    return {name: [_live_row(game_id, f"v-{name}", p, stamp, tip=tip)] for name, p in probs.items()}


def _merge(*parts: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    merged: dict[str, list[dict[str, str]]] = {}
    for part in parts:
        for name, rows in part.items():
            merged.setdefault(name, []).extend(rows)
    return merged


def _components(rows_by_name: dict[str, list[dict[str, str]]]) -> dict[str, live_pool.Rows]:
    return {name: {r["game_id"]: r for r in rows_by_name.get(name, [])} for name in MEMBERS3}


def _pins(tmp_path: Path, rows_by_name: dict[str, list[dict[str, str]]]) -> dict:
    pins = {}
    for name in MEMBERS3:
        path = tmp_path / f"{name}.csv"
        append_rows(path, LOG_COLUMNS, rows_by_name.get(name, []))
        pins[name] = (path, f"v-{name}")
    return pins


def test_pool3_is_declared_live_on_elor_m1_m5_with_its_own_log() -> None:
    assert config.POOL3_LIVE_ENABLED is True
    assert config.POOL3_MEMBERS == ("elor", "m1", "m5")
    assert config.EUROLEAGUE.pool3_prediction_log == Path(
        "predictions/euroleague_pool3_2026-27.csv"
    )


def test_pool3_is_the_equal_weight_pool_of_its_three_members_and_not_elo() -> None:
    rows = _game("E1", "2026-10-19T10:00:00Z", {**PROBS3, "elo": 0.9})
    out, skipped, _ = live_pool.pool_rows(
        _components(rows), set(), "v-pool3", LIVE_NOW, members=MEMBERS3, model="pool3"
    )
    expected = pool_probabilities(np.array([[0.6, 0.7, 0.8]]))[0]
    assert skipped == 0 and len(out) == 1
    assert float(out[0]["p_home"]) == pytest.approx(round(expected, 4), abs=1e-4)
    assert out[0]["model"] == "pool3"


def test_pool3_needs_all_three_members() -> None:
    rows = _game("E1", "2026-10-19T10:00:00Z", {"elor": 0.6, "m1": 0.7, "elo": 0.9})
    out, _, _ = live_pool.pool_rows(
        _components(rows), set(), "v-pool3", LIVE_NOW, members=MEMBERS3, model="pool3"
    )
    assert out == []  # no M5 row: the game is not pooled


def test_pool3_component_stamped_at_or_after_tipoff_excludes_the_game() -> None:
    rows = _merge(
        _game("E1", "2026-10-19T10:00:00Z", {"elor": 0.6, "m1": 0.7}),
        _game("E1", TIP, {"m5": 0.8}),  # M5 stamped exactly at tip-off
    )
    out, skipped, _ = live_pool.pool_rows(
        _components(rows), set(), "v-pool3", LIVE_NOW, members=MEMBERS3, model="pool3"
    )
    assert out == [] and skipped == 1


def test_pool3_version_is_tagged_pool3_and_depends_on_its_members() -> None:
    version = live_pool.pool_version(MEMBERS3, "pool3")
    assert "+pool3." in version
    assert version != live_pool.pool_version()


def test_pool3_disabled_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "POOL3_LIVE_ENABLED", False)
    pins = _pins(tmp_path, _game("E1", "2026-10-19T10:00:00Z", PROBS3))
    target = tmp_path / "pool3.csv"
    assert live_pool.predict_pool3(log_path=target, components=pins, clock=lambda: LIVE_NOW) == 0
    assert not target.exists()


def test_pool3_enabled_appends_once_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "POOL3_LIVE_ENABLED", True)
    pins = _pins(tmp_path, _game("E1", "2026-10-19T10:00:00Z", PROBS3))
    target = tmp_path / "pool3.csv"

    def run() -> int:
        return live_pool.predict_pool3(log_path=target, components=pins, clock=lambda: LIVE_NOW)

    assert run() == 1
    assert run() == 0
    written = pd.read_csv(target, dtype={"game_id": str})
    assert list(written.columns) == list(LOG_COLUMNS)
    assert written["model"].tolist() == ["pool3"]
    assert written["model_version"].tolist() == [live_pool.pool_version(MEMBERS3, "pool3")]


def test_pool3_no_lookahead_a_later_game_changes_no_earlier_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "POOL3_LIVE_ENABLED", True)
    early = _game("E1", "2026-10-19T10:00:00Z", PROBS3)
    pins = _pins(tmp_path, early)
    target = tmp_path / "pool3.csv"
    assert live_pool.predict_pool3(log_path=target, components=pins, clock=lambda: LIVE_NOW) == 1
    before = target.read_bytes()
    alone, _, _ = live_pool.pool_rows(
        _components(early), set(), "v-pool3", LIVE_NOW, members=MEMBERS3, model="pool3"
    )

    # E2 (tip-off 2026-10-24) is logged by all three members later, with extreme probabilities.
    later = _game(
        "E2", "2026-10-22T10:00:00Z", {"elor": 0.99, "m1": 0.01, "m5": 0.95}, "2026-10-24T17:00:00Z"
    )
    both, _, _ = live_pool.pool_rows(
        _components(_merge(early, later)),
        set(),
        "v-pool3",
        LIVE_NOW,
        members=MEMBERS3,
        model="pool3",
    )
    assert [r for r in both if r["game_id"] == "E1"] == alone

    for name in MEMBERS3:
        append_rows(pins[name][0], LOG_COLUMNS, later[name])
    clock = datetime(2026, 10, 22, 12, tzinfo=UTC)
    assert live_pool.predict_pool3(log_path=target, components=pins, clock=lambda: clock) == 1
    assert target.read_bytes().startswith(before)  # the earlier row is untouched on disk
