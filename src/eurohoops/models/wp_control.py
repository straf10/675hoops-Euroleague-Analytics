"""Game-control parts (docs/models/wp.md, section 8): dominance, control, drama, comeback, crunch.

Inputs come from the chosen WP line (the baseline if the gate fails): the team's own WP at each
checkpoint, in game order, and the per-play change in WP. Killer instinct is dropped. The 0.6
control threshold and the 300 s crunch window are display conventions, not fitted values.
No composite is built.

A team's view is its own WP: the home WP for the home team, 1 minus it for the away team. The
section 8 formulas, written for the eventual winner, are applied to each team's own view.
"""

from dataclasses import dataclass

import numpy as np

from eurohoops.models.wp import CONTROL_THRESHOLD, CRUNCH_SECONDS

FloatArray = np.ndarray


@dataclass(frozen=True)
class GameParts:
    dominance: float  # mean of 2 * (WP - 0.5) over checkpoints; range (-1, 1)
    control: float  # share of checkpoints with WP > 0.6; range [0, 1]
    drama: float  # total variation of WP over checkpoints; raw
    comeback: float  # 1 - min WP over checkpoints; range [0, 1]
    crunch: float  # sum of |dWP| over regulation plays with t <= 300 s; raw


def team_view(wp_home: FloatArray, team_is_home: bool) -> FloatArray:
    return (
        np.asarray(wp_home, dtype=np.float64)
        if team_is_home
        else 1.0 - np.asarray(wp_home, dtype=np.float64)
    )


def dominance(team_wp: FloatArray) -> float:
    return float(np.mean(2.0 * (team_wp - 0.5)))


def control(team_wp: FloatArray) -> float:
    return float(np.mean(team_wp > CONTROL_THRESHOLD))


def drama(team_wp: FloatArray) -> float:
    return float(np.sum(np.abs(np.diff(team_wp))))


def comeback(team_wp: FloatArray) -> float:
    return float(1.0 - np.min(team_wp))


def crunch(delta_wp: FloatArray, t: FloatArray, regulation: FloatArray) -> float:
    """Sum of |dWP| over plays in regulation with at most 300 s left. ``delta_wp`` is each play's
    change on the line, both terms taken at the play's own clock (section 8)."""
    in_window = regulation & (t <= CRUNCH_SECONDS)
    return float(np.sum(np.abs(delta_wp[in_window])))


def game_parts(
    team_wp: FloatArray, delta_wp: FloatArray, t: FloatArray, regulation: FloatArray
) -> GameParts:
    """All five parts for one team: ``team_wp`` at the checkpoints in game order, and the play
    deltas with their clock ``t`` and a regulation flag."""
    return GameParts(
        dominance=dominance(team_wp),
        control=control(team_wp),
        drama=drama(team_wp),
        comeback=comeback(team_wp),
        crunch=crunch(delta_wp, t, regulation),
    )
