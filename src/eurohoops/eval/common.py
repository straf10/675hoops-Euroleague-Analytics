"""Helpers shared by the eval backtests: report rounding, the paired-bootstrap CI block, the
package-version model tag, the input-data digest and the console-table cell."""

import hashlib
import math
from collections.abc import Callable, Mapping
from importlib.metadata import version
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval.metrics import paired_bootstrap_ci
from eurohoops.models.elo import FloatArray


def round6(value: float) -> float:
    """Report rounding: six decimals, as a plain float."""
    return round(float(value), 6)


def round_finite(value: float | None, digits: int = 6) -> float | None:
    """Report rounding that keeps a missing or non-finite value as None (JSON null)."""
    return None if value is None or not math.isfinite(value) else round(float(value), digits)


def paired_ci(
    diff: FloatArray,
    resamples: int,
    seed: int,
    rounding: Callable[[float], float | None] = round6,
) -> dict[str, Any]:
    """Mean and paired bootstrap 95% CI of ``diff`` as a report block (no empty-split check)."""
    mean, low, high = paired_bootstrap_ci(diff, resamples, seed)
    return {
        "mean": rounding(mean),
        "ci95": [rounding(low), rounding(high)],
        "resamples": resamples,
        "seed": seed,
    }


def gate_passed(report: Mapping[str, Any]) -> bool:
    """Whether a backtest report's validation gate passed: ``gate.passed`` is exactly ``true``.

    A report without a gate, a gate without a verdict (``null``: undecided) and anything that is
    not a JSON ``true`` all read as not passed, so a model goes live only on an explicit pass.
    """
    gate = report.get("gate")
    return isinstance(gate, Mapping) and gate.get("passed") is True


def rmse_diff_bootstrap_ci(
    residual_a: FloatArray, residual_b: FloatArray, resamples: int, seed: int
) -> dict[str, Any] | None:
    """The 95% percentile CI of RMSE(a) - RMSE(b) over game-index resamples (H-d): RMSE is not
    a mean of per-game values, so ``eval.metrics.paired_bootstrap_ci`` (built for linear
    statistics) does not apply -- both RMSEs are recomputed on every resample instead."""
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


def tagged_version(tag: str, key: str | bytes) -> str:
    """``<package version>+<tag>.<8 hex of sha256(key)>``: a model version tied to its tuning
    (a ``str`` key is hashed as UTF-8)."""
    raw = key.encode() if isinstance(key, str) else key
    return f"{version('eurohoops')}+{tag}.{hashlib.sha256(raw).hexdigest()[:8]}"


def data_sha256(*frames: pd.DataFrame) -> str:
    """sha256 of every input table's canonical CSV, in the order given."""
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(frame.to_csv(index=False, lineterminator="\n").encode())
    return digest.hexdigest()


def table_cell(value: float | None, width: int, digits: int) -> str:
    """One right-aligned fixed-point cell of a console table; '-' for a missing value."""
    return f"{'-' if value is None else f'{value:.{digits}f}':>{width}}"
