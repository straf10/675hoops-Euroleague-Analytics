"""POOL-c (docs/models/pool_c.md, draft): the c transform, the bounded fit and the paired gap.

The rows are synthetic and seeded here; nothing reads predictions/ or odds/.
"""

import numpy as np
import pytest

from eurohoops.eval.pool_c import C_BOUNDS, apply_c, fit_c, mean_log_loss, paired_gap
from eurohoops.models.pool import PROB_CLIP


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
