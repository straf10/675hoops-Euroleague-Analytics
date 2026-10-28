"""Win Shares (stats/win_shares.py): each formula on hand-computed numbers, a two-team game
worked out by hand, the team-sum check, and the points-per-win fit (a comparison only).

Hand example: one game, season 2025. Team A won 80-76 over team B. Each team has five players who
each played 6,000 seconds (team minutes 30,000). A1 and A2 hold team A's counting stats (A3-A5 have
none), and B1 and B2 hold team B's. Both teams took 60 field goals and 100 possessions, so league
PPP is 156 / 200 = 0.78, league PPG is 78, and points per win is 0.32 x 78 = 24.96 for both teams.
Team A's defence allowed 30 of 60 field goals (DFG 50%) and 8 of 40 offensive rebounds (DOR 20%),
so FMwt is 0.8. Team A's and B's free-throw percentages are both 50%.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eurohoops.stats.win_shares import (
    box_win_shares,
    fit_points_per_win,
    individual_drtg,
    marginal_defense,
    marginal_offense,
    points_per_win,
    points_produced,
    possessions_used,
    qast,
    scoring_possessions,
    scoring_possessions_player,
    stop_percentage,
    team_check,
    team_orb_weight,
    team_play_pct,
    team_seasons_regular,
    win_shares,
)

PPW = 24.96  # 0.32 x 78 x (100 / 100)
ZEROS = (
    "pts",
    "pf",
    "fg2m",
    "fg2a",
    "fg3m",
    "fg3a",
    "ftm",
    "fta",
    "oreb",
    "dreb",
    "ast",
    "stl",
    "blk",
    "tov",
)


def _team(team: str, opp: str, won: bool, **counts: int) -> dict[str, object]:
    return {
        "season": 2025,
        "game_id": "g1",
        "team": team,
        "opponent": opp,
        "won": won,
        "poss": 100,
        **counts,
    }


def _player(team: str, pid: str, sec: int, **stats: int) -> dict[str, object]:
    row: dict[str, object] = {
        "season": 2025,
        "game_id": "g1",
        "team": team,
        "opponent": "B" if team == "A" else "A",
        "player_id": pid,
        "player": pid,
        "sec": sec,
    }
    return {**row, **dict.fromkeys(ZEROS, 0), **stats}


def _box() -> tuple[pd.DataFrame, pd.DataFrame]:
    teams = pd.DataFrame(
        [
            _team(
                "A",
                "B",
                True,
                pts=80,
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
                ast=15,
            ),
            _team(
                "B",
                "A",
                False,
                pts=76,
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
                ast=12,
            ),
        ]
    )
    players = pd.DataFrame(
        [
            _player(
                "A",
                "A1",
                6000,
                pts=48,
                fg2m=12,
                fg2a=24,
                fg3m=6,
                fg3a=12,
                ftm=6,
                fta=12,
                oreb=5,
                dreb=20,
                tov=7,
                stl=4,
                blk=3,
                ast=9,
                pf=12,
            ),
            _player(
                "A",
                "A2",
                6000,
                pts=32,
                fg2m=8,
                fg2a=16,
                fg3m=4,
                fg3a=8,
                ftm=4,
                fta=8,
                oreb=3,
                dreb=12,
                tov=5,
                stl=2,
                blk=1,
                ast=6,
                pf=8,
            ),
            _player("A", "A3", 6000),
            _player("A", "A4", 6000),
            _player("A", "A5", 6000),
            _player(
                "B",
                "B1",
                6000,
                pts=46,
                fg2m=12,
                fg2a=24,
                fg3m=6,
                fg3a=12,
                ftm=4,
                fta=8,
                oreb=5,
                dreb=20,
                tov=9,
                stl=4,
                blk=3,
                ast=7,
                pf=12,
            ),
            _player(
                "B",
                "B2",
                6000,
                pts=30,
                fg2m=8,
                fg2a=16,
                fg3m=4,
                fg3a=8,
                ftm=2,
                fta=4,
                oreb=3,
                dreb=12,
                tov=5,
                stl=2,
                blk=1,
                ast=5,
                pf=8,
            ),
            _player("B", "B3", 6000),
            _player("B", "B4", 6000),
            _player("B", "B5", 6000),
        ]
    )
    return players, teams


def test_scoring_possessions_and_play_rate() -> None:
    assert scoring_possessions(30, 0.5, 20) == pytest.approx(36.0)  # 30 + 0.75 x 20 x 0.4
    assert team_play_pct(36.0, 60, 20, 12) == pytest.approx(0.45)  # 36 / (60 + 8 + 12)


def test_orb_weight_from_orb_and_play_rates() -> None:
    assert team_orb_weight(0.2, 0.45) == pytest.approx(36 / 47)  # 0.36 / (0.36 + 0.11)


def test_qast_from_minutes_assists_and_makes() -> None:
    # A1 plays 6,000 of 30,000 team seconds (one fifth), 9 of his team's 15 assists, 18 of 30 FGM.
    value = qast(sec=6000, team_sec=30000, ast=9, fgm=18, team_ast=15, team_fgm=30)
    assert value == pytest.approx(0.228)  # 1.14 x (15 - 9) / 30; the second term is 0 at one fifth


def test_points_per_win_is_the_pace_adjusted_league_ppg() -> None:
    assert points_per_win(78, 100, 100) == pytest.approx(PPW)
    assert points_per_win(78, 110, 100) == pytest.approx(PPW * 1.1)


def test_points_produced_hand_value_for_a2() -> None:
    # FG part 28 x (1 - 0.5 x 0.5833 x 0.342); AST part 4.0833; FT 4; ORB part 3 x 0.7660 x 2.2222.
    prod = points_produced(
        fgm=12,
        fg3m=4,
        pts=32,
        ftm=4,
        fga=24,
        fg_share=28 / 48,
        qast_value=0.342,
        ast=6,
        team_fgm=30,
        team_fg3m=10,
        team_pts=80,
        team_ftm=10,
        team_fga=60,
        oreb=3,
        team_orb_factor=3.6 / 47,
        orb_weight_play=36 / 47 * 0.45,
        team_ppp_scoring=80 / 36,
    )
    assert prod == pytest.approx(33.038308, abs=1e-5)


def test_possessions_used_hand_value_for_a2() -> None:
    scoring = scoring_possessions_player(
        fgm=12,
        fga=24,
        pts=32,
        ftm=4,
        fta=8,
        ft_pct=0.5,
        fg_share=28 / 48,
        qast_value=0.342,
        ast=6,
        team_pts=80,
        team_ftm=10,
        team_fga=60,
        oreb=3,
        team_orb_factor=3.6 / 47,
        orb_weight_play=36 / 47 * 0.45,
    )
    used = possessions_used(
        scoring=scoring, fga=24, fgm=12, team_orb_pct_value=0.2, ft_pct=0.5, fta=8, tov=5
    )
    assert used == pytest.approx(30.073706, abs=1e-5)


def test_marginal_offense_and_defense_hand_values() -> None:
    assert marginal_offense(51.229974, 0.78, 45.335557) == pytest.approx(18.697178, abs=1e-5)
    stop = stop_percentage(15.47616, 30000, 100, 6000)  # stops x team MIN / (poss x MIN)
    assert stop == pytest.approx(0.773808)
    drtg = individual_drtg(76, 76 / 33.6, stop)
    assert drtg == pytest.approx(71.03248, abs=1e-4)
    md = marginal_defense(6000, 30000, 100, 0.78, drtg)  # 0.2 x 100 x (1.08 x 0.78 - DRtg / 100)
    assert md == pytest.approx(2.6415, abs=1e-3)


def test_win_shares_hand_example() -> None:
    players, teams = _box()
    ws = win_shares(players, teams).set_index("player_id")
    assert ws.loc["A1", "points_produced"] == pytest.approx(51.229974, abs=1e-5)
    assert ws.loc["A1", "possessions_used"] == pytest.approx(45.335557, abs=1e-5)
    assert ws.loc["A1", "ows"] == pytest.approx(0.749086, abs=1e-5)
    assert ws.loc["A1", "dws"] == pytest.approx(0.105829, abs=1e-5)
    assert ws.loc["A1", "ws"] == pytest.approx(0.854915, abs=1e-5)
    assert ws.loc["A1", "ws40"] == pytest.approx(0.341966, abs=1e-5)  # 0.854915 / 100 x 40
    assert ws.loc["A2", "ows"] == pytest.approx(0.459031, abs=1e-5)
    assert ws.loc["A2", "dws"] == pytest.approx(0.013439, abs=1e-5)
    assert ws.loc["A3", "ows"] == pytest.approx(0.0)  # no shots, no assists
    assert ws.loc["A3", "dws"] == pytest.approx(-0.086404, abs=1e-5)
    assert ws.loc["B1", "ows"] == pytest.approx(0.633656, abs=1e-5)
    assert ws.loc["B1", "ws"] == pytest.approx(0.716707, abs=1e-5)
    assert ws.loc["B2", "dws"] == pytest.approx(-0.010567, abs=1e-5)
    assert ws.loc["B3", "dws"] == pytest.approx(-0.114356, abs=1e-5)


def test_league_offense_sums_to_points_over_points_per_win() -> None:
    # Sum of OWS = (sum PProd - 0.92 x league PPP x sum possessions used) / points per win.
    players, teams = _box()
    ws = win_shares(players, teams)
    marginal = ws["points_produced"].sum() - 0.92 * 0.78 * ws["possessions_used"].sum()
    assert ws["ows"].sum() == pytest.approx(marginal / PPW, abs=1e-9)


def test_team_sum_check() -> None:
    players, teams = _box()
    ws = win_shares(players, teams)
    sums = ws.groupby("team")["ws"].sum()
    assert sums["A"] == pytest.approx(1.068173, abs=1e-5)
    assert sums["B"] == pytest.approx(0.787362, abs=1e-5)
    check = team_check(ws, teams).iloc[0]
    assert check["teams"] == 2
    assert check["mae"] == pytest.approx((abs(sums["A"] - 1) + abs(sums["B"] - 0)) / 2, abs=1e-9)
    assert check["correlation"] == pytest.approx(1.0)  # the winner also has the larger WS sum
    assert check["ws_total"] == pytest.approx(sums.sum(), abs=1e-9)
    assert check["wins_total"] == 1


def test_box_win_shares_validates_and_drops_players_off_court() -> None:
    players, teams = _box()
    players.loc[players["player_id"] == "B5", "sec"] = 0
    out = box_win_shares(players, teams)
    assert "B5" not in set(out["player_id"])
    assert len(out) == 9


def test_fit_points_per_win_recovers_slope() -> None:
    rng = np.random.default_rng(1)
    diff = rng.uniform(-10, 10, size=300)
    win_pct = 0.5 + 0.02 * diff  # exact: 1 / 0.02 = 50 points per win
    frame = pd.DataFrame(
        {"games": 34, "wins": 34 * win_pct, "pf": 1000 + 34 * diff / 2, "pa": 1000 - 34 * diff / 2}
    )
    fit = fit_points_per_win(frame, resamples=200)
    assert fit.value == pytest.approx(50.0, rel=1e-9)
    assert fit.low <= fit.value + 1e-9
    assert fit.value - 1e-9 <= fit.high
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
