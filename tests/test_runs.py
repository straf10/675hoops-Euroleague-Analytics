"""Scoring runs (stats/runs.py): the run finder, the clock, the fixture games and the payload.

The fixture's play-by-play (``tests/fixtures/stats_raw/playbyplay``) is a slice of the real cache;
its scoring events add up to each game's final score, which the test checks.
"""

from pathlib import Path

import pytest

from eurohoops.stats.export import load_cached_games
from eurohoops.stats.onoff import score_events
from eurohoops.stats.runs import (
    AWAY,
    HOME,
    RUN_FIELDS,
    TOP_RUNS,
    Basket,
    find_runs,
    game_runs,
    runs_payload,
    seconds_left,
)
from tests.conftest import FIXTURES

RAW = FIXTURES / "stats_raw"


def basket(side: int, points: int, period: int = 1, left: int | None = 600) -> Basket:
    return Basket(period=period, left=left, side=side, points=points)


def test_a_run_is_consecutive_scoring_by_one_side() -> None:
    # home 2, home 3, then away 2: the first run is 5 points, the away run 2
    baskets = [basket(HOME, 2, left=500), basket(HOME, 3, left=470), basket(AWAY, 2, left=400)]
    out = find_runs(baskets)
    assert out["home"] == [[5, 1, 500, 1, 470, 0, 0, 5, 0]]
    assert out["away"] == [[2, 1, 400, 1, 400, 5, 0, 5, 2]]


def test_run_scores_are_the_running_score_before_and_after() -> None:
    baskets = [
        basket(AWAY, 2, left=590),
        basket(HOME, 2, left=580),
        basket(HOME, 2, left=560),
        basket(HOME, 1, left=550),
    ]
    home = find_runs(baskets)["home"]
    assert home == [[5, 1, 580, 1, 550, 0, 2, 5, 2]]


def test_top_three_by_points_ties_go_to_the_earlier_run() -> None:
    # home runs of 4, 6, 4, 6, 2 points, each split by an away basket; the clock is 600 - index
    sequence = [
        (HOME, 4),
        (AWAY, 1),
        (HOME, 6),
        (AWAY, 3),
        (HOME, 4),
        (AWAY, 2),
        (HOME, 6),
        (AWAY, 1),
        (HOME, 2),
    ]
    baskets = [basket(side, pts, left=600 - i) for i, (side, pts) in enumerate(sequence)]
    home = find_runs(baskets)["home"]
    assert TOP_RUNS == 3 and len(home) == 3
    assert home == [
        [6, 1, 598, 1, 598, 4, 1, 10, 1],  # the first 6-point run (index 2)
        [6, 1, 594, 1, 594, 14, 6, 20, 6],  # the second (index 6)
        [4, 1, 600, 1, 600, 0, 0, 4, 0],  # the earlier of the two 4-point runs (index 0)
    ]


def test_fewer_runs_than_the_top_leaves_the_list_short() -> None:
    out = find_runs([basket(HOME, 2)])
    assert out["home"] == [[2, 1, 600, 1, 600, 0, 0, 2, 0]]
    assert out["away"] == []


def test_a_run_crosses_periods_and_keeps_both_clocks() -> None:
    baskets = [basket(AWAY, 2, period=4, left=5), basket(AWAY, 2, period=5, left=290)]
    assert find_runs(baskets)["away"] == [[4, 4, 5, 5, 290, 0, 0, 0, 4]]


def test_clock_counts_seconds_left_in_the_period() -> None:
    assert seconds_left(1, 0) == 600
    assert seconds_left(4, 2399) == 1
    assert seconds_left(5, 2400) == 300  # first overtime starts after 40 minutes
    assert seconds_left(5, 2700) == 0
    assert seconds_left(2, None) is None


def test_a_basket_without_a_clock_keeps_its_place_in_the_run() -> None:
    baskets = [basket(HOME, 2, left=None), basket(HOME, 2, left=500)]
    assert find_runs(baskets)["home"] == [[4, 1, None, 1, 500, 0, 0, 4, 0]]


def test_fixture_games_add_up_to_the_final_score() -> None:
    games, _ = load_cached_games(RAW)
    played = games[games["played"]]
    scores = score_events(RAW, played)
    runs = game_runs(RAW, played)
    assert runs, "the fixture has play-by-play"
    for g in played.itertuples(index=False):
        if g.game_id not in runs:
            continue
        ev = scores[scores["game_id"] == g.game_id]
        baskets = [
            Basket(int(p), None, HOME if h else AWAY, int(pts))
            for p, pts, h in zip(ev["period"], ev["points"], ev["home"], strict=True)
        ]
        everything = find_runs(baskets, top=10_000)
        assert sum(r[0] for r in everything["home"]) == int(g.home_score)
        assert sum(r[0] for r in everything["away"]) == int(g.away_score)


def test_each_game_has_at_most_three_runs_per_side() -> None:
    games, _ = load_cached_games(RAW)
    for runs in game_runs(RAW, games[games["played"]]).values():
        assert len(runs["home"]) <= TOP_RUNS and len(runs["away"]) <= TOP_RUNS
        for row in runs["home"] + runs["away"]:
            assert len(row) == len(RUN_FIELDS)


def test_payload_lists_only_games_with_runs(tmp_path: Path) -> None:
    runs = {"E2024_1": {"home": [], "away": []}}
    payload = runs_payload(2024, ["E2024_2", "E2024_1"], runs)
    assert payload == {"season": 2024, "run_fields": list(RUN_FIELDS), "games": runs}


@pytest.mark.parametrize("side", [HOME, AWAY])
def test_both_sides_are_reported(side: int) -> None:
    out = find_runs([basket(side, 3)])
    key = "home" if side == HOME else "away"
    assert out[key] and out[key][0][0] == 3
