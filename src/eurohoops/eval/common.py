"""Helpers shared by the eval backtests: report rounding, the paired-bootstrap CI block, the
package-version model tag, the input-data digest and the console-table cell."""

import hashlib
import math
from collections.abc import Callable
from importlib.metadata import version
from typing import Any

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


def tagged_version(tag: str, key: str) -> str:
    """``<package version>+<tag>.<8 hex of sha256(key)>``: a model version tied to its tuning."""
    return f"{version('eurohoops')}+{tag}.{hashlib.sha256(key.encode()).hexdigest()[:8]}"


def data_sha256(*frames: pd.DataFrame) -> str:
    """sha256 of every input table's canonical CSV, in the order given."""
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(frame.to_csv(index=False, lineterminator="\n").encode())
    return digest.hexdigest()


def table_cell(value: float | None, width: int, digits: int) -> str:
    """One right-aligned fixed-point cell of a console table; '-' for a missing value."""
    return f"{'-' if value is None else f'{value:.{digits}f}':>{width}}"
