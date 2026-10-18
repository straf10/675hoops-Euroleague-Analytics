"""The WP model math (docs/models/wp.md, sections 1, 4, 5 and 7) on small synthetic states."""

import math

import numpy as np
import pytest
from scipy.special import ndtr

from eurohoops.models import wp


def _col(*values: float) -> np.ndarray:
    return np.array(values, dtype=float)


def test_baseline_at_tip_off_is_phi_of_the_expected_margin_over_eleven() -> None:
    p = wp.baseline_wp(_col(0.0), _col(2400.0), _col(11.0))
    assert math.isclose(p[0], ndtr(1.0), rel_tol=1e-12)


def test_baseline_at_the_buzzer_uses_the_sixty_second_floor() -> None:
    p = wp.baseline_wp(_col(5.0), _col(0.0), _col(0.0))
    assert math.isclose(p[0], ndtr(5.0 / (11.0 * math.sqrt(60.0 / 2400.0))), rel_tol=1e-12)


def test_baseline_pre_game_margin_counts_less_as_the_game_ends() -> None:
    # Same score and expected margin: at t = 2000 the expectation is still mostly to be played,
    # at t = 100 almost none of it is, so the probability sits closer to 0.5.
    early = wp.baseline_wp(_col(0.0), _col(2000.0), _col(10.0))[0]
    late = wp.baseline_wp(_col(0.0), _col(100.0), _col(10.0))[0]
    assert 0.5 < late < early


def test_features_match_section_four_and_floor_the_buzzer() -> None:
    x = wp.base_features(_col(6.0), _col(1200.0), _col(0.0), _col(0.0), _col(1.0))
    m, tf, ot, m_tf, z, lp, nt = x[0]
    assert (m, tf, ot, lp, nt) == (6.0, 0.5, 0.0, 0.0, 1.0)
    assert m_tf == 3.0
    assert math.isclose(z, 6.0 / math.sqrt(1200.0 / 2400.0))
    at_buzzer = wp.base_features(_col(6.0), _col(0.0), _col(0.0), _col(0.0), _col(0.0))
    assert math.isclose(at_buzzer[0][4], 6.0 / math.sqrt(60.0 / 2400.0))


def test_logit_design_adds_the_interaction_column() -> None:
    x = wp.logit_design(_col(4.0), _col(1200.0), _col(0.0), _col(0.5), _col(0.0))
    assert x.shape == (1, 8)
    assert math.isclose(x[0, 7], 4.0 * 0.5 * 0.5)


def test_displayed_line_starts_at_p_pre_and_fades_linearly_to_the_buzzer() -> None:
    wp_model = np.array([0.5, 0.5, 0.5])
    t = np.array([2400.0, 1200.0, 0.0])
    line = wp.displayed_wp(wp_model, 0.2, t, np.zeros(3))
    assert np.allclose(line, [0.7, 0.6, 0.5])


def test_overtime_has_no_tipoff_gap() -> None:
    line = wp.displayed_wp(_col(0.5), 0.2, _col(300.0), _col(1.0))
    assert np.allclose(line, [0.5])


def test_displayed_line_is_clipped_to_the_stated_range() -> None:
    line = wp.displayed_wp(_col(0.99, 0.01), 0.5, _col(2400.0, 2400.0), np.zeros(2))
    assert np.allclose(line, [0.999, 0.51])


def test_tipoff_gap_is_the_pre_game_probability_minus_the_model_at_tip_off() -> None:
    assert math.isclose(wp.tipoff_gap(0.62, 0.60), 0.02)


def test_logit_family_is_monotone_in_the_margin() -> None:
    rng = np.random.default_rng(0)
    n = 4000
    m = rng.normal(0, 10, n)
    t = rng.uniform(0, 2400, n)
    y = (rng.uniform(size=n) < ndtr(m / 9.0)).astype(float)
    zeros = np.zeros(n)
    fam = wp.fit_family("logit", None, (m, t, zeros, zeros, zeros), y)
    low = fam.predict_raw(_col(-10.0), _col(1200.0), _col(0.0), _col(0.0), _col(0.0))
    high = fam.predict_raw(_col(10.0), _col(1200.0), _col(0.0), _col(0.0), _col(0.0))
    assert 0.0 < low[0] < 0.5 < high[0] < 1.0


def test_gbm_setting_is_fitted_and_unknown_settings_are_refused() -> None:
    rng = np.random.default_rng(1)
    n = 2000
    m = rng.normal(0, 10, n)
    t = rng.uniform(0, 2400, n)
    y = (rng.uniform(size=n) < ndtr(m / 9.0)).astype(float)
    zeros = np.zeros(n)
    fam = wp.fit_family("gbm", "G1", (m, t, zeros, zeros, zeros), y)
    assert (fam.name, fam.setting) == ("gbm", "G1")
    raw = fam.predict_raw(
        _col(-15.0, 15.0), _col(600.0, 600.0), np.zeros(2), np.zeros(2), np.zeros(2)
    )
    assert raw[0] < raw[1]
    with pytest.raises(ValueError, match="unknown GBM setting"):
        wp.fit_family("gbm", "G9", (m, t, zeros, zeros, zeros), y)


def test_isotonic_map_is_a_step_function_into_the_unit_interval() -> None:
    raw = np.linspace(0.05, 0.95, 200)
    iso = wp.fit_isotonic(raw, (raw > 0.5).astype(float))
    values = iso.predict(np.array([-1.0, 0.2, 0.8, 2.0]))
    assert np.all((values >= 0.0) & (values <= 1.0))
    assert values[0] == values[1] == 0.0
    assert values[2] == values[3] == 1.0


def test_log_loss_is_clipped_and_matches_the_definition() -> None:
    ll = wp.log_loss(_col(1.0, 0.0), _col(0.8, 0.0))
    assert math.isclose(ll[0], -math.log(0.8))
    assert math.isfinite(ll[1])


def test_version_string_carries_the_spec_hash() -> None:
    assert f"0.2.0+wp.{wp.SPEC_SHA256[:8]}" == wp.VERSION
    assert len(wp.SPEC_SHA256) == 64
