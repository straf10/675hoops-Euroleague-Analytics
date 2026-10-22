"""Power of the R1 promotion looks (PLAN §8.1 R1; research idea E1). Reporting only.

Nothing here decides a promotion and nothing feeds ``promotion.promote``. For a true per-game
log-loss gap, the module answers two questions about the rule in ``promotion.py``: how often
the two-sided 97.5% paired-bootstrap CI of the mean gap lies below 0 while the mean is at most
``MIN_GAP``, at each look, in a normal approximation (``normal_promote_prob``) and by simulation
(``simulate_promotion``).

``bootstrap_upper`` is the vectorised form of ``promotion.bootstrap_ci``: the same resamples
(one fixed index matrix per sample size, drawn from the rule's seed), so its upper bound equals
the rule's. It is used because the simulation runs thousands of looks.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

from eurohoops.eval.promotion import CI_LEVEL, MIN_GAP, RESAMPLES, SEED
from eurohoops.models.elo import FloatArray

UPPER_PCT = 100.0 * (1.0 - (1.0 - CI_LEVEL) / 2.0)  # 98.75: the upper end of the 97.5% CI
Z_UPPER = float(stats.norm.ppf(UPPER_PCT / 100.0))  # about 2.2414


@dataclass(frozen=True)
class Look:
    name: str
    n_games: int


def bootstrap_indices(n: int, resamples: int = RESAMPLES, seed: int = SEED) -> np.ndarray:
    """The resample index matrix of the rule: row r holds the games of resample r.

    Stored as uint16 (a season has far fewer than 65,536 games): less simulation memory.
    """
    if n > np.iinfo(np.uint16).max:
        raise ValueError("a season has more games than the uint16 index can hold")
    rng = np.random.default_rng(seed)
    chunk = 1000  # drawn in blocks of rows: the same stream as one draw, with less temporary memory
    blocks = [
        rng.integers(0, n, (min(chunk, resamples - i), n)).astype(np.uint16)
        for i in range(0, resamples, chunk)
    ]
    return np.concatenate(blocks)


def bootstrap_upper(diff: FloatArray, indices: np.ndarray) -> float:
    """Upper bound of the rule's CI of the mean of ``diff`` (``bootstrap_ci``, vectorised)."""
    chunk = 1000  # rows gathered at a time, to keep memory small
    means = np.concatenate(
        [diff[indices[i : i + chunk]].mean(axis=1) for i in range(0, len(indices), chunk)]
    )
    return float(np.percentile(means, UPPER_PCT))


def normal_cumulative_prob(true_gap: float, sd: float, looks: Sequence[Look]) -> tuple[float, ...]:
    """P(promote by each look), normal approximation: the mean of look k is N(true_gap, sd^2 / n_k)
    and promotion at look k needs it below ``min(MIN_GAP, -Z_UPPER * sd / sqrt(n_k))``.

    Looks are nested (a later look includes the earlier games), so the means are correlated.
    Returns the running cumulative probability after each look. For two looks this is
    P(m1 < t1 or m2 < t2) with corr(m1, m2) = sqrt(n1 / n2).
    """
    sizes = [look.n_games for look in looks]
    thresholds = np.array([min(MIN_GAP, -Z_UPPER * sd / np.sqrt(n)) for n in sizes])
    out: list[float] = []
    for k in range(1, len(looks) + 1):
        # Cov(m_i, m_j) = sd^2 / max(n_i, n_j) for nested samples (the first n_min games are shared)
        cov = np.array(
            [[sd * sd / max(sizes[i], sizes[j]) for j in range(k)] for i in range(k)], dtype=float
        )
        # P(no look so far promotes) = P(every m_i >= t_i) = P(-m_i <= -t_i for every i)
        no_promotion = stats.multivariate_normal(mean=np.full(k, -true_gap), cov=cov).cdf(
            -thresholds[:k]
        )
        out.append(1.0 - float(no_promotion))
    return tuple(out)


@dataclass(frozen=True)
class SimResult:
    true_gap: float
    sims: int
    seed: int
    marginal: tuple[float, ...]  # P(first promotion at this look)
    cumulative: tuple[float, ...]  # P(promotion at or before this look)


def simulate_promotion(
    gaps: FloatArray,
    true_gap: float,
    looks: Sequence[Look],
    *,
    sims: int,
    seed: int,
) -> SimResult:
    """Paired bootstrap by simulation: draw each season's per-game gaps from the historical
    gaps, centred on their mean and shifted to ``true_gap``, run the rule at every look.

    ``gaps`` are historical per-game gaps (any split). The looks are nested: the first ``n``
    games of one simulated season form look ``n``, so a later look includes the earlier games.
    """
    centred = gaps - gaps.mean()
    n_max = max(look.n_games for look in looks)
    indices = {look.n_games: bootstrap_indices(look.n_games) for look in looks}
    rng = np.random.default_rng(seed)
    season = rng.choice(centred, size=(sims, n_max), replace=True) + true_gap
    first = np.zeros(len(looks), dtype=np.int64)
    for row in season:
        for k, look in enumerate(looks):
            diff = row[: look.n_games]
            if diff.mean() <= MIN_GAP and bootstrap_upper(diff, indices[look.n_games]) < 0.0:
                first[k] += 1
                break
    marginal = first / sims
    return SimResult(
        true_gap=true_gap,
        sims=sims,
        seed=seed,
        marginal=tuple(float(x) for x in marginal),
        cumulative=tuple(float(x) for x in np.cumsum(marginal)),
    )
