"""The shared bootstrap helpers give exactly the numbers the per-model copies gave.

The reference functions below are frozen copies of the implementations that lived in
``eval/m6_backtest.py``, ``eval/m7_backtest.py``, ``eval/metrics.py`` and ``eval/m3_backtest.py``
before they were merged. The reports hold numbers these produced, so the shared versions must
agree with them bit for bit, not approximately."""

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval.common import rmse_diff_bootstrap_ci, round_finite
from eurohoops.eval.metrics import (
    cluster_bootstrap_ci,
    cluster_ratio_ci,
    paired_bootstrap_ci_clustered,
)

FloatArray = np.ndarray[Any, np.dtype[np.float64]]


def ref_m6(numerator, denominator, cluster, resamples, seed):  # type: ignore[no-untyped-def]
    if not len(numerator):
        return math.nan, math.nan, math.nan
    nums = np.bincount(cluster, weights=numerator)
    dens = np.bincount(cluster, weights=denominator)
    draw = np.random.default_rng(seed).integers(0, len(nums), size=(resamples, len(nums)))
    means = nums[draw].sum(axis=1) / dens[draw].sum(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(numerator.sum() / denominator.sum()), float(low), float(high)


def ref_m7(diff, cluster, resamples, seed):  # type: ignore[no-untyped-def]
    if not len(diff):
        return math.nan, math.nan, math.nan
    sums = np.bincount(cluster, weights=diff)
    counts = np.bincount(cluster).astype(np.float64)
    draw = np.random.default_rng(seed).integers(0, len(sums), size=(resamples, len(sums)))
    means = sums[draw].sum(axis=1) / counts[draw].sum(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(diff.mean()), float(low), float(high)


def ref_paired_clustered(  # type: ignore[no-untyped-def]
    diff, clusters: Sequence[object], resamples, seed, *, level=0.95
):
    if len(clusters) != len(diff):
        raise ValueError("every game needs a cluster label")
    if not len(diff):
        return math.nan, math.nan, math.nan
    codes = pd.factorize(pd.Series(list(clusters)))[0]
    k = int(codes.max()) + 1
    sums = np.bincount(codes, weights=diff, minlength=k)
    sizes = np.bincount(codes, minlength=k).astype(np.float64)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, k, size=(resamples, k))
    means = sums[pick].sum(axis=1) / sizes[pick].sum(axis=1)
    tail = 100.0 * (1.0 - level) / 2.0
    low, high = np.percentile(means, [tail, 100.0 - tail])
    return float(diff.mean()), float(low), float(high)


def ref_rmse(residual_a, residual_b, resamples, seed):  # type: ignore[no-untyped-def]
    n = len(residual_a)
    if not n:
        return None
    point = float(np.sqrt(np.mean(residual_a**2)) - np.sqrt(np.mean(residual_b**2)))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(resamples, n))
    rmse_a = np.sqrt((residual_a[idx] ** 2).mean(axis=1))
    rmse_b = np.sqrt((residual_b[idx] ** 2).mean(axis=1))
    low, high = np.percentile(rmse_a - rmse_b, [2.5, 97.5])
    return {
        "mean": round_finite(point),
        "ci95": [round_finite(float(low)), round_finite(float(high))],
        "resamples": resamples,
        "seed": seed,
    }


def data(seed: int, n: int = 240, clusters: int = 31) -> tuple[FloatArray, FloatArray, Any]:
    rng = np.random.default_rng(seed)
    cluster = rng.integers(0, clusters, size=n)
    _, cluster = np.unique(cluster, return_inverse=True)  # ids 0..C-1, every one present
    return rng.normal(0.2, 1.0, n), rng.uniform(0.5, 3.0, n), cluster.astype(np.int64)


@pytest.mark.parametrize("seed", [1, 7, 20261102])
def test_the_ratio_core_is_the_m6_helper(seed: int) -> None:
    num, den, cluster = data(seed)
    assert cluster_ratio_ci(num, den, cluster, 1500, seed) == ref_m6(num, den, cluster, 1500, seed)


@pytest.mark.parametrize("seed", [1, 7, 20261102])
def test_the_mean_form_is_the_m7_helper(seed: int) -> None:
    diff, _, cluster = data(seed)
    assert cluster_bootstrap_ci(diff, cluster, 1500, seed) == ref_m7(diff, cluster, 1500, seed)


@pytest.mark.parametrize(("seed", "level"), [(1, 0.95), (9, 0.95), (4, 0.99), (4, 0.9)])
def test_the_labelled_form_is_the_metrics_helper(seed: int, level: float) -> None:
    diff, _, cluster = data(seed)
    labels = [f"r{c}" for c in cluster]
    got = paired_bootstrap_ci_clustered(diff, labels, 1500, seed, level=level)
    assert got == ref_paired_clustered(diff, labels, 1500, seed, level=level)


def test_empty_inputs_are_all_nan_in_every_form() -> None:
    empty, ids = np.zeros(0), np.zeros(0, dtype=np.int64)
    for got in (
        cluster_ratio_ci(empty, empty, ids, 10, 1),
        cluster_bootstrap_ci(empty, ids, 10, 1),
        paired_bootstrap_ci_clustered(empty, [], 10, 1),
    ):
        assert all(math.isnan(v) for v in got)


@pytest.mark.parametrize("seed", [1, 5, 13])
def test_the_rmse_difference_is_the_m3_helper(seed: int) -> None:
    rng = np.random.default_rng(seed)
    a, b = rng.normal(0, 1.2, 180), rng.normal(0, 1.0, 180)
    assert rmse_diff_bootstrap_ci(a, b, 800, seed) == ref_rmse(a, b, 800, seed)
    assert rmse_diff_bootstrap_ci(np.zeros(0), np.zeros(0), 10, 1) is None
