"""Game-control parts (docs/models/wp.md, section 8) with hand-computed answers."""

import math

import numpy as np

from eurohoops.models import wp_control as wc


def test_game_decided_at_the_buzzer_shows_the_loser_ahead_until_the_last_checkpoint() -> None:
    wp_home = np.array([0.9, 0.9, 0.9, 0.0])  # home led by a lot, then lost the final play
    home = wc.team_view(wp_home, team_is_home=True)
    away = wc.team_view(wp_home, team_is_home=False)
    assert math.isclose(wc.dominance(home), 0.35)  # 2 * mean(0.4, 0.4, 0.4, -0.5)
    assert math.isclose(wc.control(home), 0.75)  # three of four above 0.6
    assert math.isclose(wc.drama(home), 0.9)  # |0.9 - 0.0| once
    assert math.isclose(wc.dominance(away), -0.35)
    assert math.isclose(wc.control(away), 0.25)
    assert math.isclose(wc.comeback(away), 0.9)  # 1 - min(0.1, 0.1, 0.1, 1.0)


def test_buzzer_winner_crunch_counts_the_last_plays_in_regulation() -> None:
    delta = np.array([0.2, 0.5, 0.3, 0.1, -0.4])
    t = np.array([250.0, 400.0, 100.0, 300.0, 0.0])
    regulation = np.array([True, True, False, True, True])  # the t = 100 play is overtime
    # 250 s (0.2), 300 s (0.1, inclusive) and the buzzer play (0.4); 400 s and OT are out.
    assert math.isclose(wc.crunch(delta, t, regulation), 0.7)


def test_blowout_has_high_dominance_and_control_and_almost_no_drama() -> None:
    wp_home = np.array([0.98, 0.99, 0.995, 1.0])
    home = wc.team_view(wp_home, team_is_home=True)
    assert math.isclose(wc.dominance(home), 2 * np.mean(wp_home - 0.5))
    assert math.isclose(wc.control(home), 1.0)
    assert math.isclose(wc.drama(home), 0.02, abs_tol=1e-12)
    assert math.isclose(wc.comeback(home), 0.02, abs_tol=1e-12)


def test_overtime_checkpoints_count_for_drama_and_control_but_not_for_crunch() -> None:
    # Regulation ends level-ish, the away side wins in the first overtime.
    wp_home = np.array([0.6, 0.5, 0.2, 0.0])
    away = wc.team_view(wp_home, team_is_home=False)
    assert math.isclose(wc.drama(away), 0.1 + 0.3 + 0.2)
    assert math.isclose(wc.control(away), 0.5)  # 0.8 and 1.0 are the only views above 0.6
    delta = np.array([0.4, -0.2])
    t = np.array([120.0, 0.0])
    regulation = np.array([False, False])  # both plays are in overtime
    assert wc.crunch(delta, t, regulation) == 0.0


def test_team_view_flips_only_for_the_away_side() -> None:
    wp_home = np.array([0.25, 0.75])
    assert np.allclose(wc.team_view(wp_home, True), wp_home)
    assert np.allclose(wc.team_view(wp_home, False), [0.75, 0.25])


def test_game_parts_bundles_the_five_parts() -> None:
    parts = wc.game_parts(
        np.array([0.5, 0.7]), np.array([0.2]), np.array([200.0]), np.array([True])
    )
    assert parts.crunch == 0.2
    assert math.isclose(parts.dominance, 0.2)  # 2 * mean(0, 0.2)
    assert math.isclose(parts.comeback, 0.5)
