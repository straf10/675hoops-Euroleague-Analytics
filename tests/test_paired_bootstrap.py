"""The game-level paired bootstrap gives exactly the numbers its former copies gave.

The values below were produced by the copies in ``eval/promotion.py`` (``bootstrap_ci``, a loop
over resamples), ``eval/metrics.py`` (``paired_bootstrap_ci``), ``eval/benchmark.py``
(``paired_gap_ci``) and ``eval/early_totals.py`` (``_bucket_summary``) before they were merged
into ``metrics.paired_bootstrap_ci``. Reports hold numbers these produced, so they are pinned bit
for bit, not approximately. ``eval/r1_power.py`` keeps its own vectorised form (one index matrix
reused over thousands of simulated looks) and is checked against the rule in ``test_r1_power``.
"""

from typing import Any

import numpy as np
import pytest

from eurohoops.eval.benchmark import paired_gap_ci
from eurohoops.eval.early_totals import _bucket_summary
from eurohoops.eval.metrics import paired_bootstrap_ci
from eurohoops.eval.promotion import bootstrap_ci

FloatArray = np.ndarray[Any, np.dtype[np.float64]]


def inputs() -> list[tuple[int, FloatArray, FloatArray]]:
    rng = np.random.default_rng(5)
    out = []
    for n in (2, 37, 250):
        a = rng.normal(0.6, 0.15, n)
        b = rng.normal(0.62, 0.15, n)
        out.append((n, a, b))
    return out


PROMOTION = {
    2: ((-0.28172063505405, -0.10303547047372985), (-0.28172063505405, -0.10303547047372985)),
    37: (
        (-0.11772769983351415, 0.024013720585209286),
        (-0.11883631874703392, 0.016142955027032266),
    ),
    250: (
        (-0.04793376465527877, 0.010843778394658136),
        (-0.04800001820860885, 0.010755308595800922),
    ),
}
METRICS = {
    2: (-0.19237805276388992, -0.28172063505405, -0.10303547047372985),
    37: (-0.05002478667855233, -0.10935911646396763, 0.011507171410750099),
    250: (-0.01858063318326458, -0.043295370850808174, 0.00684629924193643),
}
BENCHMARK = {
    2: [-0.281721, -0.103035],
    37: [-0.111149, 0.011469],
    250: [-0.044088, 0.007404],
}
EARLY = {
    2: {
        "n": 2,
        "line": {"mean": -0.192378, "ci95": [-0.281721, -0.103035]},
        "m1": {"mean": 0.412642, "ci95": [0.342891, 0.482394]},
    },
    37: {
        "n": 37,
        "line": {"mean": -0.050025, "ci95": [-0.112235, 0.013111]},
        "m1": {"mean": 0.330235, "ci95": [0.278818, 0.381382]},
    },
    250: {
        "n": 250,
        "line": {"mean": -0.018581, "ci95": [-0.043704, 0.006533]},
        "m1": {"mean": 0.318652, "ci95": [0.298833, 0.338689]},
    },
}


@pytest.mark.parametrize("case", inputs(), ids=lambda c: f"n{c[0]}")
def test_every_former_copy_gives_its_pinned_numbers(
    case: tuple[int, FloatArray, FloatArray],
) -> None:
    n, a, b = case
    assert (bootstrap_ci(a - b), bootstrap_ci(a - b, 500, 3)) == PROMOTION[n]
    assert paired_bootstrap_ci(a - b, 2000, 11) == METRICS[n]
    assert paired_gap_ci(a, b) == BENCHMARK[n]
    assert _bucket_summary(a - b, b - a * 0.5) == EARLY[n]


def test_percentiles_choose_the_interval() -> None:
    diff = np.random.default_rng(1).normal(0.0, 1.0, 50)
    _, lo95, hi95 = paired_bootstrap_ci(diff, 1000, 2)
    _, lo80, hi80 = paired_bootstrap_ci(diff, 1000, 2, percentiles=(10.0, 90.0))
    assert lo95 < lo80 < hi80 < hi95
