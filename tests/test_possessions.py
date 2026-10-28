"""Possessions: the box formula (hand-computed on real box scores) and the EuroLeague PBP count."""

import json
from typing import Any

import pytest

from eurohoops.parse.possessions import box_possessions, count_possessions, possession_ends
from eurohoops.parse.stints import Event, events
from eurohoops.parse.team_box import euroleague_lines
from tests.conftest import FIXTURES


def test_box_formula_on_a_real_euroleague_box_score() -> None:
    """E2023_1, RED 94-73 ASV. RED: FGA 37 + 34 = 71, OREB 17, TOV 10, FTA 13
    -> 71 - 17 + 10 + 0.42 * 13 = 69.46. ASV: 29 + 25 - 9 + 16 + 0.42 * 21 = 69.82."""
    box = json.loads((FIXTURES / "box_E2023_1.json").read_text(encoding="utf-8"))
    parsed = euroleague_lines(box)
    assert not isinstance(parsed, str)
    lines, minutes = parsed
    assert minutes == 40.0
    red, asv = lines["RED"], lines["ASV"]
    assert (red["points"], red["fga"], red["oreb"], red["tov"], red["fta"]) == (94, 71, 17, 10, 13)
    assert box_possessions(red["fga"], red["oreb"], red["tov"], red["fta"]) == pytest.approx(
        69.46, abs=1e-12
    )
    assert box_possessions(asv["fga"], asv["oreb"], asv["tov"], asv["fta"]) == pytest.approx(
        69.82, abs=1e-12
    )


def test_team_rebounds_and_turnovers_are_in_the_euroleague_totals() -> None:
    box = json.loads((FIXTURES / "box_E2023_1.json").read_text(encoding="utf-8"))
    red = box["Stats"][0]
    players = sum(p["OffensiveRebounds"] for p in red["PlayersStats"])
    assert red["totr"]["OffensiveRebounds"] == players + red["tmr"]["OffensiveRebounds"] == 17
    assert red["tmr"]["OffensiveRebounds"] == 2


def ev(kind: str, team: str = "", clock: int = 0, period: int = 1) -> Event:
    return Event(period=period, elapsed=clock, kind=kind, team=team, player="")


TEAMS = ("AAA", "BBB")


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([ev("2FGM", "AAA", 10)], {"AAA": 1, "BBB": 0}),
        ([ev("3FGA", "AAA", 10), ev("D", "BBB", 11)], {"AAA": 1, "BBB": 0}),
        # An offensive rebound continues the possession; the putback ends it.
        ([ev("2FGA", "AAA", 10), ev("O", "AAA", 11), ev("2FGM", "AAA", 12)], {"AAA": 1, "BBB": 0}),
        ([ev("TO", "BBB", 10)], {"AAA": 0, "BBB": 1}),
        # A two-shot trip ends at its last free throw; substitutions in between change nothing.
        ([ev("FTM", "AAA", 10), ev("IN", "AAA", 10), ev("FTM", "AAA", 10)], {"AAA": 1, "BBB": 0}),
        # A missed last free throw waits for the rebound.
        ([ev("FTM", "AAA", 10), ev("FTA", "AAA", 10), ev("D", "BBB", 10)], {"AAA": 1, "BBB": 0}),
        ([ev("FTM", "AAA", 10), ev("FTA", "AAA", 10), ev("O", "AAA", 10)], {"AAA": 0, "BBB": 0}),
        # And-one: the made field goal already ended the possession.
        ([ev("2FGM", "AAA", 10), ev("CM", "BBB", 10), ev("FTM", "AAA", 10)], {"AAA": 1, "BBB": 0}),
        # Technical and unsportsmanlike free throws end nothing.
        ([ev("CMT", "BBB", 10), ev("FTM", "AAA", 10)], {"AAA": 0, "BBB": 0}),
        ([ev("CMU", "BBB", 10), ev("FTM", "AAA", 10), ev("FTM", "AAA", 10)], {"AAA": 0, "BBB": 0}),
        # A miss nobody rebounds before the buzzer ends the possession at the period end.
        ([ev("3FGA", "AAA", 599), ev("EP")], {"AAA": 1, "BBB": 0}),
        ([ev("FTA", "AAA", 599), ev("2FGM", "BBB", 600, period=2)], {"AAA": 1, "BBB": 1}),
        # A defensive rebound without a preceding miss (e.g. a logging slip) ends nothing.
        ([ev("D", "BBB", 10)], {"AAA": 0, "BBB": 0}),
        # A second trip closes the first.
        ([ev("FTM", "AAA", 10), ev("FTM", "BBB", 20)], {"AAA": 1, "BBB": 1}),
    ],
)
def test_pbp_possession_ends(rows: list[Event], expected: dict[str, int]) -> None:
    assert count_possessions(rows, TEAMS) == expected


def test_a_trip_ends_at_its_last_free_throw() -> None:
    rows = [ev("FTM", "AAA", 10), ev("OUT", "AAA", 10), ev("FTM", "AAA", 10), ev("IN", "BBB", 10)]
    (end,) = possession_ends(rows, TEAMS)
    assert (end.index, end.team) == (2, "AAA")


def test_events_from_other_teams_are_ignored() -> None:
    assert count_possessions([ev("2FGM", "N/D", 10)], TEAMS) == {"AAA": 0, "BBB": 0}


def pbp_rows(rows: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "FirstQuarter": [
            {"PLAYTYPE": k, "CODETEAM": t, "PLAYER_ID": "", "MARKERTIME": c, "MINUTE": 1}
            for k, t, c in rows
        ]
    }


def test_pbp_count_on_raw_rows() -> None:
    pbp = pbp_rows(
        [("BP", "", ""), ("2FGAB", "AAA", "09:50"), ("D", "BBB", "09:48"), ("EP", "", "")]
    )
    assert count_possessions(events(pbp), TEAMS) == {"AAA": 1, "BBB": 0}
