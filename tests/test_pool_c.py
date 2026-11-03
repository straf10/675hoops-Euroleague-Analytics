"""POOL-c (docs/models/pool_c.md): the c transform, the bounded fit, the paired gap and the two
stages (fit refuses before round 19, freezes c; eval scores rounds 20 on).

The transform tests use synthetic seeded rows. The stage tests use the small fixtures in
tests/fixtures/pool_c/ (a games mart extract and POOL's log); nothing reads predictions/ or odds/.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval.pool_c import (
    C_BOUNDS,
    GATE_SEED,
    StageRefused,
    apply_c,
    fit_c,
    mean_log_loss,
    paired_gap,
    rows_sha256,
    run_eval,
    run_fit,
    scored_games,
    split_fit_eval,
)
from eurohoops.eval.scorecard import read_log
from eurohoops.models.pool import PROB_CLIP

FIXTURES = Path(__file__).parent / "fixtures" / "pool_c"
SEASON = 2026
NO_PUSHES = ()  # the fixture rows are stamped two days before tip-off


def _league(n: int, true_c: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Pool probabilities whose logit is ``z``, and outcomes drawn from sigmoid(true_c * z)."""
    rng = np.random.default_rng(seed)
    z = rng.normal(0.0, 1.0, n)
    p_pool = 1.0 / (1.0 + np.exp(-z))
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-true_c * z))).astype(np.float64)
    return p_pool, y


def test_c_of_one_is_the_pool_and_zero_is_a_coin() -> None:
    p = np.array([0.1, 0.35, 0.5, 0.8, 0.97])
    np.testing.assert_allclose(apply_c(p, 1.0), p, atol=1e-12)
    np.testing.assert_allclose(apply_c(p, 0.0), np.full(5, 0.5))


def test_apply_c_is_symmetric_and_clipped() -> None:
    p = np.array([0.02, 0.3, 0.66, 0.9])
    for c in (0.4, 1.0, 2.5):
        np.testing.assert_allclose(apply_c(1.0 - p, c), 1.0 - apply_c(p, c), atol=1e-12)
    out = apply_c(np.array([1e-4, 0.9999]), 100.0)
    assert out.min() >= PROB_CLIP
    assert out.max() <= 1.0 - PROB_CLIP


def test_fit_recovers_an_overconfident_pool_and_is_deterministic() -> None:
    p, y = _league(20_000, true_c=0.6, seed=1)
    c = fit_c(p, y)
    assert c == pytest.approx(0.6, abs=0.03)
    assert fit_c(p, y) == c
    assert C_BOUNDS[0] <= c <= C_BOUNDS[1]
    assert mean_log_loss(p, y, c) <= mean_log_loss(p, y, 1.0)


def test_fit_is_near_one_for_a_calibrated_pool() -> None:
    p, y = _league(20_000, true_c=1.0, seed=2)
    assert fit_c(p, y) == pytest.approx(1.0, abs=0.05)


def test_paired_gap_passes_only_when_the_fitted_c_helps_out_of_sample() -> None:
    p_fit, y_fit = _league(20_000, true_c=0.6, seed=3)
    c = fit_c(p_fit, y_fit)
    p_eval, y_eval = _league(4_000, true_c=0.6, seed=4)
    good = paired_gap(p_eval, y_eval, c, resamples=2_000)
    assert good["pass"] is True
    assert good["ci_hi"] < 0.0
    assert good["mean_diff"] < 0.0
    assert good["n"] == 4_000

    calibrated_p, calibrated_y = _league(4_000, true_c=1.0, seed=5)
    flat = paired_gap(calibrated_p, calibrated_y, 1.0, resamples=2_000)
    assert flat["mean_diff"] == 0.0
    assert flat["pass"] is False


def test_paired_gap_is_reproducible_from_its_seed() -> None:
    p, y = _league(300, true_c=0.6, seed=6)
    first = paired_gap(p, y, 0.8, resamples=500, seed=7)
    assert first == paired_gap(p, y, 0.8, resamples=500, seed=7)
    assert first["resamples"] == 500
    assert first["seed"] == 7


def test_rows_are_validated() -> None:
    p, y = _league(10, true_c=1.0, seed=8)
    with pytest.raises(ValueError, match="one length"):
        fit_c(p, y[:5])
    with pytest.raises(ValueError, match="inside"):
        mean_log_loss(np.array([0.0, 0.5]), np.array([0.0, 1.0]), 1.0)
    with pytest.raises(ValueError, match="0 or 1"):
        paired_gap(p, np.full(10, 0.5), 1.0, resamples=10)


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The fixture games (rounds 1-19 played, round 21 not, one playoff game) and POOL's log."""
    games = pd.read_csv(FIXTURES / "games.csv", dtype={"game_id": str})
    return read_log(FIXTURES / "pool_log.csv"), games


def test_fit_refuses_until_every_round_1_to_19_game_is_played(tmp_path: Path) -> None:
    log, games = _inputs()
    games.loc[games["game_id"] == "F19", "played"] = False
    out = tmp_path / "pool_c_fit.json"
    with pytest.raises(StageRefused, match="1 of 19 regular-season games of rounds 1-19"):
        run_fit(log, games, SEASON, NO_PUSHES, out)
    assert not out.exists()


def test_fit_uses_only_rounds_1_to_19_and_freezes_c(tmp_path: Path) -> None:
    log, games = _inputs()
    out = tmp_path / "pool_c_fit.json"
    payload = run_fit(log, games, SEASON, NO_PUSHES, out)
    assert payload["stage"] == "fit"
    assert payload["n_games"] == 15  # POOL's rows for rounds 5-19; rounds 1-4 are not logged
    assert (payload["first_round"], payload["last_round"]) == (5, 19)
    assert payload["scheduled_games"] == 19
    assert C_BOUNDS[0] <= payload["c"] <= C_BOUNDS[1]
    assert json.loads(out.read_text(encoding="utf-8")) == payload


def test_split_puts_rounds_1_to_19_in_the_fit_and_the_rest_in_the_evaluation() -> None:
    log, games = _inputs()
    fit, evaluation = split_fit_eval(scored_games(log, games, SEASON, NO_PUSHES))
    assert set(fit["round"]) <= set(range(1, 20))
    assert set(fit["phase"]) == {"RS"}
    assert set(evaluation["game_id"]) == {"E20", "P01"}  # E21 is logged but not played: unscored
    assert not set(fit["game_id"]) & set(evaluation["game_id"])


def test_frozen_fit_is_not_overwritten_without_force(tmp_path: Path) -> None:
    log, games = _inputs()
    out = tmp_path / "pool_c_fit.json"
    first = run_fit(log, games, SEASON, NO_PUSHES, out)
    before = out.read_text(encoding="utf-8")
    with pytest.raises(StageRefused, match="frozen"):
        run_fit(log, games, SEASON, NO_PUSHES, out)
    assert out.read_text(encoding="utf-8") == before
    assert run_fit(log, games, SEASON, NO_PUSHES, out, force=True)["c"] == first["c"]


def test_later_games_do_not_change_the_fit(tmp_path: Path) -> None:
    log, games = _inputs()
    before = run_fit(log, games, SEASON, NO_PUSHES, tmp_path / "a.json")
    # round 21 is played and round 20's logged probability changes: neither is in the fit set
    later_games = games.copy()
    later_games.loc[later_games["game_id"] == "E21", ["played", "home_score", "away_score"]] = [
        True,
        80,
        77,
    ]
    later_log = log.copy()
    later_log.loc[later_log["game_id"] == "E20", "p_home"] = 0.99
    after = run_fit(later_log, later_games, SEASON, NO_PUSHES, tmp_path / "b.json")
    assert after["c"] == before["c"]
    assert after["fit_rows_sha256"] == before["fit_rows_sha256"]


def test_eval_scores_rounds_after_the_fit_with_the_frozen_c(tmp_path: Path) -> None:
    log, games = _inputs()
    fit_path = tmp_path / "pool_c_fit.json"
    run_fit(log, games, SEASON, NO_PUSHES, fit_path)
    out = tmp_path / "diag_pool_c.json"
    payload = run_eval(log, games, SEASON, NO_PUSHES, fit_path, out)
    assert set(payload) == {
        "stage",
        "season",
        "rule",
        "c",
        "fit_rows_sha256",
        "first_round",
        "last_round",
        "n",
        "mean_diff",
        "ci_lo",
        "ci_hi",
        "resamples",
        "seed",
        "pass",
    }
    assert payload["n"] == 2
    assert (payload["first_round"], payload["last_round"]) == (20, 20)
    assert payload["c"] == json.loads(fit_path.read_text(encoding="utf-8"))["c"]
    assert payload["seed"] == GATE_SEED
    assert payload["resamples"] == 10_000
    assert payload["ci_lo"] <= payload["mean_diff"] <= payload["ci_hi"]
    assert json.loads(out.read_text(encoding="utf-8")) == payload


def test_eval_reports_zero_games_before_any_is_played(tmp_path: Path) -> None:
    log, games = _inputs()
    fit_path = tmp_path / "pool_c_fit.json"
    run_fit(log, games, SEASON, NO_PUSHES, fit_path)
    games.loc[games["phase"] != "RS", "played"] = False
    games.loc[games["game_id"] == "E20", "played"] = False
    payload = run_eval(log, games, SEASON, NO_PUSHES, fit_path, tmp_path / "diag.json")
    assert payload["n"] == 0
    assert payload["pass"] is False
    assert payload["mean_diff"] is None


def test_eval_needs_the_frozen_fit_and_the_same_fit_rows(tmp_path: Path) -> None:
    log, games = _inputs()
    fit_path = tmp_path / "pool_c_fit.json"
    with pytest.raises(StageRefused, match="run the fit stage first"):
        run_eval(log, games, SEASON, NO_PUSHES, fit_path, tmp_path / "diag.json")
    run_fit(log, games, SEASON, NO_PUSHES, fit_path)
    changed = games.copy()
    changed.loc[changed["game_id"] == "F10", ["home_score", "away_score"]] = [70, 84]
    with pytest.raises(StageRefused, match="fit rows differ"):
        run_eval(log, changed, SEASON, NO_PUSHES, fit_path, tmp_path / "diag.json")
    fit, _ = split_fit_eval(scored_games(log, games, SEASON, NO_PUSHES))
    frozen = json.loads(fit_path.read_text(encoding="utf-8"))
    assert rows_sha256(fit) == frozen["fit_rows_sha256"]
