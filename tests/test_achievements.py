"""Furthest phase per club and player season (``stats/achievements.py``) on a synthetic league."""

import pandas as pd
import pytest

from eurohoops.stats.achievements import achievements_payload, final_game

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
    return {"season": season, "game_id": gid, "team": team, "player_id": pid}


# 2010: W beats R in the final; S and T are the semifinal losers (third place: S beats T).
# P3 loses a play-in game to P4 (P4 then reaches the playoffs); Z plays only the regular season.
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


def test_player_entries_follow_the_club_and_the_stage_he_played(
    payload: dict[str, object],
) -> None:
    players = payload["players"]
    assert isinstance(players, dict)
    # traded mid-season: one entry per club, each with the furthest stage he reached there
    assert players["P_T"] == [[2010, "A", "RS", 0], [2010, "W", "PO", 1], [2019, "A", "RS", 0]]
    # won the final: W; the cancelled 2019 season has no champion, so no flag there
    assert players["P_W"] == [[2010, "W", "W", 1], [2019, "W", "RS", 0]]
    # did not play the Final Four, still counts as a champion of the club
    assert players["P_N"] == [[2010, "W", "PO", 1]]
    # third-place game for a semifinal loser: FF
    assert players["P_S"] == [[2010, "S", "FF", 0]]
    # runner-up in the final: F
    assert players["P_R"] == [[2010, "R", "F", 0], [2019, "R", "RS", 0]]
    # play-in only: PI
    assert players["P_P3"] == [[2010, "P3", "PI", 0]]
    assert players["P_P4"] == [[2010, "P4", "PI", 0]]
    assert players["P_Z"] == [[2010, "Z", "RS", 0], [2019, "Z", "RS", 0]]


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
