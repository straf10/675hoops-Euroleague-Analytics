"""Equal-weight logarithmic opinion pool of the four live EuroLeague forecasters (POOL).

    P_pool = sigmoid( mean_k logit(clip(P_k)) )  with fixed weights 1 / K

Nothing here is tuned (docs/models/pool.md): the weights are equal, the clip level is fixed, and
the components are the pinned live models. The pool is symmetric under flipping every
probability, and every output lies strictly inside (0, 1).
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

PROB_CLIP = 1e-6  # components are clipped to [PROB_CLIP, 1 - PROB_CLIP] before the logit
COMPONENTS = ("elo", "m1", "m5", "elor")  # the order of the pool's columns


def logit(p: FloatArray) -> FloatArray:
    """Log-odds of ``p`` after clipping to [PROB_CLIP, 1 - PROB_CLIP]."""
    clipped = np.clip(np.asarray(p, dtype=np.float64), PROB_CLIP, 1.0 - PROB_CLIP)
    return np.asarray(np.log(clipped / (1.0 - clipped)), dtype=np.float64)


def pool_probabilities(p: Sequence[Sequence[float]] | FloatArray) -> FloatArray:
    """Pooled home-win probabilities of a ``(games, components)`` array of component P(home).

    Equal weights: each component's log-odds counts 1/K. Rejects non-finite input and an empty
    component axis, so a missing forecast can never reach the log as a silent NaN.
    """
    arr = np.asarray(p, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] == 0:
        raise ValueError(f"expected a (games, components) array, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("pool input has a non-finite component probability")
    z = logit(arr).mean(axis=1)
    return np.asarray(1.0 / (1.0 + np.exp(-z)), dtype=np.float64)


def pool_margin(margins: Sequence[Sequence[float]] | FloatArray) -> FloatArray:
    """Equal-weight arithmetic mean of ``(games, components)`` expected margins (display only)."""
    arr = np.asarray(margins, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] == 0:
        raise ValueError(f"expected a (games, components) array, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("pool input has a non-finite component margin")
    return np.asarray(arr.mean(axis=1), dtype=np.float64)
