"""Assist network (stats/assists.py): tiered linking of AS rows, aggregation.

The pairing tests build small play-by-play logs by hand. The fixture test runs the real games of
``tests/fixtures/stats_raw`` through the same code the export uses.
"""

from eurohoops.parse.stints import Event
from eurohoops.stats.assists import (
    CLOCK_WINDOW,
    EVENT_WINDOW,
    LOOSE_CLOCK,
    NO_CLOCK_WINDOW,
    AssistRow,
    assist_rows,
    assists_payload,
    game_assists,
)
from eurohoops.stats.export import load_cached_games
from tests.conftest import FIXTURES

RAW = FIXTURES / "stats_raw"
A, B = "ULK", "PAM"


def ev(kind: str, team: str, player: str = "p", clock: int | None = 500, period: int = 1) -> Event:
    return Event(period=period, elapsed=clock, kind=kind, team=team, player=player)


# ---- fg tier: one-to-one matching of AS rows to field goals


def test_the_make_just_before_the_assist_at_a_close_clock_links() -> None:
    log = [ev("2FGM", A, "scorer", 500), ev("AS", A, "passer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 2, "fg")]


def test_the_make_just_after_the_assist_links() -> None:
    log = [ev("AS", A, "passer", 480), ev("3FGM", A, "scorer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 3, "fg")]


def test_a_make_by_the_other_team_never_links() -> None:
    log = [ev("2FGM", B, "other", 500), ev("AS", A, "passer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


def test_an_opposing_make_between_the_rows_blocks_the_fg_tier() -> None:
    # B scores between the assist and the make: the fg tier refuses; only the loose tier, with its
    # penalty, can take it
    log = [ev("AS", A, "passer", 480), ev("2FGM", B, "other", 470), ev("DUNK", A, "scorer", 470)]
    assert assist_rows(log)[0].tier == "loose"


def test_a_make_beyond_the_clock_window_does_not_link_in_fg() -> None:
    log = [ev("AS", A, "passer", 500), ev("2FGM", A, "scorer", 500 - CLOCK_WINDOW - 1)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]
    log = [ev("AS", A, "passer", 500), ev("2FGM", A, "scorer", 500 - CLOCK_WINDOW)]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 2, "fg")]


def test_a_make_beyond_the_event_window_is_not_fg() -> None:
    far = [ev("AS", A, "passer", 480)]
    far += [ev("2FGA", B, "x", 480) for _ in range(EVENT_WINDOW)]  # misses, no opposing make
    far.append(ev("2FGM", A, "scorer", 480))  # EVENT_WINDOW + 1 events away
    assert assist_rows(far)[0].tier == "loose"  # the fg tier stops here; the loose tier catches it


def test_a_row_without_a_clock_links_only_within_a_few_events() -> None:
    near = [ev("2FGM", A, "scorer", None), ev("AS", A, "passer", None)]
    assert assist_rows(near) == [AssistRow(A, "passer", "scorer", 2, "fg")]
    far = [ev("2FGM", A, "scorer", None)]
    far += [ev("2FGA", B, "x", None) for _ in range(NO_CLOCK_WINDOW)]
    far.append(ev("AS", A, "passer", None))
    assert assist_rows(far) == [AssistRow(A, "passer", None, 0)]


def test_the_closest_make_is_preferred() -> None:
    log = [ev("2FGM", A, "far", 470), ev("2FGM", A, "close", 480), ev("AS", A, "passer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", "close", 2, "fg")]


def test_a_make_is_credited_once_to_the_closest_assist() -> None:
    log = [ev("2FGM", A, "scorer", 500), ev("AS", A, "first", 480), ev("AS", A, "second", 480)]
    rows = assist_rows(log)
    assert [r.scorer for r in rows] == ["scorer", None]
    assert [r.passer for r in rows] == ["first", "second"]


def test_a_matching_reassigns_so_both_assists_link_when_possible() -> None:
    # AS "first" fits both makes; AS "second" fits both too. A maximum matching links both.
    log = [
        ev("AS", A, "first", 490),
        ev("2FGM", A, "a", 490),
        ev("2FGM", A, "b", 480),
        ev("AS", A, "second", 480),
    ]
    rows = assist_rows(log)
    assert sorted(r.scorer for r in rows if r.scorer) == ["a", "b"]


def test_points_follow_the_make_kind() -> None:
    for kind, points in (("2FGM", 2), ("LAYUPMD", 2), ("DUNK", 2), ("3FGM", 3)):
        log = [ev(kind, A, "scorer", 500), ev("AS", A, "passer", 480)]
        assert assist_rows(log)[0].points == points


def test_a_players_own_make_is_never_his_assist() -> None:
    log = [ev("2FGM", A, "passer", 490), ev("AS", A, "passer", 480), ev("2FGM", A, "scorer", 470)]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 2, "fg")]

    alone = [ev("2FGM", A, "passer", 490), ev("AS", A, "passer", 480)]
    assert assist_rows(alone) == [AssistRow(A, "passer", None, 0)]


def test_free_throws_alone_are_not_assisted_baskets() -> None:
    log = [ev("FTM", A, "shooter", 500), ev("AS", A, "passer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


# ---- ft tier: the pass led to a foul on a teammate who made a free throw


def test_a_made_free_throw_in_the_foul_trip_credits_the_assist() -> None:
    log = [ev("RV", A, "shooter", 500), ev("FTM", A, "shooter", 500), ev("AS", A, "passer", 500)]
    assert assist_rows(log) == [AssistRow(A, "passer", "shooter", 1, "ft")]


def test_the_passer_is_never_the_free_throw_shooter() -> None:
    log = [ev("RV", A, "p", 500), ev("FTM", A, "p", 500), ev("AS", A, "p", 500)]
    assert assist_rows(log) == [AssistRow(A, "p", None, 0)]


def test_one_foul_credits_one_assist() -> None:
    log = [
        ev("RV", A, "shooter", 500),
        ev("FTM", A, "shooter", 500),
        ev("AS", A, "first", 500),
        ev("AS", A, "second", 500),
    ]
    rows = assist_rows(log)
    assert rows[0] == AssistRow(A, "first", "shooter", 1, "ft")
    assert rows[1] == AssistRow(A, "second", None, 0)


def test_a_free_throw_must_be_within_two_seconds_of_the_assist() -> None:
    log = [ev("RV", A, "shooter", 500), ev("FTM", A, "shooter", 500), ev("AS", A, "passer", 497)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


def test_a_free_throw_needs_a_foul_received_in_the_trip() -> None:
    log = [ev("FTM", A, "shooter", 500), ev("AS", A, "passer", 500)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


def test_a_field_goal_takes_precedence_over_a_free_throw() -> None:
    log = [
        ev("2FGM", A, "scorer", 500),
        ev("RV", A, "shooter", 480),
        ev("FTM", A, "shooter", 480),
        ev("AS", A, "passer", 480),
    ]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 2, "fg")]


# ---- loose tier: minimum-cost assignment of the leftovers, shot-clock cap, opposing penalty


def test_a_loose_link_pays_the_penalty_across_an_opposing_make() -> None:
    log = [ev("AS", A, "passer", 470), ev("2FGM", B, "other", 480), ev("2FGM", A, "scorer", 490)]
    assert assist_rows(log)[0] == AssistRow(A, "passer", "scorer", 2, "loose")


def test_the_loose_tier_respects_the_shot_clock_cap() -> None:
    gap = LOOSE_CLOCK + 6
    log = [
        ev("AS", A, "passer", 500),
        ev("2FGM", B, "other", 490),
        ev("2FGM", A, "scorer", 500 - gap),
    ]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


# ---- aggregation


def test_payload_aggregates_pairs_and_passers_and_checks_box_totals() -> None:
    rows = {
        "g1": [
            AssistRow(A, "p1", "s1", 2),
            AssistRow(A, "p1", "s1", 3),
            AssistRow(A, "p2", "s2", 2),
            AssistRow(A, "p2", None, 0),
        ],
        "g2": [AssistRow(B, "q1", "q2", 2)],
        "g3": [AssistRow(A, "p1", "s1", 2)],  # not in the requested games
    }
    out = assists_payload(2024, ["g2", "g1"], rows, {A: 4, B: 3})
    assert out["season"] == 2024
    clubs = out["clubs"]
    assert clubs[A] == {
        "as_rows": 4,
        "linked": 3,
        "linked_fg": 3,
        "linked_ft": 0,
        "linked_loose": 0,
        "box": 4,
        "pairs": [["p1", "s1", 2, 5], ["p2", "s2", 1, 2]],
        "ft_pairs": [],
        "loose_pairs": [],
        "passers": [["p1", 2, 2, 5], ["p2", 2, 1, 2]],
    }
    assert clubs[B]["pairs"] == [["q1", "q2", 1, 2]]
    assert clubs[B]["box"] == 3


def test_payload_keeps_the_tiers_apart() -> None:
    rows = {
        "g1": [
            AssistRow(A, "p1", "s1", 2, "fg"),
            AssistRow(A, "p2", "f1", 1, "ft"),
            AssistRow(A, "p3", "l1", 2, "loose"),
        ]
    }
    club = assists_payload(2024, ["g1"], rows, {A: 3})["clubs"][A]
    assert club["linked"] == 3
    assert (club["linked_fg"], club["linked_ft"], club["linked_loose"]) == (1, 1, 1)
    assert club["pairs"] == [["p1", "s1", 1, 2]]
    assert club["ft_pairs"] == [["p2", "f1", 1, 1]]
    assert club["loose_pairs"] == [["p3", "l1", 1, 2]]


def test_fixture_games_are_paired_and_counted() -> None:
    games, _ = load_cached_games(RAW)
    played = games[games["played"]]
    rows = game_assists(RAW, played)
    assert rows, "the fixture has play-by-play"
    for game_id, game_rows in rows.items():
        assert all(r.scorer is None or r.points in (1, 2, 3) for r in game_rows), game_id
        assert all((r.scorer is None) == (r.points == 0) for r in game_rows), game_id
        assert all((r.tier is None) == (r.scorer is None) for r in game_rows), game_id
