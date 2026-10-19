"""Coaching style (stats/coach_style.py) on hand-made play-by-play and synthetic cache files."""

import gzip
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from eurohoops.stats.coach_style import (
    CHALLENGE_FROM,
    Action,
    StyleIndex,
    after_timeout,
    challenges,
    coach_style,
    game_style,
    game_styles,
    is_clutch,
    rotation,
)
from eurohoops.stats.coaches import coach_payloads

A, B = "AAA", "BBB"


def act(
    kind: str,
    team: str = "",
    *,
    period: int = 1,
    left: int | None = 500,
    score: tuple[int, int] | None = None,
) -> Action:
    return Action(period, left, kind, team, score)


def ato(*rows: Action) -> dict[str, tuple[int, int]]:
    return after_timeout(list(rows), (A, B))


# ---- after timeout: possession end rules ----


def test_def_rebound_by_the_other_team_ends_the_possession() -> None:
    result = ato(act("TOUT", A), act("2FGA", A), act("D", B), act("2FGM", A))
    assert result[A] == (1, 0)  # the basket after the rebound is B's possession


def test_turnover_ends_the_possession() -> None:
    result = ato(act("TOUT", A), act("D", A), act("TO", A), act("2FGM", B))
    assert result[A] == (1, 0)


def test_made_field_goal_ends_the_possession_and_scores_its_points() -> None:
    result = ato(act("TOUT", A), act("3FGM", A), act("D", B), act("2FGA", B))
    assert result[A] == (1, 3)


def test_and_one_keeps_the_ball_until_the_free_throw_is_made() -> None:
    result = ato(act("TOUT", A), act("2FGM", A), act("CM", B), act("FTM", A), act("D", B))
    assert result[A] == (1, 3)  # 2 + the and-one free throw, one possession


def test_last_free_throw_made_ends_the_possession() -> None:
    result = ato(act("TOUT", A), act("D", A), act("FTM", A), act("FTM", A), act("2FGA", B))
    assert result[A] == (1, 2)


def test_missed_last_free_throw_keeps_the_ball_until_a_rebound() -> None:
    kept = ato(act("TOUT", A), act("D", A), act("FTA", A), act("O", A), act("2FGM", A))
    assert kept[A] == (1, 2)
    lost = ato(act("TOUT", A), act("D", A), act("FTA", A), act("D", B))
    assert lost[A] == (1, 0)


def test_end_of_period_ends_the_possession() -> None:
    result = ato(act("TOUT", A), act("D", A), act("FTA", A), act("EP", period=1, left=0))
    assert result[A] == (1, 0)


def test_blocked_miss_is_still_the_shooters_possession() -> None:
    result = ato(act("TOUT", A), act("2FGAB", A), act("D", B))
    assert result[A] == (1, 0)


def test_dunk_and_layup_score_as_field_goals() -> None:
    result = ato(
        act("TOUT", A),
        act("D", A),
        act("DUNK", A),
        act("D", B),
        act("TOUT", A),
        act("D", A),
        act("LAYUPMD", A),
        act("D", B),
    )
    assert result[A] == (2, 4)


def test_the_run_starts_when_the_ball_reaches_the_timeout_team() -> None:
    # B has the ball when A calls timeout. B scores, the ball goes to A, A's possession starts.
    result = ato(
        act("2FGA", B),
        act("TOUT", A),
        act("2FGM", B),
        act("2FGM", A),
        act("D", B),
    )
    assert result[A] == (1, 2)
    assert result[B] == (0, 0)


def test_no_possession_for_a_timeout_team_while_the_other_team_has_the_ball() -> None:
    result = ato(act("D", A), act("TOUT", B), act("2FGA", A), act("D", B), act("2FGA", A))
    assert result[A] == (0, 0)
    assert result[B] == (1, 0)


def test_tv_timeouts_are_ignored() -> None:
    result = ato(act("TOUT_TV", A), act("D", A), act("TO", A))
    assert result[A] == (0, 0)


def test_a_timeout_inside_the_own_possession_does_not_restart_it() -> None:
    result = ato(act("TOUT", A), act("2FGA", A), act("TOUT", A), act("2FGM", A), act("D", B))
    assert result[A] == (1, 2)


def test_own_defensive_rebound_then_timeout_counts_as_the_after_timeout_possession() -> None:
    # A rebounds, calls timeout to draw up a play while holding the ball, then scores.
    result = ato(act("D", A), act("TOUT", A), act("2FGM", A), act("D", B))
    assert result[A] == (1, 2)


def test_foul_drawn_then_timeout_then_layup_counts_with_its_points() -> None:
    # A rebounds, B fouls A (no shot), A calls timeout while holding the ball, then A scores.
    result = ato(act("D", A), act("CM", B), act("TOUT", A), act("LAYUPMD", A), act("D", B))
    assert result[A] == (1, 2)


def test_points_before_the_timeout_do_not_count() -> None:
    # A and-one: A scores 2 before its timeout and still holds the ball; only the free throw
    # made after the timeout counts.
    result = ato(act("2FGM", A), act("CM", B), act("TOUT", A), act("FTM", A), act("D", B))
    assert result[A] == (1, 1)


def test_held_ball_timeout_then_turnover_is_a_zero_point_possession() -> None:
    result = ato(act("D", A), act("TOUT", A), act("TO", A), act("2FGM", B))
    assert result[A] == (1, 0)


def test_timeout_between_own_free_throws_is_not_an_after_timeout_possession() -> None:
    result = ato(act("FTM", A), act("TOUT", A), act("FTM", A), act("2FGA", B))
    assert result[A] == (0, 0)


def test_timeout_after_the_other_teams_turnover_counts_when_the_ball_comes_to_it() -> None:
    result = ato(act("TO", B), act("TOUT", A), act("2FGM", A), act("D", B))
    assert result[A] == (1, 2)


def test_two_waiting_timeouts_each_count_for_their_next_possession() -> None:
    # B scores, the ball goes to A. B calls timeout (waits), then A calls its own (has the ball).
    rows = [
        act("2FGM", B),
        act("TOUT", B),  # B waits for its possession
        act("TOUT", A),  # A has the ball from B's basket: its possession starts now
        act("2FGA", A),
        act("D", B),  # B gets the ball: B's possession, started by the timeout it waited for
        act("2FGM", B),
    ]
    result = ato(*rows)
    assert result[A] == (1, 0)
    assert result[B] == (1, 2)


def test_period_end_clears_a_waiting_timeout() -> None:
    # A calls timeout while B has the ball, the period ends, and A gets the ball in the next period:
    # that possession is not after the timeout.
    result = ato(
        act("2FGA", B, period=1, left=3),
        act("TOUT", A, period=1, left=1),
        act("EP", period=1, left=0),
        act("2FGM", B, period=2, left=600),
        act("2FGM", A, period=2, left=590),
        act("D", B, period=2, left=580),
    )
    assert result[A] == (0, 0)


# ---- clutch ----


def test_margin_within_five_carried_into_the_last_five_minutes_is_clutch() -> None:
    rows = [
        act("2FGM", A, period=4, left=330, score=(60, 58)),  # margin 2 at 5:30
        act("2FGA", B, period=4, left=290),  # at 4:50 the margin is still 2
    ]
    assert is_clutch(rows)


def test_margin_within_five_only_at_5_30_is_not_clutch() -> None:
    rows = [
        act("2FGM", A, period=4, left=330, score=(40, 35)),  # margin 5 at 5:30
        act("3FGM", A, period=4, left=320, score=(43, 35)),  # margin 8 at 5:20
        act("2FGA", B, period=4, left=290),
        act("EG", period=4, left=0),
    ]
    assert not is_clutch(rows)


def test_a_scoring_row_inside_the_window_that_closes_the_gap_is_clutch() -> None:
    rows = [
        act("2FGM", A, period=4, left=400, score=(50, 40)),  # margin 10 at 6:40
        act("3FGM", B, period=4, left=280, score=(50, 43)),  # margin 7 at 4:40
        act("2FGM", B, period=4, left=200, score=(50, 45)),  # margin 5 at 3:20
    ]
    assert is_clutch(rows)


def test_overtime_counts_when_the_game_was_tied_at_the_end_of_regulation() -> None:
    rows = [
        act("2FGM", A, period=4, left=400, score=(80, 80)),
        act("2FGA", B, period=4, left=350),
        act("2FGA", B, period=5, left=290),
    ]
    assert is_clutch(rows)


def test_overtime_with_a_big_margin_is_not_clutch() -> None:
    rows = [
        act("2FGM", A, period=4, left=400, score=(80, 60)),
        act("EG", period=4, left=0),
        act("2FGA", B, period=5, left=290),
    ]
    assert not is_clutch(rows)


def test_a_big_margin_in_the_last_five_minutes_is_not_clutch() -> None:
    rows = [
        act("2FGM", A, period=3, left=100, score=(70, 50)),
        act("2FGM", A, period=4, left=200, score=(80, 60)),
        act("EG", period=4, left=0),
    ]
    assert not is_clutch(rows)


# ---- challenges and rotation ----


def test_challenges_are_counted_by_team_and_late_ones_by_period() -> None:
    rows = [
        act("CCH", A, period=4, left=200),
        act("CCH", B, period=2, left=500),
        act("CCH", A, period=5, left=100),
    ]
    assert challenges(rows) == {A: (2, 2), B: (1, 0)}


def test_rotation_counts_players_with_minutes_and_the_top_seven_share() -> None:
    minutes = ["30:00", "25:00", "20:00", "18:00", "15:00", "10:00", "5:00", "2:00", "DNP", "0:00"]
    box = {"Stats": [{"Team": A, "PlayersStats": [{"Team": A, "Minutes": m} for m in minutes]}]}
    used, top7 = rotation(box)[A]
    assert used == 8
    assert top7 == pytest.approx(123 / 125)


# ---- cache-backed game style and the coach's figures ----


def _pbp(first: list[dict[str, Any]], fourth: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "FirstQuarter": first,
        "SecondQuarter": [],
        "ThirdQuarter": [],
        "ForthQuarter": fourth or [],
        "ExtraTime": [],
        "CodeTeamA": A,
        "CodeTeamB": B,
    }


def _row(kind: str, team: str, marker: str = "05:00", **points: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "PLAYTYPE": kind,
        "CODETEAM": team,
        "MARKERTIME": marker,
        "POINTS_A": None,
        "POINTS_B": None,
    }
    row.update(points)
    return row


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))


def _box(home_minutes: list[str]) -> dict[str, Any]:
    return {
        "Stats": [
            {"Team": A, "PlayersStats": [{"Team": A, "Minutes": m} for m in home_minutes]},
            {"Team": B, "PlayersStats": [{"Team": B, "Minutes": "20:00"}]},
        ]
    }


def test_game_style_reads_the_cached_play_by_play_and_box_score(tmp_path: Path) -> None:
    pbp = _pbp(
        [
            _row("TOUT", A, "09:00"),
            _row("D", A, "08:50"),
            _row("2FGM", A, "08:40", POINTS_A=2, POINTS_B=0),
            _row("TO", A, "08:00"),
            _row("CCH", A, "04:00"),
        ]
    )
    _write(tmp_path / "playbyplay" / "E2022" / "7.json.gz", pbp)
    _write(tmp_path / "boxscore" / "E2022" / "7.json.gz", _box(["30:00", "10:00"]))
    style = game_style(tmp_path, 2022, "7")
    assert style is not None
    assert style.teams[A].ato_possessions == 1  # the first possession after the timeout only
    assert style.teams[A].ato_points == 2
    assert style.teams[A].challenges == 1
    assert style.teams[A].challenges_late == 0
    assert style.teams[A].players_used == 2
    assert style.clutch is False  # no fourth-quarter rows, so nothing inside the window


def test_game_styles_and_coach_figures_compare_with_the_league(tmp_path: Path) -> None:
    _write(
        tmp_path / "playbyplay" / "E2022" / "1.json.gz",
        _pbp([_row("TOUT", A, "09:00"), _row("TO", A, "08:00")]),
    )
    _write(tmp_path / "boxscore" / "E2022" / "1.json.gz", _box(["25:00", "25:00"]))
    _write(
        tmp_path / "playbyplay" / "E2022" / "2.json.gz",
        _pbp([_row("TOUT", B, "09:00"), _row("2FGM", B, "08:00", POINTS_A=0, POINTS_B=2)]),
    )
    _write(tmp_path / "boxscore" / "E2022" / "2.json.gz", _box(["20:00"]))
    games = pd.DataFrame(
        [
            {
                "season": 2022,
                "game_id": "E2022_1",
                "game_code": "1",
                "played": True,
                "forfeit": False,
            },
            {
                "season": 2022,
                "game_id": "E2022_2",
                "game_code": "2",
                "played": True,
                "forfeit": False,
            },
        ]
    )
    index = game_styles(tmp_path, games)
    rows = pd.DataFrame([{"season": 2022, "game_id": "E2022_1", "team": A, "won": True}])
    block = coach_style(rows, index)
    assert block["ato"] == {"possessions": 1, "points": 0, "ppp": 0.0, "league_ppp": 1.0}
    assert block["clutch"]["team_games"] == 1
    assert block["clutch"]["games"] == 0
    assert block["rotation"]["players_per_game"] == 2.0
    # four team-games with a box score: A 2 + B 1 in game 1, A 1 + B 1 in game 2
    assert block["rotation"]["league_players_per_game"] == 1.25
    # 2021-22 is in the challenge window: the coach's team-game counts, with none made
    assert block["challenges"]["games"] == 1
    assert block["challenges"]["per_game"] == 0.0
    assert block["challenges"]["late_share"] is None
    assert CHALLENGE_FROM == 2021


def test_coach_with_no_style_games_gets_empty_figures() -> None:
    index = StyleIndex(games={}, seasons={})
    rows = pd.DataFrame([{"season": 2015, "game_id": "E2015_9", "team": A, "won": False}])
    block = coach_style(rows, index)
    assert block["ato"] == {"possessions": 0, "points": 0, "ppp": None, "league_ppp": None}
    assert block["clutch"]["games"] == 0
    assert block["clutch"]["team_games"] == 0
    assert block["challenges"] is None


def test_coach_payloads_carry_the_style_block_per_coach() -> None:
    rows = pd.DataFrame(
        [
            {
                "season": 2022,
                "game_id": "E2022_1",
                "tipoff_utc": "2022-10-06T18:00:00Z",
                "team": A,
                "opponent": B,
                "home": True,
                "won": True,
                "p_win": 0.5,
                "slug": "john-smith",
                "name": "John Smith",
            }
        ]
    )
    with_style = coach_payloads(rows, {}, {}, StyleIndex(games={}, seasons={}))
    assert with_style["coaches/john-smith.json"]["style"]["ato"]["possessions"] == 0
    without = coach_payloads(rows, {}, {})
    assert without["coaches/john-smith.json"]["style"] is None
