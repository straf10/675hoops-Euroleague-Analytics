from datetime import date

import pytest

from eurohoops.config import season_for


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 7, 31), "2025-26"),
        (date(2026, 8, 1), "2026-27"),
        (date(2026, 10, 1), "2026-27"),
        (date(2026, 12, 31), "2026-27"),
        (date(2027, 1, 1), "2026-27"),
        (date(2027, 7, 31), "2026-27"),
        (date(2027, 8, 1), "2027-28"),
    ],
)
def test_season_for_switches_on_1_august(day: date, expected: str) -> None:
    assert season_for(day) == expected
