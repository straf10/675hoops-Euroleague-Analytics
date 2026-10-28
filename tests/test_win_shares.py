"""Win Shares (stats/win_shares.py): each formula on hand-computed numbers, the two-team example
worked out by hand, the team-sum check, and the points-per-win fit.

Hand example: one game, season 2025. Team A (won 80-76) and team B; 100 possessions each, so
league PPP = 156 / 200 = 0.78. Both defences hold opponents to 50% FG (FMwt = 0.8) and 20% of
missed shots to offensive rebounds (DOR% = 0.2). Each team has two players who each played 6,000
seconds (team minutes 12,000). The first player holds the team's counting stats, the second none.
Assisted field goals: A1 6 twos and 4 threes, B1 5 twos and 3 threes, so points per assisted FG =
43 / 18.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eurohoops.stats.assists import AssistRow
from eurohoops.stats.win_shares import (
    AST_CREDIT,
    DEFENSE_REPLACEMENT,
    assisted_fg,
    fit_points_per_win,
    forced_miss_weight,
    individual_drtg,
    marginal_defense,
    marginal_offense,
    offense_possessions,
    points_produced,
    stop_percentage,
    team_check,
    team_seasons_regular,
    win_shares,
)

PPW = 35.5


def _team(team: str, opp: str, won: bool, pts: int, **counts: int) -> dict[str, object]:
    base = {"season": 2025, "game_id": "g1", "team": team, "opponent": opp, "won": won, "pts": pts}
    return {**base, "poss": 100, **counts}


def _box() -> tuple[pd.DataFrame, pd.DataFrame]:
    teams = pd.DataFrame(
        [
            _team(
                "A",
                "B",
                True,
                80,
                fg2m=20,
                fg2a=40,
                fg3m=10,
                fg3a=20,
                ftm=10,
                fta=20,
                oreb=8,
                dreb=32,
                tov=12,
                stl=6,
                blk=4,
            ),
            _team(
                "B",
                "A",
                False,
                76,
                fg2m=20,
                fg2a=40,
                fg3m=10,
                fg3a=20,
                ftm=6,
                fta=12,
                oreb=8,
                dreb=32,
                tov=14,
                stl=6,
                blk=4,
            ),
        ]
    )
    counts = {
        "fg2m": 0,
        "fg2a": 0,
        "fg3m": 0,
        "fg3a": 0,
        "fta": 0,
        "oreb": 0,
        "dreb": 0,
        "ast": 0,
        "stl": 0,
        "blk": 0,
        "tov": 0,
        "pf": 0,
    }
    a1 = {
        "fg2m": 20,
        "fg2a": 40,
        "fg3m": 10,
        "fg3a": 20,
        "fta": 20,
        "oreb": 8,
        "dreb": 32,
        "ast": 15,
        "stl": 6,
        "blk": 4,
        "tov": 12,
        "pf": 20,
    }
    b1 = {
        "fg2m": 20,
        "fg2a": 40,
        "fg3m": 10,
        "fg3a": 20,
        "fta": 12,
        "oreb": 8,
        "dreb": 32,
        "ast": 12,
        "stl": 6,
        "blk": 4,
        "tov": 14,
        "pf": 20,
    }
    rows = [
        ("A", "A1", a1),
        ("A", "A2", counts),
        ("B", "B1", b1),
        ("B", "B2", counts),
    ]
    players = pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": "g1",
                "team": team,
                "opponent": "B" if team == "A" else "A",
                "player_id": pid,
                "player": pid,
                "sec": 6000,
                **stats,
            }
            for team, pid, stats in rows
        ]
    )
    return players, teams


def _assisted() -> pd.DataFrame:
    rows = {
        "g1": [
            *[AssistRow("A", "A2", "A1", 2, "fg")] * 6,
            *[AssistRow("A", "A2", "A1", 3, "fg")] * 4,
            *[AssistRow("B", "B2", "B1", 2, None)] * 5,
            *[AssistRow("B", "B2", "B1", 3, "fg")] * 3,
            AssistRow("A", "A2", "A1", 1, "ft"),  # a free-throw link: not a field goal
        ]
    }
    return assisted_fg(rows, {"g1": 2025})


def test_forced_miss_weight_hand_values() -> None:
    assert forced_miss_weight(0.5, 0.2) == pytest.approx(0.8)
    # 0.4 x 0.8 / (0.4 x 0.8 + 0.6 x 0.2) = 0.32 / 0.44
    assert forced_miss_weight(0.4, 0.2) == pytest.approx(0.32 / 0.44)


def test_offense_possessions_and_marginal_offense() -> None:
    used = offense_possessions(60, 20, 12, 8)  # 60 + 0.44 x 20 + 12 - 8
    assert used == pytest.approx(72.8)
    assert marginal_offense(83.596667, 0.78, used) == pytest.approx(31.355387, abs=1e-4)


def test_points_produced_splits_assisted_points() -> None:
    assert AST_CREDIT == 0.5
    # unassisted 46 + half of 24 assisted + 15 AST x 43/18 x 0.5 + 8 ORB x 0.8 x 1.2
    prod = points_produced(46, 24, ast=15, league_points_per_assist=43 / 18, orb=8, team_ppp=0.8)
    assert prod == pytest.approx(83.596667, abs=1e-4)


def test_defense_stop_drtg_and_marginal_defense() -> None:
    stop = stop_percentage(28.2896, 12000, 100, 6000)  # stops x team MIN / (poss x MIN)
    assert stop == pytest.approx(0.565792)
    drtg = individual_drtg(76, 76 / 33.6, stop)  # 76 + 0.2 (100 x 2.2619 x (1 - 0.5658) - 76)
    assert drtg == pytest.approx(80.442743, abs=1e-4)
    md = marginal_defense(6000, 12000, 100, 0.78, drtg)  # 0.5 x 100 x (1.08 x 0.78 - DRtg / 100)
    assert DEFENSE_REPLACEMENT == 1.08
    assert md == pytest.approx(1.8986286, abs=1e-4)


def test_win_shares_hand_example() -> None:
    players, teams = _box()
    ws = win_shares(players, teams, _assisted(), PPW).set_index("player_id")
    assert ws.loc["A1", "ows"] == pytest.approx(0.8832503, abs=1e-4)
    assert ws.loc["A1", "dws"] == pytest.approx(0.0534825, abs=1e-4)
    assert ws.loc["A1", "ws"] == pytest.approx(0.9367328, abs=1e-4)
    assert ws.loc["A1", "ws40"] == pytest.approx(0.9367328 / 100 * 40, abs=1e-3)
    assert ws.loc["A2", "ows"] == pytest.approx(0.0, abs=1e-9)
    assert ws.loc["A2", "dws"] == pytest.approx(-0.1518755, abs=1e-4)
    assert ws.loc["B1", "ows"] == pytest.approx(0.8726424, abs=1e-4)  # used 60 + 0.44 x 12 + 14 - 8
    assert ws.loc["B1", "ws"] == pytest.approx(0.8834035, abs=1e-4)
    assert ws.loc["B2", "dws"] == pytest.approx(-0.2010094, abs=1e-4)


def test_team_sum_check() -> None:
    players, teams = _box()
    ws = win_shares(players, teams, _assisted(), PPW)
    sums = ws.groupby("team")["ws"].sum()
    assert sums["A"] == pytest.approx(0.7848573, abs=1e-4)
    assert sums["B"] == pytest.approx(0.6823951, abs=1e-4)
    check = team_check(ws, teams).iloc[0]
    assert check["teams"] == 2
    assert check["mae"] == pytest.approx(0.4487689, abs=1e-4)  # mean of |0.785 - 1| and |0.682 - 0|
    assert check["correlation"] == pytest.approx(1.0)  # the winner also has the larger WS sum
    assert check["ws_total"] == pytest.approx(1.4672524, abs=1e-4)


def test_fit_points_per_win_recovers_slope() -> None:
    rng = np.random.default_rng(1)
    diff = rng.uniform(-10, 10, size=300)
    wins_pct = 0.5 + 0.02 * diff  # exact: 1 / 0.02 = 50 points per win
    frame = pd.DataFrame(
        {"games": 34, "wins": 34 * wins_pct, "pf": 1000 + 34 * diff / 2, "pa": 1000 - 34 * diff / 2}
    )
    fit = fit_points_per_win(frame, resamples=200)
    assert fit.value == pytest.approx(50.0, rel=1e-9)
    assert fit.low <= fit.value + 1e-9 and fit.value - 1e-9 <= fit.high
    assert fit.intercept == pytest.approx(0.5, abs=1e-9)


def test_team_seasons_regular_counts_regular_season_only() -> None:
    games = pd.DataFrame(
        {
            "game_id": ["r1", "r2", "p1"],
            "season": [2025, 2025, 2025],
            "phase": ["RS", "RS", "PO"],
            "home": ["A", "B", "A"],
            "away": ["B", "A", "B"],
            "home_score": [80, 70, 90],
            "away_score": [76, 75, 60],
            "played": [True, True, True],
            "forfeit": [False, False, False],
        }
    )
    out = team_seasons_regular(games).set_index("team")
    assert out.loc["A", "games"] == 2
    assert out.loc["A", "wins"] == 2  # won at home (80-76) and at B (75-70)
    assert out.loc["A", "pf"] == 80 + 75
    assert out.loc["B", "pa"] == 80 + 75  # B's points against: 80 at A, 75 at home
