"""Item 14: the daylight-saving switches of Europe/Athens (2026-10-25 and 2027-03-28, both at
01:00 UTC) must not move a forecast across its tip-off, a game into or out of a round, or a game
onto another day. Every guard compares UTC instants, and the Athens zone only labels the dates."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from eurohoops.parse.games import ATHENS
from eurohoops.predict import LatePredictionError, refuse_late, upcoming_games
from eurohoops.tipoff import first_tipoff_on


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def test_the_late_guard_uses_instants_across_the_october_switch() -> None:
    tipoff = pd.Timestamp("2026-10-25T01:30:00Z")  # 03:30 EET, the second 03:30 of that night
    refuse_late(utc("2026-10-25T01:29:59"), [("g", tipoff)])  # just before: allowed
    with pytest.raises(LatePredictionError):
        refuse_late(utc("2026-10-25T01:30:00"), [("g", tipoff)])


def test_the_late_guard_uses_instants_across_the_march_switch() -> None:
    tipoff = pd.Timestamp("2027-03-28T01:00:00Z")  # 04:00 EEST, the clocks jump from 03:00 EET
    refuse_late(utc("2027-03-28T00:59:59"), [("g", tipoff)])
    with pytest.raises(LatePredictionError):
        refuse_late(utc("2027-03-28T01:00:00"), [("g", tipoff)])


def _round(season: int, tipoff: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [season],
            "confirmed_date": [True],
            "played": [False],
            "phase": ["RS"],
            "round": [9],
            "tipoff_utc": pd.to_datetime([tipoff], utc=True),
        }
    )


def test_a_game_across_the_october_switch_is_selected_by_instant() -> None:
    games = _round(2026, "2026-10-25T01:30:00Z")
    lead = timedelta(hours=1)
    assert upcoming_games(games, 2026, utc("2026-10-25T00:45:00"), lead).tolist() == [True]
    assert upcoming_games(games, 2026, utc("2026-10-25T01:31:00"), lead).tolist() == [False]


def test_a_game_across_the_march_switch_is_selected_by_instant() -> None:
    games = _round(2027, "2027-03-28T01:00:00Z")
    lead = timedelta(hours=1)
    assert upcoming_games(games, 2027, utc("2027-03-28T00:30:00"), lead).tolist() == [True]
    assert upcoming_games(games, 2027, utc("2027-03-28T01:01:00"), lead).tolist() == [False]


def test_athens_labels_follow_the_offset_on_each_side_of_each_switch() -> None:
    stamps = pd.Series(
        pd.to_datetime(
            [
                "2026-10-25T00:30:00Z",  # EEST, +03:00
                "2026-10-25T01:30:00Z",  # EET, +02:00 (the same clock hour, again)
                "2027-03-28T00:59:00Z",  # EET, +02:00
                "2027-03-28T01:00:00Z",  # EEST, +03:00
            ],
            utc=True,
        )
    )
    local = stamps.dt.tz_convert(ATHENS)
    assert local.dt.strftime("%Y-%m-%dT%H:%M%z").tolist() == [
        "2026-10-25T03:30+0300",
        "2026-10-25T03:30+0200",
        "2027-03-28T02:59+0200",
        "2027-03-28T04:00+0300",
    ]
    assert local.dt.strftime("%Y-%m-%d").tolist() == [
        "2026-10-25",
        "2026-10-25",
        "2027-03-28",
        "2027-03-28",
    ]


def test_first_tipoff_of_a_utc_day_is_the_earlier_instant_across_the_switch() -> None:
    games = pd.DataFrame(
        {
            "tipoff_utc": pd.to_datetime(
                ["2026-10-24T23:30:00Z", "2026-10-25T01:30:00Z"], utc=True
            ),
            "confirmed_date": [True, True],
            "played": [False, False],
        }
    )
    assert first_tipoff_on(games, datetime(2026, 10, 25).date()) == utc("2026-10-25T01:30:00")
    assert first_tipoff_on(games, datetime(2026, 10, 24).date()) == utc("2026-10-24T23:30:00")
