"""POOL (docs/models/pool.md): pooling math, the all-four and logged-before-tip-off rules, the
write-once guard, the overlap audit, and the live gate (off by default)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops import config, live_pool
from eurohoops.eval import pool as eval_pool
from eurohoops.logs import append_rows
from eurohoops.models.pool import COMPONENTS, logit, pool_margin, pool_probabilities
from eurohoops.predict import LOG_COLUMNS

TIP = "2026-10-20T17:00:00Z"


# -- pooling math -------------------------------------------------------------------------------


def test_equal_weights_are_the_mean_log_odds() -> None:
    p = np.array([[0.6, 0.6, 0.6, 0.6]])
    assert pool_probabilities(p)[0] == pytest.approx(0.6)
    q = np.array([[0.2, 0.9, 0.5, 0.7]])
    expected = 1 / (1 + np.exp(-np.mean(logit(q[0]))))
    assert pool_probabilities(q)[0] == pytest.approx(expected)


def test_pool_is_symmetric_under_flipping_every_probability() -> None:
    rng = np.random.default_rng(1)
    p = rng.uniform(0.05, 0.95, size=(50, 4))
    assert np.allclose(pool_probabilities(1 - p), 1 - pool_probabilities(p))


def test_pool_is_invariant_to_component_order() -> None:
    p = np.array([[0.31, 0.62, 0.48, 0.77]])
    assert np.allclose(pool_probabilities(p), pool_probabilities(p[:, ::-1]))


def test_pool_is_strictly_inside_zero_one_at_the_extremes() -> None:
    extreme = np.array([[0.0, 1.0, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 0.0]])
    out = pool_probabilities(extreme)
    assert np.all(out > 0.0) and np.all(out < 1.0)
    assert out[0] == pytest.approx(0.5)  # two clipped 1s and two clipped 0s cancel
    assert out[1] > 0.999 and out[2] < 0.001


def test_clipping_bounds_the_logit_at_the_clip_level() -> None:
    assert logit(np.array([0.0]))[0] == pytest.approx(np.log(1e-6 / (1 - 1e-6)))
    assert logit(np.array([1.0]))[0] == pytest.approx(-np.log(1e-6 / (1 - 1e-6)))


def test_pool_rejects_bad_shapes_and_non_finite_input() -> None:
    with pytest.raises(ValueError, match="shape"):
        pool_probabilities(np.array([0.5, 0.5]))
    with pytest.raises(ValueError, match="shape"):
        pool_probabilities(np.empty((3, 0)))
    with pytest.raises(ValueError, match="non-finite"):
        pool_probabilities(np.array([[0.5, np.nan, 0.5, 0.5]]))
    with pytest.raises(ValueError, match="non-finite"):
        pool_margin(np.array([[1.0, np.inf]]))


def test_pool_margin_is_the_arithmetic_mean() -> None:
    assert pool_margin(np.array([[1.0, 2.0, 3.0, 6.0]]))[0] == pytest.approx(3.0)


# -- row construction ---------------------------------------------------------------------------


def _row(
    game_id: str,
    version: str,
    p: float,
    stamp: str,
    *,
    tip: str = TIP,
    home: str = "BAR",
    margin: float = 2.0,
) -> dict[str, str]:
    return {
        "game_id": game_id,
        "season": "2026",
        "round": "7",
        "phase": "RS",
        "tipoff_utc": tip,
        "home": home,
        "away": "MAD",
        "p_home": f"{p:.4f}",
        "exp_margin": f"{margin:.2f}",
        "model": "x",
        "model_version": version,
        "predicted_at_utc": stamp,
    }


def _components(rows_by_name: dict[str, list[dict[str, str]]]) -> dict[str, live_pool.Rows]:
    return {name: {r["game_id"]: r for r in rows_by_name.get(name, [])} for name in COMPONENTS}


def _all_four(game_id: str, stamp: str = "2026-10-19T10:00:00Z") -> dict[str, list[dict[str, str]]]:
    """One row per component, probabilities 0.5, 0.6, 0.7, 0.8 in COMPONENTS order."""
    return {
        name: [_row(game_id, f"v-{name}", 0.5 + 0.1 * i, stamp)]
        for i, name in enumerate(COMPONENTS)
    }


def test_only_games_all_four_components_logged_are_pooled() -> None:
    rows = _all_four("E1")
    rows["m5"] = []  # M5 missing for this game
    rows["elo"] += [_row("E2", "v-elo", 0.7, "2026-10-19T10:00:00Z")]
    rows["m1"] += [_row("E2", "v-m1", 0.6, "2026-10-19T10:00:00Z")]
    rows["m5"] += [_row("E2", "v-m5", 0.6, "2026-10-19T10:00:00Z")]
    rows["elor"] += [_row("E2", "v-elor", 0.6, "2026-10-19T10:00:00Z")]
    out, skipped = live_pool.pool_rows(_components(rows), set(), "pool-v")
    assert [r["game_id"] for r in out] == ["E2"]
    assert skipped == 0


def test_pool_row_is_stamped_with_the_latest_component_and_is_before_tipoff() -> None:
    rows = {
        "elo": [_row("E1", "v-elo", 0.5, "2026-10-19T10:00:00Z")],
        "m1": [_row("E1", "v-m1", 0.5, "2026-10-19T11:30:00Z")],
        "m5": [_row("E1", "v-m5", 0.5, "2026-10-19T10:45:00Z")],
        "elor": [_row("E1", "v-elor", 0.5, "2026-10-19T09:00:00Z")],
    }
    out, _ = live_pool.pool_rows(_components(rows), set(), "pool-v")
    assert out[0]["predicted_at_utc"] == "2026-10-19T11:30:00Z"
    assert out[0]["predicted_at_utc"] < out[0]["tipoff_utc"]


def test_a_component_stamped_at_or_after_tipoff_excludes_the_game() -> None:
    rows = _all_four("E1", stamp="2026-10-20T17:00:00Z")  # equal to tip-off: not before it
    out, skipped = live_pool.pool_rows(_components(rows), set(), "pool-v")
    assert out == [] and skipped == 1
    late = _all_four("E2", stamp="2026-10-20T18:00:00Z")
    out, skipped = live_pool.pool_rows(_components(late), set(), "pool-v")
    assert out == [] and skipped == 1


def test_disagreeing_fixtures_are_not_pooled() -> None:
    rows = _all_four("E1")
    rows["m1"] = [_row("E1", "v-m1", 0.5, "2026-10-19T10:00:00Z", home="MAD")]
    out, skipped = live_pool.pool_rows(_components(rows), set(), "pool-v")
    assert out == [] and skipped == 1


def test_already_logged_games_are_not_written_again() -> None:
    out, _ = live_pool.pool_rows(_components(_all_four("E1")), {("E1", "pool-v")}, "pool-v")
    assert out == []


def test_pooled_probability_matches_the_components_as_logged() -> None:
    out, _ = live_pool.pool_rows(_components(_all_four("E1")), set(), "pool-v")
    # components 0.5, 0.6, 0.7, 0.8 (the fixture helper's ramp)
    expected = pool_probabilities(np.array([[0.5, 0.6, 0.7, 0.8]]))[0]
    assert float(out[0]["p_home"]) == pytest.approx(round(expected, 4), abs=1e-4)


# -- files: append-only, versions, guard, gate ----------------------------------------------------


def _write_components(tmp_path: Path, rows_by_name: dict[str, list[dict[str, str]]]) -> dict:
    pins = {}
    for name in COMPONENTS:
        path = tmp_path / f"{name}.csv"
        append_rows(path, LOG_COLUMNS, rows_by_name.get(name, []))
        pins[name] = (path, f"v-{name}")
    return pins


def test_read_component_ignores_other_versions_and_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "elo.csv"
    append_rows(
        path,
        LOG_COLUMNS,
        [
            _row("E1", "v-elo", 0.5, "2026-10-19T10:00:00Z"),
            _row("E2", "0.1.0+old", 0.5, "2026-10-19T10:00:00Z"),
        ],
    )
    assert list(live_pool.read_component(path, "v-elo")) == ["E1"]
    assert live_pool.read_component(tmp_path / "absent.csv", "v-elo") == {}
    append_rows(path, LOG_COLUMNS, [_row("E1", "v-elo", 0.6, "2026-10-19T10:00:00Z")])
    with pytest.raises(ValueError, match="logged twice"):
        live_pool.read_component(path, "v-elo")


def test_live_is_disabled_by_default_and_writes_nothing(tmp_path: Path) -> None:
    assert config.POOL_LIVE_ENABLED is False
    rows = {name: _all_four("E1")[name] for name in COMPONENTS}
    pins = _write_components(tmp_path, rows)
    target = tmp_path / "pool.csv"
    assert live_pool.predict_pool(log_path=target, components=pins) == 0
    assert not target.exists()


def test_enabled_predict_pool_appends_once_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "POOL_LIVE_ENABLED", True)
    rows = _all_four("E1")
    pins = _write_components(tmp_path, rows)
    target = tmp_path / "pool.csv"
    assert live_pool.predict_pool(log_path=target, components=pins) == 1
    assert live_pool.predict_pool(log_path=target, components=pins) == 0
    written = pd.read_csv(target, dtype={"game_id": str})
    assert list(written.columns) == list(LOG_COLUMNS)
    assert written["model"].tolist() == ["pool"]
    assert written["model_version"].tolist() == [live_pool.pool_version()]


def test_pool_version_is_tagged_and_depends_on_the_pins() -> None:
    version = live_pool.pool_version()
    assert "+pool." in version
    assert version == live_pool.pool_version()


def test_live_comparison_report_is_written_once(tmp_path: Path) -> None:
    target = tmp_path / "pool_live.json"
    payload = {"games": 0}
    eval_pool.write_live_comparison(target, payload)
    with pytest.raises(eval_pool.PoolEvalAlreadyWrittenError):
        eval_pool.write_live_comparison(target, payload)


def test_live_comparison_is_paired_and_reports_the_shadow_form() -> None:
    rng = np.random.default_rng(7)
    y = rng.integers(0, 2, size=400).astype(float)
    p_elo = np.clip(0.5 + 0.1 * (y - 0.5) + rng.normal(0, 0.1, 400), 0.05, 0.95)
    same = eval_pool.live_comparison(p_elo, p_elo, y)
    assert same["mean"] == 0.0 and same["shadow_criterion_met"] is False
    empty = eval_pool.live_comparison(np.array([]), np.array([]), np.array([]))
    assert empty["games"] == 0
    with pytest.raises(ValueError, match="same games"):
        eval_pool.live_comparison(p_elo, p_elo[:-1], y)


# -- overlap audit ------------------------------------------------------------------------------


def _frame(seasons: list[int], *, present: bool = True) -> pd.DataFrame:
    n = len(seasons)
    data = {"game_id": [f"G{i}" for i in range(n)], "season": seasons, "home_won": [1] * n}
    for name in COMPONENTS:
        data[f"p_{name}"] = [0.5] * n if present else [np.nan] * n
    return pd.DataFrame(data)


def test_overlap_audit_finds_no_clean_game_when_every_season_is_seen() -> None:
    report = eval_pool.overlap_report(_frame([2015, 2020, 2023]))
    assert report["all_four"]["games"] == 3
    assert report["clean_games"] == 0 and report["clean_seasons"] == []
    assert report["pairs"]["elo+m1"]["games"] == 3
    assert "clean out-of-sample common games: 0 (none)" in eval_pool.format_overlap(report)


def test_overlap_audit_counts_a_clean_season_and_skips_missing_components() -> None:
    frame = pd.concat([_frame([2026, 2026]), _frame([2026], present=False)], ignore_index=True)
    report = eval_pool.overlap_report(frame)
    assert report["clean_games"] == 2 and report["clean_seasons"] == [2026]
    assert report["all_four"]["games"] == 2
    assert "(seasons [2026])" in eval_pool.format_overlap(report)


def test_load_components_joins_the_committed_report_shapes(tmp_path: Path) -> None:
    m5 = tmp_path / "m5.csv"
    m5.write_text(
        "game_id,season,split,model,variant,p_home,actual_margin\n"
        "E1,2023,validation,elo,elo,0.6,4\n"
        "E1,2023,validation,m1,student_t_const,0.61,4\n"
        "E1,2023,validation,m5,proj_hc|core|d180|r40,0.62,4\n"
        "E1,2023,validation,m5_oracle,proj_hc|core|d180|r40,0.99,4\n",
        encoding="utf-8",
    )
    cv = tmp_path / "cv.csv"
    cv.write_text("game_id,season,home_won,p_w0.5|n24\nE1,2023,1,0.63\n", encoding="utf-8")
    frame = eval_pool.load_components(m5, cv, "w0.5|n24")
    row = frame.iloc[0]
    assert row["p_m5"] == pytest.approx(0.62)  # the oracle row is not picked
    assert row["p_elor"] == pytest.approx(0.63)
    assert bool(row["home_won"]) is True
    empty = eval_pool.load_components(tmp_path / "none.csv", cv, "w0.5|n24")
    assert empty.empty
