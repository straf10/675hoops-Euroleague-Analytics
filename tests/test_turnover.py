import numpy as np
import pandas as pd

from eurohoops.models.m5 import ResidualFit
from eurohoops.models.turnover import mixed_team_adjustment, roster_continuity


def test_roster_continuity_first_game_of_season_is_one() -> None:
    games = pd.DataFrame(
        {
            "game_id": ["g1"],
            "season": [2025],
            "phase": ["RS"],
            "round": [1],
            "tipoff_utc": [pd.Timestamp("2025-10-01", tz="UTC")],
            "home": ["A"],
            "away": ["B"],
            "played": [True],
            "forfeit": [False],
            "neutral": [False],
        }
    )
    player_games = pd.DataFrame(
        {
            "game_id": ["g1", "g1"],
            "team": ["A", "B"],
            "player_id": ["p1", "p2"],
            "sec": [600, 600],
        }
    )
    out = roster_continuity(games, player_games)
    assert out.iloc[0]["c_home"] == 1.0
    assert out.iloc[0]["c_away"] == 1.0


def test_mixed_adjustment_with_carry_one_matches_full() -> None:
    full = ResidualFit(
        adjustment=np.array([2.0]),
        rest_coef=np.zeros((1, 0)),
        home=np.array([0.5]),
        r_home=np.array([1.0]),
        r_away=np.array([-1.0]),
    )
    season = ResidualFit(
        adjustment=np.array([9.0]),
        rest_coef=np.zeros((1, 0)),
        home=np.array([0.1]),
        r_home=np.array([4.0]),
        r_away=np.array([-4.0]),
    )
    adj = mixed_team_adjustment(full, season, np.array([1.0]), np.array([1.0]), np.array([1.0]))
    assert adj[0] == 2.5
