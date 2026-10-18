"""Assist network (stats/assists.py): rule D pairing, the one-make-per-assist rule, aggregation.

The pairing tests build small play-by-play logs by hand. The fixture test runs the real games of
``tests/fixtures/stats_raw`` through the same code the export uses.
"""

from eurohoops.parse.stints import Event
from eurohoops.stats.assists import AssistRow, assist_rows, assists_payload, game_assists
from eurohoops.stats.export import load_cached_games
from tests.conftest import FIXTURES

RAW = FIXTURES / "stats_raw"
A, B = "ULK", "PAM"


def ev(kind: str, team: str, player: str = "p", clock: int | None = 500, period: int = 1) -> Event:
    return Event(period=period, elapsed=clock, kind=kind, team=team, player=player)


def test_rule_a_links_the_make_just_before_the_assist() -> None:
    log = [ev("2FGM", A, "scorer", 500), ev("AS", A, "passer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 2)]


def test_rule_a_needs_the_passers_team() -> None:
    # the last make is B's, so rule A fails; B's make is not at the same clock and is not near
    log = [ev("2FGM", B, "other", 500), ev("AS", A, "passer", 480), ev("2FGM", B, "x", 400)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


def test_rule_b_links_the_next_make_at_the_same_clock() -> None:
    # the AS row is logged just before its own make, with the same clock second
    log = [ev("AS", A, "passer", 480), ev("3FGM", A, "scorer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 3)]


def test_rule_c_links_a_nearby_same_team_make() -> None:
    # B's make sits between, so A and B fail; A's make two events later is within two events
    log = [ev("AS", A, "passer", 480), ev("2FGM", B, "other", 470), ev("DUNK", A, "scorer", 400)]
    assert assist_rows(log) == [AssistRow(A, "passer", "scorer", 2)]


def test_rule_c_links_a_far_make_only_at_the_same_clock() -> None:
    far = [ev("AS", A, "passer", 480)]
    far += [ev("2FGA", B, "x", 470) for _ in range(5)]  # misses do not count
    far.append(ev("2FGM", A, "late", 400))  # same team, six events on, another clock second
    assert assist_rows(far) == [AssistRow(A, "passer", None, 0)]
    same_clock = [ev("AS", A, "passer", 480)]
    same_clock += [ev("2FGM", B, "x", 300) for _ in range(4)]
    same_clock.append(ev("2FGM", A, "scorer", 480))  # 5 events on, but the same clock second
    assert assist_rows(same_clock) == [AssistRow(A, "passer", "scorer", 2)]


def test_a_make_never_crosses_a_period() -> None:
    log = [ev("2FGM", A, "scorer", 1, period=1), ev("AS", A, "passer", 600, period=2)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


def test_free_throws_are_not_assisted_baskets() -> None:
    log = [ev("FTM", A, "shooter", 500), ev("AS", A, "passer", 480)]
    assert assist_rows(log) == [AssistRow(A, "passer", None, 0)]


def test_the_first_assist_keeps_a_make_the_second_loses_it() -> None:
    log = [ev("2FGM", A, "scorer", 500), ev("AS", A, "first", 480), ev("AS", A, "second", 480)]
    rows = assist_rows(log)
    assert [r.scorer for r in rows] == ["scorer", None]
    assert [r.passer for r in rows] == ["first", "second"]


def test_points_follow_the_make_kind() -> None:
    for kind, points in (("2FGM", 2), ("LAYUPMD", 2), ("DUNK", 2), ("3FGM", 3)):
        log = [ev(kind, A, "scorer", 500), ev("AS", A, "passer", 480)]
        assert assist_rows(log)[0].points == points


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
        "box": 4,
        "pairs": [["p1", "s1", 2, 5], ["p2", "s2", 1, 2]],
        "passers": [["p1", 2, 2, 5], ["p2", 2, 1, 2]],
    }
    assert clubs[B]["pairs"] == [["q1", "q2", 1, 2]]
    assert clubs[B]["box"] == 3


def test_fixture_games_are_paired_and_counted() -> None:
    games, _ = load_cached_games(RAW)
    played = games[games["played"]]
    rows = game_assists(RAW, played)
    assert rows, "the fixture has play-by-play"
    for game_id, game_rows in rows.items():
        assert all(r.scorer is None or r.points in (2, 3) for r in game_rows), game_id
        assert all((r.scorer is None) == (r.points == 0) for r in game_rows), game_id
