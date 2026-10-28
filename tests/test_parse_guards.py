"""Malformed EuroLeague payloads must raise or be flagged, never read as valid data (item 12)."""

import copy
import gzip
import json

import pytest

from eurohoops.parse.games import parse_schedule
from eurohoops.parse.schemas import box_count
from eurohoops.parse.stints import box_facts
from eurohoops.parse.team_box import euroleague_lines
from tests.conftest import FIXTURES, load_fixture


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


def box_fixture() -> dict:
    return json.loads(gzip.open(FIXTURES / "stats_raw/boxscore/E2010/1.json.gz").read())


@pytest.mark.parametrize("value", [80.5, "80.5", True, "8O", None])
def test_a_box_count_that_is_not_a_whole_number_raises(value: object) -> None:
    with pytest.raises(ValueError):
        box_count(value)


@pytest.mark.parametrize(("value", "want"), [(80, 80), (80.0, 80), ("80", 80), (" 80 ", 80)])
def test_a_whole_box_count_is_read_exactly(value: object, want: int) -> None:
    assert box_count(value) == want


def test_a_fractional_points_total_is_rejected_by_both_box_readers() -> None:
    box = box_fixture()
    box["Stats"][0]["totr"]["Points"] = 80.5  # truncation used to read this as 80
    with pytest.raises(ValueError, match=r"80.5"):
        euroleague_lines(box)
    with pytest.raises(ValueError, match=r"80.5"):
        box_facts(box)


def test_the_committed_box_score_still_reads() -> None:
    lines, minutes = euroleague_lines(box_fixture())
    assert set(lines) == {"KHI", "SOP"} and minutes == 40.0
