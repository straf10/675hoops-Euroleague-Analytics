"""Malformed EuroLeague payloads must raise or be flagged, never read as valid data (item 12)."""

import copy

import pytest

from eurohoops.parse.games import parse_schedule
from tests.conftest import load_fixture


def first_game() -> dict:
    return copy.deepcopy(load_fixture("schedule_E2024.json")[0])


@pytest.mark.parametrize("key", ["played", "isNeutralVenue", "confirmedDate"])
def test_a_string_flag_is_rejected_not_read_as_true(key: str) -> None:
    game = first_game()
    game[key] = "false"  # a non-empty string is truthy: it would read as true
    with pytest.raises(ValueError, match=f"{key} is 'false', not a boolean"):
        parse_schedule(2024, [game])


def test_a_tipoff_without_a_timezone_is_rejected() -> None:
    game = first_game()
    game["utcDate"] = game["utcDate"].removesuffix("Z")  # local-looking, zone unknown
    with pytest.raises(ValueError, match="has no timezone"):
        parse_schedule(2024, [game])


def test_an_explicit_offset_is_accepted() -> None:
    game = first_game()
    game["utcDate"] = game["utcDate"].removesuffix("Z") + "+00:00"
    assert parse_schedule(2024, [game]).loc[0, "tipoff_utc"].hour == 16


@pytest.mark.parametrize("side", ["local", "road"])
def test_a_padded_club_code_is_rejected(side: str) -> None:
    game = first_game()
    game[side]["club"]["code"] = game[side]["club"]["code"] + " "
    with pytest.raises(ValueError, match="is not a clean code"):
        parse_schedule(2024, [game])
