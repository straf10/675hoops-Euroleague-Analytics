"""POOL-c (docs/models/pool_c.md, draft): the equal-weight pool with its logit scaled by one c.

    P_c = sigmoid( c * z_pool ),   z_pool = logit(P_pool)  (the logit POOL already computes)

``c`` is fitted by log loss on POOL's scored rows for rounds 1-19 and then frozen. The fit and the
gate's paired bootstrap are pure functions of the arrays they are given: which rows go in (the
rounds, the scored row before tip-off) is the caller's choice, set by the gate. Nothing here reads
the logs.

Probabilities are clipped to the pool's clip level before any log loss, so a logged 0.0000 or
1.0000 cannot make the loss infinite.
"""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit

from eurohoops.eval.metrics import paired_bootstrap_ci, per_game_log_loss
from eurohoops.models.elo import FloatArray
from eurohoops.models.pool import PROB_CLIP, logit

C_BOUNDS = (0.0, 5.0)  # the search interval for c; a bounded, deterministic 1-D minimisation
GATE_RESAMPLES = 10_000
GATE_SEED = 20261022  # the date the gate was drafted


def _clip(p: FloatArray) -> FloatArray:
    return np.clip(p, PROB_CLIP, 1.0 - PROB_CLIP)


def _checked(pool_p: FloatArray, home_won: FloatArray) -> tuple[FloatArray, FloatArray]:
    p = np.asarray(pool_p, dtype=np.float64)
    y = np.asarray(home_won, dtype=np.float64)
    if p.ndim != 1 or p.shape != y.shape or not len(p):
        raise ValueError("pool_p and home_won must be non-empty 1-D arrays of one length")
    if not np.all((p > 0.0) & (p < 1.0)):
        raise ValueError("POOL probabilities must lie strictly inside (0, 1)")
    if not np.all((y == 0.0) | (y == 1.0)):
        raise ValueError("home_won must be 0 or 1")
    return p, y


def apply_c(pool_p: FloatArray, c: float) -> FloatArray:
    """POOL-c home-win probabilities: sigmoid(c * logit(P_pool)), clipped to the pool's level."""
    z = c * logit(np.asarray(pool_p, dtype=np.float64))
    return _clip(expit(z))


def mean_log_loss(pool_p: FloatArray, home_won: FloatArray, c: float) -> float:
    """Mean per-game log loss of POOL-c on the given rows."""
    p, y = _checked(pool_p, home_won)
    return float(per_game_log_loss(apply_c(p, c), y).mean())


def fit_c(pool_p: FloatArray, home_won: FloatArray) -> float:
    """The c in ``C_BOUNDS`` that minimises the mean log loss of POOL-c on the given rows.

    Bounded Brent search: deterministic, and the same rows always give the same c. The loss is
    convex in c until the clip binds, so the search finds the minimum.
    """
    p, y = _checked(pool_p, home_won)
    result = minimize_scalar(
        lambda c: mean_log_loss(p, y, float(c)),
        bounds=C_BOUNDS,
        method="bounded",
        options={"xatol": 1e-8},
    )
    if not result.success:
        raise RuntimeError(f"c fit did not converge: {result.message}")
    return float(result.x)


def paired_gap(
    pool_p: FloatArray,
    home_won: FloatArray,
    c: float,
    *,
    resamples: int = GATE_RESAMPLES,
    seed: int = GATE_SEED,
) -> dict[str, float | int | bool]:
    """Paired bootstrap of (POOL-c minus POOL) per-game log loss on the given rows.

    The 95% CI is the percentile interval of the mean over ``resamples`` paired resamples drawn
    with ``seed`` (``eval.metrics.paired_bootstrap_ci``). ``pass`` is the draft gate's rule: the
    CI upper bound is below zero.
    """
    p, y = _checked(pool_p, home_won)
    base = per_game_log_loss(_clip(p), y)
    scaled = per_game_log_loss(apply_c(p, c), y)
    mean, low, high = paired_bootstrap_ci(scaled - base, resamples, seed)
    return {
        "n": len(p),
        "c": float(c),
        "mean_diff": round(mean, 6),
        "ci_lo": round(low, 6),
        "ci_hi": round(high, 6),
        "resamples": resamples,
        "seed": seed,
        "pass": bool(high < 0.0),
    }
