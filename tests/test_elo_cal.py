"""Unit tests for the ELOC calibration fit (``models/elo_cal.py``): the logit identity, the
maximum-likelihood point, recovery of known parameters, the identity on calibrated Elo, a
synthetic miscalibrated probability being improved, and the input guards."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import expit

from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.models import elo
from eurohoops.models.elo_cal import apply, elo_logit, fit


def test_elo_logit_is_the_logit_of_the_elo_win_probability() -> None:
    diffs = np.array([-300.0, -90.0, 0.0, 45.0, 400.0])
    p = np.array([elo.win_probability(float(d)) for d in diffs])
    np.testing.assert_allclose(elo_logit(diffs), np.log(p / (1.0 - p)), rtol=1e-12, atol=1e-12)


def test_fit_recovers_known_parameters() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(0.0, 1.0, 40_000)
    y = (rng.random(40_000) < expit(0.3 + 0.6 * x)).astype(float)
    cal = fit(x, y)
    assert cal.a == pytest.approx(0.3, abs=0.03)
    assert cal.b == pytest.approx(0.6, abs=0.03)


def test_fit_is_a_stationary_point_of_the_likelihood() -> None:
    rng = np.random.default_rng(2)
    x = rng.normal(0.0, 0.8, 500)
    y = (rng.random(500) < expit(-0.2 + 1.3 * x)).astype(float)
    cal = fit(x, y)
    p = expit(cal.a + cal.b * x)
    assert abs(float(np.sum(y - p))) < 1e-6  # d/da of the log-likelihood
    assert abs(float(np.sum(x * (y - p)))) < 1e-6  # d/db


def test_calibrated_elo_is_left_near_the_identity() -> None:
    """When Elo is already calibrated, the fit returns (0, 1) up to sampling noise."""
    rng = np.random.default_rng(3)
    diffs = rng.normal(0.0, 150.0, 30_000)
    y = (rng.random(30_000) < expit(elo_logit(diffs))).astype(float)
    cal = fit(elo_logit(diffs), y)
    assert abs(cal.a) < 0.03
    assert cal.b == pytest.approx(1.0, abs=0.05)


def test_a_miscalibrated_probability_is_improved_out_of_sample() -> None:
    """Outcomes follow a truth that is less extreme than Elo's: Elo is overconfident, so a
    fitted slope shrinks it and the held-out log loss falls."""
    rng = np.random.default_rng(4)
    n = 6000
    diffs = rng.normal(0.0, 300.0, n)  # Elo's view: too sharp by a factor of 2.5
    truth = expit(elo_logit(diffs) / 2.5)
    y = (rng.random(n) < truth).astype(float)
    train, test = slice(0, 4000), slice(4000, n)
    cal = fit(elo_logit(diffs[train]), y[train])
    raw = per_game_log_loss(expit(elo_logit(diffs[test])), y[test]).mean()
    improved = per_game_log_loss(apply(cal, diffs[test]), y[test]).mean()
    assert cal.b == pytest.approx(0.4, abs=0.05)
    assert improved < raw


def test_apply_maps_zero_difference_to_the_intercept_sigmoid() -> None:
    rng = np.random.default_rng(5)
    diffs = rng.normal(0.0, 200.0, 500)
    y = (rng.random(500) < expit(elo_logit(diffs) + 0.2)).astype(float)
    cal = fit(elo_logit(diffs), y)
    assert apply(cal, np.array([0.0]))[0] == pytest.approx(expit(cal.a))


def test_a_perfectly_separable_sample_has_no_maximum_likelihood_point() -> None:
    with pytest.raises(ValueError, match="no maximum likelihood point"):
        fit(np.array([-1.0, -0.5, 0.5, 1.0]), np.array([0.0, 0.0, 1.0, 1.0]))


@pytest.mark.parametrize(
    ("x", "y", "match"),
    [
        (np.array([]), np.array([]), "non-empty"),
        (np.array([0.0, 1.0]), np.array([1.0]), "non-empty"),
        (np.array([0.0, np.nan]), np.array([0.0, 1.0]), "finite"),
        (np.array([0.0, 1.0, 2.0]), np.array([1.0, 1.0, 1.0]), "both home wins"),
    ],
)
def test_fit_refuses_bad_inputs(x: np.ndarray, y: np.ndarray, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        fit(x, y)
