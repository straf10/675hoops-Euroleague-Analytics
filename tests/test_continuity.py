"""Returning-minutes share: pure functions, no cache needed."""

import pandas as pd
import pytest

from eurohoops.models.continuity import club_share, player_continuity


def _minutes(rows: list[tuple[int, str, str, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["season", "team", "player_id", "sec"])


def _roster(rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["club", "player_id"])


def _shares(minutes: pd.DataFrame, roster: pd.DataFrame, season: int = 2025) -> dict[str, float]:
    clubs = club_share(player_continuity(minutes, roster, season))
    return dict(zip(clubs["team"], clubs["share"], strict=True))


def test_a_club_with_all_players_back_is_one_hundred_percent() -> None:
    minutes = _minutes([(2024, "PAM", "P1", 1200), (2024, "PAM", "P2", 600)])
    roster = _roster([("PAM", "P1"), ("PAM", "P2"), ("PAM", "P3")])
    assert _shares(minutes, roster) == {"PAM": pytest.approx(1.0)}


def test_the_share_weights_by_minutes_not_by_head_count() -> None:
    # A 25-minute starter leaves; a 1-minute player stays.
    minutes = _minutes([(2024, "OLY", "STAR", 1500), (2024, "OLY", "BENCH", 60)])
    roster = _roster([("OLY", "BENCH")])
    assert _shares(minutes, roster) == {"OLY": pytest.approx(60 / 1560)}


def test_a_new_club_with_no_previous_season_has_no_value() -> None:
    minutes = _minutes([(2024, "PAM", "P1", 1200), (2025, "NEW", "N1", 900)])
    roster = _roster([("NEW", "N1")])
    assert "NEW" not in _shares(minutes, roster)


def test_a_player_who_moved_counts_for_the_new_club_only() -> None:
    # P1 played for OLY in 2024 and has moved to PAM. His 2024 minutes are OLY's, so he is a
    # departure there; PAM gets no credit for minutes it did not have.
    minutes = _minutes(
        [(2024, "OLY", "P1", 1000), (2024, "OLY", "P2", 1000), (2024, "PAM", "P3", 1000)]
    )
    roster = _roster([("PAM", "P1"), ("OLY", "P2"), ("PAM", "P3")])
    shares = _shares(minutes, roster)
    assert shares["OLY"] == pytest.approx(0.5)
    assert shares["PAM"] == pytest.approx(1.0)
    players = player_continuity(minutes, roster, 2025).set_index("player_id")
    assert not bool(players.loc["P1", "returning"])
    assert players.loc["P1", "team"] == "OLY"


def test_last_season_sums_every_line_and_ignores_older_seasons() -> None:
    # Regular season and playoff lines for one player add up; 2023 is not last season for 2025.
    minutes = _minutes(
        [(2024, "PAM", "P1", 1000), (2024, "PAM", "P1", 300), (2023, "PAM", "P9", 5000)]
    )
    players = player_continuity(minutes, _roster([("PAM", "P1")]), 2025)
    assert list(players["player_id"]) == ["P1"]
    assert int(players["last_sec"].iloc[0]) == 1300


def test_a_first_season_has_no_players_and_no_clubs() -> None:
    minutes = _minutes([(2010, "PAM", "P1", 1200)])
    players = player_continuity(minutes, _roster([("PAM", "P1")]), 2010)
    assert players.empty and club_share(players).empty
