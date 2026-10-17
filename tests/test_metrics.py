import math

import numpy as np
import pytest

from eurohoops.eval.metrics import (
    crps_normal,
    ece,
    paired_bootstrap_ci,
    paired_bootstrap_ci_clustered,
    reliability,
    score,
)

# Four games: bins 1 (two games), 7 and 9.
P = np.array([0.15, 0.18, 0.72, 0.95])
Y = np.array([0.0, 1.0, 1.0, 1.0])


def test_ece_on_a_hand_computed_toy_set() -> None:
    # bin 1: mean P .165 vs observed .5 (x2 games); bin 7: .72 vs 1; bin 9: .95 vs 1.
    expected = (2 * abs(0.165 - 0.5) + abs(0.72 - 1.0) + abs(0.95 - 1.0)) / 4
    assert expected == pytest.approx(0.25)
    assert ece(P, Y) == pytest.approx(expected, abs=1e-12)


def test_reliability_bins() -> None:
    bins = reliability(P, Y)
    assert len(bins) == 10
    assert [b["n"] for b in bins] == [0, 2, 0, 0, 0, 0, 0, 1, 0, 1]
    assert bins[1] == {"low": 0.1, "high": 0.2, "n": 2, "mean_p": 0.165, "observed": 0.5}
    assert bins[0]["mean_p"] is None
    assert bins[0]["observed"] is None


def test_bin_edges_are_left_closed_and_one_falls_in_the_last_bin() -> None:
    edges = np.array([0.0, 0.1, 0.5, 0.9999, 1.0])
    counts = [b["n"] for b in reliability(edges, np.ones(5))]
    assert counts == [1, 1, 0, 0, 0, 1, 0, 0, 0, 2]


def test_a_perfectly_calibrated_bin_has_zero_ece() -> None:
    p = np.full(4, 0.75)
    assert ece(p, np.array([1.0, 1.0, 1.0, 0.0])) == pytest.approx(0.0)


def test_score_carries_calibration() -> None:
    m = score(P, np.zeros(4), np.where(Y == 1.0, 5.0, -5.0))
    assert m.ece == pytest.approx(0.25)
    assert m.as_dict()["reliability"][7]["observed"] == 1.0


def test_empty_score_keeps_the_bins() -> None:
    empty = score(np.empty(0), np.empty(0), np.empty(0)).as_dict()
    assert empty["ece"] is None
    assert [b["n"] for b in empty["reliability"]] == [0] * 10


def normal_cdf(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    return np.array([0.5 * (1.0 + math.erf((v - mu) / (sigma * math.sqrt(2.0)))) for v in x])


@pytest.mark.parametrize(
    ("mu", "sigma", "y"), [(0.0, 1.0, 0.0), (4.5, 11.7, -12.0), (-3.0, 2.0, 7.5)]
)
def test_crps_matches_a_numerical_integral(mu: float, sigma: float, y: float) -> None:
    # CRPS = integral of (F(x) - 1{x >= y})^2 dx, split at the step so both halves are smooth.
    lo, hi = min(mu, y) - 12 * sigma, max(mu, y) + 12 * sigma
    below, above = np.linspace(lo, y, 200_001), np.linspace(y, hi, 200_001)
    integral = np.trapezoid(normal_cdf(below, mu, sigma) ** 2, below) + np.trapezoid(
        (1.0 - normal_cdf(above, mu, sigma)) ** 2, above
    )
    closed = crps_normal(np.array([mu]), sigma, np.array([y]))[0]
    assert closed == pytest.approx(integral, abs=1e-6)


def test_crps_tends_to_the_absolute_error_as_sigma_shrinks() -> None:
    crps = crps_normal(np.array([2.0, -1.0]), 1e-9, np.array([7.0, -1.0]))
    assert crps == pytest.approx([5.0, 0.0], abs=1e-8)


def test_score_reports_crps_only_with_a_sigma() -> None:
    margin = np.array([10.0, -4.0])
    exp = np.array([6.0, 2.0])
    p = np.array([0.7, 0.6])
    assert score(p, exp, margin).margin_crps is None
    expected = crps_normal(exp, 12.0, margin).mean()
    assert score(p, exp, margin, 12.0).margin_crps == pytest.approx(expected)


# ---- round-clustered paired bootstrap


def test_clustered_with_singletons_is_the_game_level_bootstrap() -> None:
    diff = np.random.default_rng(3).normal(-0.02, 0.2, 57)
    clusters = list(range(len(diff)))  # one game per cluster
    clustered = paired_bootstrap_ci_clustered(diff, clusters, 2_000, 99)
    game_level = paired_bootstrap_ci(diff, 2_000, 99)
    assert clustered == pytest.approx(game_level, abs=1e-12)


def test_correlated_clusters_widen_the_interval() -> None:
    rng = np.random.default_rng(5)
    # 20 rounds of 5 games; each round shares one shock, so games within a round are correlated.
    shock = np.repeat(rng.normal(0.0, 0.3, 20), 5)
    diff = shock + rng.normal(0.0, 0.01, 100)
    rounds = [r for r in range(20) for _ in range(5)]
    _, g_lo, g_hi = paired_bootstrap_ci(diff, 4_000, 1)
    _, c_lo, c_hi = paired_bootstrap_ci_clustered(diff, rounds, 4_000, 1)
    assert (c_hi - c_lo) > 2 * (g_hi - g_lo)


def test_clustered_is_deterministic_with_the_seed() -> None:
    diff = np.linspace(-0.3, 0.2, 40)
    rounds = [i // 4 for i in range(40)]
    first = paired_bootstrap_ci_clustered(diff, rounds, 500, 7)
    assert first == paired_bootstrap_ci_clustered(diff, rounds, 500, 7)
    assert first != paired_bootstrap_ci_clustered(diff, rounds, 500, 8)


def test_clustered_mean_and_level_and_edge_cases() -> None:
    diff = np.array([1.0, 2.0, 3.0, 4.0])
    mean, low, high = paired_bootstrap_ci_clustered(diff, ["a", "a", "b", "b"], 1_000, 2)
    assert mean == pytest.approx(2.5)
    wide = paired_bootstrap_ci_clustered(diff, ["a", "a", "b", "b"], 1_000, 2, level=0.99)
    assert wide[1] <= low and wide[2] >= high
    empty = paired_bootstrap_ci_clustered(np.array([]), [], 10, 1)
    assert all(math.isnan(x) for x in empty)
    with pytest.raises(ValueError, match="cluster label"):
        paired_bootstrap_ci_clustered(diff, ["a"], 10, 1)
