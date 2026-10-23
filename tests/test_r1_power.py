"""E1: power of the R1 looks (reporting only). Synthetic arrays; no logs, no real games."""

import numpy as np
import pytest

from eurohoops.eval.promotion import MIN_GAP, bootstrap_ci
from eurohoops.eval.r1_power import (
    Z_UPPER,
    Look,
    bootstrap_indices,
    bootstrap_upper,
    normal_cumulative_prob,
    simulate_promotion,
)


def test_vectorised_upper_matches_the_rule_bootstrap() -> None:
    rng = np.random.default_rng(7)
    diff = rng.normal(-0.01, 0.1, 60)
    _, hi = bootstrap_ci(diff)
    assert bootstrap_upper(diff, bootstrap_indices(len(diff))) == pytest.approx(hi, abs=1e-12)


def test_single_look_hits_half_at_its_threshold() -> None:
    sd, n = 0.1, 100
    se = sd / np.sqrt(n)
    threshold = min(MIN_GAP, -Z_UPPER * se)
    (prob,) = normal_cumulative_prob(threshold, sd, [Look("only", n)])
    assert prob == pytest.approx(0.5, abs=1e-6)


def test_power_rises_as_the_gap_grows_and_the_null_is_small() -> None:
    looks = [Look("round", 160), Look("end", 372)]
    gaps = [0.0, -0.003, -0.01, -0.02, -0.05]
    cum = [normal_cumulative_prob(g, 0.14, looks)[1] for g in gaps]
    assert cum == sorted(cum)
    assert cum[0] < 0.03  # two looks at 97.5% each: the null rate stays near 2.5%
    assert cum[-1] > 0.99


def test_cumulative_is_a_probability_and_covers_each_look() -> None:
    looks = [Look("round", 90), Look("end", 200)]
    first, end = normal_cumulative_prob(-0.02, 0.27, looks)
    assert 0.0 < first <= end <= 1.0
    (alone,) = normal_cumulative_prob(-0.02, 0.27, [looks[0]])
    assert first == pytest.approx(alone)


def test_simulation_with_no_spread_is_deterministic() -> None:
    gaps = np.zeros(40)
    looks = [Look("a", 10), Look("b", 20)]
    yes = simulate_promotion(gaps, -0.05, looks, sims=20, seed=1)
    assert yes.marginal == (1.0, 0.0)
    assert yes.cumulative == (1.0, 1.0)
    no = simulate_promotion(gaps, 0.0, looks, sims=20, seed=1)
    assert no.cumulative == (0.0, 0.0)
