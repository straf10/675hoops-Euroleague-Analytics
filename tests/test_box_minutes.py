"""The minutes rule: a team-side whose minutes miss 5 x game length, while PBP on-court time hits
it exactly, takes each mismatched player's PBP minutes (parse.box._minutes_from_pbp)."""

import pandas as pd

from eurohoops.parse.box import _Game, _minutes_from_pbp
from eurohoops.parse.esake import BoxLine

GAME = _Game("G1", 2019, "00000001", ("HOM", "AWY"), (80, 70))


def _line(player_id: str, points: int, seconds: int, fg2a: int = 0) -> BoxLine:
    return BoxLine(player_id, points, 0, fg2a, 0, 0, 0, 0, seconds)


def _pbp(rows: list[tuple[str, int, int, int]]) -> pd.DataFrame:
    """Rows of (side, points, fg2a, seconds); numbers and names are made up per row."""
    records = []
    for index, (side, points, fg2a, seconds) in enumerate(rows):
        records.append(
            {
                "side": side,
                "number": str(index),
                "player": f"P{index}",
                "points": points,
                "fg2m": 0,
                "fg2a": fg2a,
                "fg3m": 0,
                "fg3a": 0,
                "ftm": 0,
                "fta": 0,
                "seconds": seconds,
            }
        )
    return pd.DataFrame(records)


def test_mismatched_minutes_are_replaced_from_pbp_and_logged() -> None:
    # ESAKE home sums to 11000 (short 1000); PBP home is exactly 12000: A +400 and D +600.
    home = (
        _line("A", 10, 2400, fg2a=3),
        _line("B", 8, 2400, fg2a=2),
        _line("C", 6, 2000, fg2a=4),
        _line("D", 4, 2000, fg2a=1),
        _line("E", 2, 2200, fg2a=5),
    )
    away = (_line("X", 70, 12000, fg2a=9),)
    pbp = _pbp(
        [
            ("home", 10, 3, 2800),
            ("home", 8, 2, 2400),
            ("home", 6, 4, 2000),
            ("home", 4, 1, 2600),
            ("home", 2, 5, 2200),
            ("away", 70, 9, 12000),
        ]
    )
    new, log = _minutes_from_pbp(GAME, (home, away), pbp, [])
    assert sum(line.seconds for line in new[0]) == 12000
    assert new[1] == away  # the away side already sums to 5 x 2400: untouched
    assert [row["fix"] for row in log] == ["replaced_from_pbp", "replaced_from_pbp"]
    assert {row["player_id"]: (row["raw_seconds"], row["seconds"]) for row in log} == {
        "A": (2400, 2800),
        "D": (2000, 2600),
    }


def test_a_side_that_cannot_be_closed_is_logged_and_left_alone() -> None:
    # PBP home is exact (12000) and A and B differ, but +400 +400 cannot close an 8000 s gap.
    home = (_line("A", 10, 2000, fg2a=3), _line("B", 8, 2000, fg2a=2))
    pbp = _pbp(
        [
            ("home", 10, 3, 2400),
            ("home", 8, 2, 2400),
            ("home", 0, 0, 3600),
            ("home", 0, 0, 3600),
            ("away", 1, 0, 12000),
        ]
    )
    new, log = _minutes_from_pbp(GAME, (home, (_line("X", 1, 12000),)), pbp, [])
    assert new[0] == home
    assert [(row["team"], row["fix"]) for row in log] == [("HOM", "not_applied")]


def test_pbp_that_is_not_exact_changes_nothing() -> None:
    home = (_line("A", 10, 2000, fg2a=3),)
    pbp = _pbp([("home", 10, 3, 2000), ("away", 1, 0, 11999)])
    new, log = _minutes_from_pbp(GAME, (home, (_line("X", 1, 12000),)), pbp, [])
    assert new[0] == home and log == []


def test_a_sum_within_one_minute_is_not_checked() -> None:
    # ESAKE 11950 is within a minute of 12000, so the side is not checked even though PBP is exact.
    home = (
        _line("A", 10, 2390, fg2a=3),
        _line("B", 8, 2390, fg2a=2),
        _line("C", 6, 2390, fg2a=4),
        _line("D", 4, 2390, fg2a=1),
        _line("E", 2, 2390, fg2a=5),
    )
    pbp = _pbp(
        [
            ("home", 10, 3, 2400),
            ("home", 8, 2, 2400),
            ("home", 6, 4, 2400),
            ("home", 4, 1, 2400),
            ("home", 2, 5, 2400),
            ("away", 1, 0, 12000),
        ]
    )
    new, log = _minutes_from_pbp(GAME, (home, (_line("X", 1, 12000),)), pbp, [])
    assert new[0] == home and log == []
