"""Furthest phase per club and player season (``stats/achievements.py``) on a synthetic league."""

import pandas as pd
import pytest

from eurohoops.stats.achievements import achievements_payload, final_game, stat_titles

LIVE = 2030
DAY1 = pd.Timestamp("2010-06-01", tz="UTC")
DAY2 = pd.Timestamp("2010-06-03", tz="UTC")


def game(  # noqa: PLR0917 -- one row of the games table, positional for brevity
    gid: str, season: int, phase: str, when: pd.Timestamp, home: str, away: str, hs: int, aws: int
) -> dict[str, object]:
    return {
        "game_id": gid,
        "season": season,
        "phase": phase,
        "tipoff_utc": when,
        "home": home,
        "away": away,
        "home_score": hs,
        "away_score": aws,
        "played": True,
    }


def line(season: int, gid: str, team: str, pid: str) -> dict[str, object]:
    return {
        "season": season,
        "game_id": gid,
        "team": team,
        "player_id": pid,
        "sec": 1200,
        "pts": 0,
        "oreb": 0,
        "dreb": 0,
        "ast": 0,
        "stl": 0,
        "blk": 0,
        "pir": 0,
    }


def box_line(  # noqa: PLR0917 -- positional for brevity
    season: int, pid: str, n: int, sec: int, pts: int, oreb: int = 0, dreb: int = 0
) -> list[dict[str, object]]:
    """``n`` games for one player, each with the same stat line."""
    return [
        {
            **line(season, f"{pid}-{season}-{i}", "T", pid),
            "sec": sec,
            "pts": pts,
            "oreb": oreb,
            "dreb": dreb,
        }
        for i in range(n)
    ]


# 2010: W beats R in the final; S and T are the semifinal losers (third place: S beats T).
# P3 loses a play-in game to P4 (P4 then reaches the playoffs); Z plays only the regular season.
# P_N only plays a playoff game for W, so he gets W's stage (the title) without a Final Four game.
GAMES = pd.DataFrame(
    [
        game("RS1", 2010, "RS", DAY1, "W", "Z", 80, 70),
        game("RS2", 2010, "RS", DAY1, "A", "W", 70, 75),
        game("RS3", 2010, "RS", DAY1, "A", "R", 81, 79),
        game("PI1", 2010, "PI", DAY1, "P3", "P4", 60, 66),
        game("PO1", 2010, "PO", DAY1, "W", "X", 90, 80),
        game("PO2", 2010, "PO", DAY1, "R", "Y", 88, 70),
        game("PO3", 2010, "PO", DAY1, "S", "P4", 75, 72),
        game("PO4", 2010, "PO", DAY1, "T", "A", 77, 71),
        game("FF1", 2010, "FF", DAY1, "W", "S", 82, 76),  # semifinal
        game("FF2", 2010, "FF", DAY1, "R", "T", 74, 70),  # semifinal
        game("FF3", 2010, "FF", DAY2, "S", "T", 69, 64),  # third place
        game("FF4", 2010, "FF", DAY2, "W", "R", 85, 79),  # final
        # 2019: cancelled after the regular season, no playoffs and no Final Four
        game("RS5", 2019, "RS", DAY1, "Z", "W", 70, 72),
        game("RS6", 2019, "RS", DAY1, "A", "R", 60, 66),
        # before the window: not exported
        game("RS7", 2005, "RS", DAY1, "A", "Z", 70, 60),
        # the live season is not finished: not exported
        game("RS8", LIVE, "RS", DAY1, "W", "A", 70, 60),
    ]
)
BOX = pd.DataFrame(
    [
        line(2010, "RS1", "W", "P_W"),
        line(2010, "RS1", "Z", "P_Z"),
        # P_T is traded from A to W after the first regular-season game
        line(2010, "RS2", "A", "P_T"),
        line(2010, "RS2", "W", "P_W"),
        line(2010, "RS3", "A", "P_T"),
        line(2010, "RS3", "R", "P_R"),
        line(2010, "PI1", "P3", "P_P3"),
        line(2010, "PI1", "P4", "P_P4"),
        line(2010, "PO1", "W", "P_T"),
        line(2010, "PO1", "W", "P_W"),
        # P_N plays the playoffs for W but sits out the Final Four
        line(2010, "PO1", "W", "P_N"),
        line(2010, "FF1", "W", "P_W"),
        line(2010, "FF1", "S", "P_S"),
        line(2010, "FF3", "S", "P_S"),
        line(2010, "FF4", "W", "P_W"),
        line(2010, "FF4", "R", "P_R"),
        line(2019, "RS5", "Z", "P_Z"),
        line(2019, "RS5", "W", "P_W"),
        line(2019, "RS6", "A", "P_T"),
        line(2019, "RS6", "R", "P_R"),
        line(2005, "RS7", "A", "P_OLD"),
    ]
)


@pytest.fixture(scope="module")
def payload() -> dict[str, object]:
    return achievements_payload(GAMES, BOX, LIVE)


def test_seasons_start_in_2007_and_stop_before_the_live_season(payload: dict[str, object]) -> None:
    assert payload["seasons"] == [2010, 2019]


def test_club_codes_cover_every_stage(payload: dict[str, object]) -> None:
    clubs = payload["clubs"]
    assert isinstance(clubs, dict)
    assert clubs["2010"] == {
        "A": "PO",  # lost in the playoffs (PO4)
        "P3": "PI",  # lost in the play-in and never reached the playoffs
        "P4": "PO",  # won the play-in, lost in the playoffs
        "R": "F",  # lost the final
        "S": "FF",  # third place
        "T": "FF",  # fourth place
        "W": "W",  # champion
        "X": "PO",
        "Y": "PO",
        "Z": "RS",  # only regular-season games
    }


def test_cancelled_season_has_no_champion_and_no_final(payload: dict[str, object]) -> None:
    clubs = payload["clubs"]
    assert isinstance(clubs, dict)
    assert set(clubs["2019"].values()) == {"RS"}
    players = payload["players"]
    assert isinstance(players, dict)
    assert all(
        entry[3] == 0 for entries in players.values() for entry in entries if entry[0] == 2019
    )


def test_player_entries_take_the_club_season_stage_for_every_club_he_played_for(
    payload: dict[str, object],
) -> None:
    players = payload["players"]
    assert isinstance(players, dict)
    # traded mid-season: one entry per club he played for, each with that club's furthest stage
    # (A reached the playoffs in 2010; P_T played no playoff game for A, still gets PO)
    assert players["P_T"] == [
        [2010, "A", "PO", 0],
        [2010, "W", "W", 1],
        [2019, "A", "RS", 0],
    ]
    # won the final: W; the cancelled 2019 season has no champion, so no flag there
    assert players["P_W"] == [[2010, "W", "W", 1], [2019, "W", "RS", 0]]
    # played only a playoff game for the champion, sat out the Final Four: still W
    assert players["P_N"] == [[2010, "W", "W", 1]]
    # third-place game for a semifinal loser: FF
    assert players["P_S"] == [[2010, "S", "FF", 0]]
    # runner-up in the final: F
    assert players["P_R"] == [[2010, "R", "F", 0], [2019, "R", "RS", 0]]
    # play-in only: PI; P4 won the play-in, so its club-season stage is PO for him too
    assert players["P_P3"] == [[2010, "P3", "PI", 0]]
    assert players["P_P4"] == [[2010, "P4", "PO", 0]]
    assert players["P_Z"] == [[2010, "Z", "RS", 0], [2019, "Z", "RS", 0]]


def test_a_player_gets_the_club_stage_even_without_a_game_in_that_stage() -> None:
    box = pd.DataFrame([line(2010, "RS1", "Z", "P_LONE")])
    lone = achievements_payload(GAMES, box, LIVE)
    players = lone["players"]
    assert isinstance(players, dict)
    assert players["P_LONE"] == [[2010, "Z", "RS", 0]]


def test_players_outside_the_window_are_not_exported(payload: dict[str, object]) -> None:
    assert "P_OLD" not in payload["players"]


def test_final_is_the_game_between_the_semifinal_winners() -> None:
    played = GAMES[GAMES["season"] == 2010]
    game_id, champion, runner_up = final_game(played)
    assert (game_id, champion, runner_up) == ("FF4", "W", "R")


def test_a_final_four_without_a_game_between_the_winners_is_rejected() -> None:
    broken = pd.concat(
        [
            GAMES[GAMES["game_id"].isin(["FF1", "FF2"])],
            # a third game between the two semifinal losers instead of the final
            pd.DataFrame([game("FFX", 2010, "FF", DAY2, "S", "T", 60, 58)]),
        ]
    )
    with pytest.raises(ValueError, match="semifinal winners"):
        final_game(broken)


def test_a_short_final_four_is_rejected() -> None:
    with pytest.raises(ValueError, match="played games"):
        final_game(GAMES[GAMES["game_id"].isin(["FF1", "FF2"])])


def test_stat_titles_go_to_the_season_leader_among_the_qualified_players() -> None:
    rows = [
        *box_line(2010, "P_A", 4, 600, 10, dreb=3),  # 10 points, 3 rebounds a game
        *box_line(2010, "P_B", 4, 600, 15, oreb=2),  # ties P_D on points
        *box_line(2010, "P_D", 4, 600, 15),
        *box_line(2010, "P_C", 4, 300, 30),  # 5 minutes a game: unqualified
        *box_line(2010, "P_E", 1, 600, 40),  # one game when the season's most is 8: unqualified
        *box_line(2010, "P_F", 8, 600, 8),  # sets the season's most games
        *box_line(2030, "P_G", 8, 600, 50),  # a season outside the ones asked for
    ]
    titles = stat_titles(pd.DataFrame(rows), [2010])
    assert [2010, "pts"] in titles["P_B"]
    assert [2010, "pts"] in titles["P_D"]
    assert [2010, "reb"] in titles["P_A"]
    assert "P_C" not in titles
    assert "P_E" not in titles
    assert "P_G" not in titles


def test_stat_titles_are_per_game_and_rebounds_add_both_kinds() -> None:
    # P_R: 4 rebounds a game over 10 games; P_S: 7 a game over 4 games, so P_S leads
    rows = [
        *box_line(2011, "P_R", 10, 600, 0, oreb=2, dreb=2),
        *box_line(2011, "P_S", 4, 600, 0, oreb=4, dreb=3),
    ]
    titles = stat_titles(pd.DataFrame(rows), [2011])
    assert titles["P_S"] == [[2011, "reb"]]
    assert "P_R" not in titles


def test_a_stat_nobody_has_gives_no_title() -> None:
    titles = stat_titles(pd.DataFrame(box_line(2012, "P_Z", 4, 600, 0)), [2012])
    assert titles == {}


def test_the_payload_carries_stat_titles() -> None:
    payload = achievements_payload(GAMES, BOX, LIVE)
    assert isinstance(payload["stat_titles"], dict)
