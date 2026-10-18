from typing import Any

import pandas as pd
import pytest

from eurohoops.stats.units import (
    MIN_PAIR_SECONDS,
    MIN_UNIT_SECONDS,
    half_width,
    net_rating,
    possession_sd,
    units_by_season,
)

HOME = ["a", "b", "c", "d", "e"]
AWAY = ["x", "y", "z", "p", "q"]


def stint(  # noqa: PLR0917
    start: int,
    end: int,
    home: list[str],
    away: list[str],
    pts: tuple[int, int] = (0, 0),
    poss: tuple[int, int] = (0, 0),
    game: str = "G1",
    season: int = 2025,
    teams: tuple[str, str] = ("H", "A"),
) -> dict[str, Any]:
    return {
        "game_id": game,
        "season": season,
        "period": 1,
        "start_s": start,
        "end_s": end,
        "home": teams[0],
        "away": teams[1],
        "home_players": home,
        "away_players": away,
        "home_points": pts[0],
        "away_points": pts[1],
        "home_poss": poss[0],
        "away_poss": poss[1],
    }


def checks(passed: bool = True, season: int = 2025) -> pd.DataFrame:
    return pd.DataFrame([{"game_id": "G1", "season": season, "passed": passed}])


def build(
    rows: list[dict[str, Any]],
    codes: dict[str, str] | None = None,
    passed: bool = True,
) -> dict[int, dict[str, Any]]:
    return units_by_season(pd.DataFrame(rows), checks(passed), {2025: 1}, [2025], codes or {})


def club(rows: list[dict[str, Any]], code: str = "H") -> dict[str, Any]:
    return build(rows)[2025]["clubs"][code]


def test_pair_totals_add_up_over_stints() -> None:
    payload = club(
        [
            stint(0, 3000, HOME, AWAY, (10, 6), (5, 4)),
            stint(3000, 6000, ["a", "b", "c", "d", "f"], AWAY, (20, 12), (6, 6)),
        ]
    )
    pairs = {(row[0], row[1]): row for row in payload["pairs"]}
    # a and b were on together for both stints: 100 minutes, 11 possessions, 30-18 in points
    assert pairs[("a", "b")][2:8] == [100.0, 11, 30, 18, 109.1, pairs[("a", "b")][7]]
    assert pairs[("a", "b")][7] > 0  # the interval is there, and is not zero
    # a and f shared only the second stint (50 minutes): below the pair minimum
    assert ("a", "f") not in pairs


def test_unit_key_order_does_not_matter() -> None:
    payload = club(
        [
            stint(0, 3000, ["e", "d", "c", "b", "a"], AWAY, (10, 6), (5, 4)),
            stint(3000, 6000, HOME, AWAY, (4, 8), (3, 3)),
        ]
    )
    assert [row[:5] for row in payload["units"]] == [HOME]
    assert payload["units"][0][5:9] == [100.0, 8, 14, 14]


def test_minimum_minutes_filter_pairs_and_units() -> None:
    payload = club(
        [
            # exactly 100 minutes together: the pairs count; the unit (99 minutes) counts too
            stint(0, MIN_PAIR_SECONDS, HOME, AWAY, (6, 4), (2, 2)),
            # 49 minutes: neither the pairs (under 100) nor the unit (under 50) count
            stint(0, MIN_UNIT_SECONDS - 60, ["f", "g", "h", "i", "j"], AWAY, (1, 1), (1, 1)),
        ]
    )
    assert len(payload["pairs"]) == 10 and all(row[2] == 100.0 for row in payload["pairs"])
    assert [row[:5] for row in payload["units"]] == [HOME]


def test_minimum_is_inclusive_for_units() -> None:
    payload = club(
        [stint(0, MIN_UNIT_SECONDS, ["f", "g", "h", "i", "j"], AWAY, (3, 1), (1, 1))],
    )
    assert [row[:5] for row in payload["units"]] == [["f", "g", "h", "i", "j"]]
    assert payload["units"][0][5] == 50.0


def test_net_is_per_100_possessions() -> None:
    assert net_rating(30, 20, 50) == pytest.approx(20.0)
    assert net_rating(0, 0, 0) == 0.0
    payload = club([stint(0, MIN_PAIR_SECONDS, HOME, AWAY, (9, 3), (8, 4))])
    unit = payload["units"][0]
    assert unit[6:9] == [8, 9, 3]  # possessions, points for, points against
    assert unit[9] == pytest.approx(75.0)  # net per 100 possessions: (9 - 3) / 8


def test_interval_shrinks_with_possessions() -> None:
    sd = possession_sd([3.0, -4.0], [4.0, 4.0])
    assert sd == pytest.approx((25 / 8) ** 0.5)
    assert half_width(1.0, 100) == pytest.approx(19.6)
    assert half_width(1.0, 400) < half_width(1.0, 100)
    assert half_width(1.0, 0) == 0.0


def test_only_qualifying_seasons_are_published() -> None:
    rows = [stint(0, MIN_PAIR_SECONDS, HOME, AWAY, (1, 0), (1, 1))]
    assert build(rows, passed=False) == {}
    assert set(build(rows, passed=True)) == {2025}


def test_clubs_are_renamed_for_display() -> None:
    payload = build(
        [stint(0, MIN_PAIR_SECONDS, HOME, AWAY, (1, 0), (1, 1), teams=("ULK", "PAM"))],
        codes={"ULK": "FBT"},
    )[2025]
    assert set(payload["clubs"]) == {"FBT", "PAM"}
    assert payload["minimums"] == {"pair": 100, "unit": 50}


def test_top_n_by_minutes_keeps_the_longest_pairs() -> None:
    rows = [
        stint(0, MIN_PAIR_SECONDS * 2, ["a", "b", "c", "d", "e"], AWAY, (1, 0), (1, 1)),
        stint(0, MIN_PAIR_SECONDS, ["a", "b", "k", "l", "m"], AWAY, (1, 0), (1, 1)),
    ]
    payload = club(rows)
    assert len(payload["pairs"]) <= 15
    assert payload["pairs"][0][:2] == ["a", "b"] and payload["pairs"][0][2] == 300.0
