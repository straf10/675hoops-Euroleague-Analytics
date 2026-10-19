"""Explained versus unexplained failures of the audit, and its coach and standings checks."""

import duckdb
import pandas as pd
import pytest

from eurohoops.audit import Finding, audit
from eurohoops.audit_coaches import coach_findings
from eurohoops.audit_standings import Standing, standings_findings
from tests.test_audit import (
    BOX_FILL_DDL,
    GAMES_DDL,
    MISSING_DDL,
    PLAYER_BOX_DDL,
    TEAM_BOX_DDL,
    TEAM_GAMES_DDL,
    XWALK_DDL,
)


def _mart() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    for ddl in (
        GAMES_DDL,
        TEAM_GAMES_DDL,
        PLAYER_BOX_DDL,
        TEAM_BOX_DDL,
        MISSING_DDL,
        XWALK_DDL,
        BOX_FILL_DDL,
    ):
        con.execute(ddl)
    return con


def _game(con: duckdb.DuckDBPyConnection, *row: object) -> None:
    con.execute("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list(row))


def _finding(findings: list[Finding], name: str) -> Finding:
    return next(f for f in findings if f.name == name)


def test_a_covid_cancelled_game_is_explained_and_an_unexplained_one_is_not() -> None:
    con = _mart()
    _game(
        con,
        "EL19_A",
        "euroleague",
        2019,
        "RS",
        "AAA",
        "BBB",
        None,
        None,
        False,
        False,
        False,
        "2020-03-14 20:00:00+03",
    )  # inside the cancellation
    _game(
        con,
        "EL19_B",
        "euroleague",
        2019,
        "RS",
        "AAA",
        "BBB",
        None,
        None,
        False,
        False,
        False,
        "2019-12-14 20:00:00+03",
    )  # before it: unexplained
    finding = _finding(audit(con), "unplayed_past_game")
    assert (finding.count, finding.unexplained) == (2, 1)
    assert finding.examples == ["EL19_B"]
    assert sum(finding.reasons.values()) == 1


def test_a_documented_correction_explains_its_minutes_key() -> None:
    con = _mart()
    con.execute("INSERT INTO player_box VALUES ('G1','T1','P1',0,0,0,0,0,0,0,3782,'esake')")
    bare = _finding(audit(con), "minutes_above_longest_game")
    assert (bare.count, bare.unexplained) == (1, 1)
    documented = _finding(audit(con, {"G1 T1 P1": "box fix"}), "minutes_above_longest_game")
    assert (documented.count, documented.unexplained) == (1, 0)
    assert documented.reasons == {"box fix": 1}


def test_a_documented_match_explains_a_person_with_two_ids() -> None:
    con = _mart()
    con.execute("INSERT INTO player_xwalk VALUES ('P:1','euroleague','A'),('P:1','euroleague','B')")
    assert _finding(audit(con), "person_with_two_ids_in_one_league").unexplained == 1
    documented = audit(con, {"P:1 euroleague": "same player"})
    assert _finding(documented, "person_with_two_ids_in_one_league").unexplained == 0


def _coach_rows() -> pd.DataFrame:
    """Game g1: AAA (home) beat BBB; coach a is at AAA, coach b at BBB."""
    tip = pd.Timestamp("2020-10-01T18:00:00Z")
    base = {"season": 2020, "phase": "RS", "final": False, "champion": False, "p_win": 0.5}
    return pd.DataFrame(
        [
            {
                **base,
                "game_id": "g1",
                "team": "AAA",
                "opponent": "BBB",
                "home": True,
                "won": True,
                "slug": "a",
                "name": "Coach A",
                "tipoff_utc": tip,
            },
            {
                **base,
                "game_id": "g1",
                "team": "BBB",
                "opponent": "AAA",
                "home": False,
                "won": False,
                "slug": "b",
                "name": "Coach B",
                "tipoff_utc": tip,
            },
        ]
    )


def _games() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": ["g1"],
            "home": ["AAA"],
            "away": ["BBB"],
            "home_score": [80],
            "away_score": [70],
        }
    )


def test_coach_rows_agree_with_the_game_result() -> None:
    assert all(f.unexplained == 0 for f in coach_findings(_coach_rows(), _games()))


def test_a_coach_row_that_contradicts_the_score_is_flagged() -> None:
    rows = _coach_rows()
    rows.loc[0, "won"] = False
    assert _finding(coach_findings(rows, _games()), "coach_result_mismatch").unexplained == 1


def test_a_coach_on_both_sides_is_flagged() -> None:
    rows = _coach_rows()
    rows.loc[1, "slug"] = "a"
    assert _finding(coach_findings(rows, _games()), "coach_on_both_sides").unexplained == 1


def _move_coach_a(second_club_day: str, later_at_aaa: bool) -> list[Finding]:
    """Coach a at AAA on 1 October, then at CCC on ``second_club_day``; optionally back at AAA
    on 10 October (which makes the two stints overlap)."""
    rows = _coach_rows()
    extra = [
        {
            **rows.iloc[0].to_dict(),
            "game_id": "g2",
            "team": "CCC",
            "opponent": "DDD",
            "tipoff_utc": pd.Timestamp(second_club_day),
        },
    ]
    if later_at_aaa:
        extra.append(
            {
                **rows.iloc[0].to_dict(),
                "game_id": "g3",
                "team": "AAA",
                "opponent": "EEE",
                "tipoff_utc": pd.Timestamp("2020-10-10T18:00:00Z"),
            }
        )
    rows = pd.concat([rows, pd.DataFrame(extra)], ignore_index=True)
    games = pd.concat(
        [
            _games(),
            pd.DataFrame(
                {
                    "game_id": ["g2", "g3"],
                    "home": ["CCC", "AAA"],
                    "away": ["DDD", "EEE"],
                    "home_score": [1, 1],
                    "away_score": [0, 0],
                }
            ),
        ],
        ignore_index=True,
    )
    return coach_findings(rows, games)


def test_sequential_club_stints_are_explained() -> None:
    finding = _finding(_move_coach_a("2020-10-05T18:00:00Z", False), "coach_two_clubs_same_season")
    assert finding.unexplained == 0
    assert sum(finding.reasons.values()) == 1


def test_overlapping_club_stints_are_unexplained() -> None:
    finding = _finding(_move_coach_a("2020-10-05T18:00:00Z", True), "coach_two_clubs_same_season")
    assert finding.unexplained == 1


def _standing(team: str, wins: int, losses: int, pf: int, pa: int) -> Standing:
    return Standing(2021, team, wins, losses, wins + losses, pf, pa)


def _rs_rows() -> list[tuple[int, str, str, int, int]]:
    """AAA 80-70 BBB (home AAA) and BBB 70-75 AAA: AAA 2-0 for 155-140, BBB 0-2 for 140-155."""
    return [(2021, "AAA", "BBB", 80, 70), (2021, "BBB", "AAA", 70, 75)]


def test_standings_points_must_match_the_games_less_overtime() -> None:
    exact = [_standing("AAA", 2, 0, 155, 140), _standing("BBB", 0, 2, 140, 155)]
    assert standings_findings(exact, _rs_rows(), {}, [2021], {2021})[0].unexplained == 0
    # 5 overtime points for AAA in g2 (its 75 includes them): the table shows 150, not 155
    regulation = [_standing("AAA", 2, 0, 150, 140), _standing("BBB", 0, 2, 140, 150)]
    overtime = {(2021, "AAA"): (5, 0), (2021, "BBB"): (0, 5)}
    with_ot = standings_findings(regulation, _rs_rows(), overtime, [2021], {2021})[0]
    assert with_ot.unexplained == 0
    assert sum(with_ot.reasons.values()) == 2
    assert standings_findings(regulation, _rs_rows(), {}, [2021], {2021})[0].unexplained == 2


@pytest.mark.parametrize("wins", [1, 2])
def test_a_wins_mismatch_is_unexplained(wins: int) -> None:
    table = [_standing("AAA", wins, 2 - wins, 155, 140), _standing("BBB", 0, 2, 140, 155)]
    finding = standings_findings(table, _rs_rows(), {}, [2021], {2021})[0]
    assert finding.unexplained == (0 if wins == 2 else 1)


def test_a_missing_standings_season_is_explained_only_when_cancelled_or_live() -> None:
    missing = standings_findings([], _rs_rows(), {}, [2019, 2021, 2026], set())[1]
    assert missing.unexplained == 1  # 2021 has no file and no excuse
    assert sum(missing.reasons.values()) == 2  # 2019 cancelled, 2026 live
