"""Logistic recalibration of Elo (ELOC, docs/models/elo_calibrated.md).

The calibrated probability is ``p = sigmoid(a + b * logit(p_elo))``.

Elo's win probability is logistic in the rating difference, ``1 / (1 + 10^(-d/400))``, so its logit
is exactly ``d * ln(10) / 400``. The fit is an unpenalised maximum-likelihood logistic regression
of the home-win outcome on that logit. There is no grid and no regularisation: the protocol tunes
nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.special import expit

from eurohoops.models.elo import FloatArray

ELO_LOGIT_SCALE = math.log(10.0) / 400.0


@dataclass(frozen=True)
class Calibration:
    a: float  # intercept: absorbs an average home-win bias
    b: float  # slope: 1 is Elo's own spread, below 1 shrinks it, above 1 widens it
    n: int  # games in the fit
    iterations: int  # Newton steps taken


def elo_logit(diff: FloatArray) -> FloatArray:
    """``logit(p_elo)`` for Elo rating differences (home-court advantage included)."""
    out: FloatArray = np.asarray(diff, dtype=np.float64) * ELO_LOGIT_SCALE
    return out


def fit(x: FloatArray, y: FloatArray, *, max_iter: int = 50, tol: float = 1e-10) -> Calibration:
    """Maximum-likelihood ``(a, b)`` of ``P(y = 1) = sigmoid(a + b * x)``, by Newton's method.

    Starts at the identity ``(0, 1)``, which is raw Elo. Raises ValueError for empty or
    mismatched inputs, non-finite ``x``, a single outcome class, or no convergence.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 1 or x.shape != y.shape or len(x) == 0:
        raise ValueError("calibration needs one non-empty x and y of the same length")
    if not np.all(np.isfinite(x)):
        raise ValueError("calibration inputs must be finite")
    if y.min() == y.max():
        raise ValueError("calibration needs both home wins and home losses")
    design = np.column_stack([np.ones_like(x), x])
    beta = np.array([0.0, 1.0])
    for step_no in range(1, max_iter + 1):
        p = expit(design @ beta)
        grad = design.T @ (y - p)
        hess = (design * (p * (1.0 - p))[:, None]).T @ design
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError as error:  # perfectly separable or constant x: no MLE
            raise ValueError("calibration has no maximum likelihood point") from error
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            return Calibration(float(beta[0]), float(beta[1]), len(x), step_no)
    raise ValueError(f"calibration fit did not converge in {max_iter} Newton steps")


def apply(cal: Calibration, diff: FloatArray) -> FloatArray:
    """Calibrated P(home win) for Elo rating differences."""
    out: FloatArray = expit(cal.a + cal.b * elo_logit(diff))
    return out
