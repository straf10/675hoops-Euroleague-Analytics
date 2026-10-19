from collections.abc import Iterator

import duckdb
import pytest

from eurohoops.audit import audit

GAMES_DDL = """
CREATE TABLE games (
    game_id VARCHAR, competition VARCHAR, season INTEGER, phase VARCHAR,
    home VARCHAR, away VARCHAR, home_score INTEGER, away_score INTEGER,
    played BOOLEAN, forfeit BOOLEAN, neutral BOOLEAN, tipoff_utc TIMESTAMPTZ
)
"""
TEAM_GAMES_DDL = """
CREATE TABLE team_games (
    game_id VARCHAR, competition VARCHAR, season INTEGER, team VARCHAR,
    home BOOLEAN, points INTEGER, source VARCHAR
)
"""
PLAYER_BOX_DDL = """
CREATE TABLE player_box (
    game_id VARCHAR, team VARCHAR, player_id VARCHAR, points INTEGER, fg2m INTEGER,
    fg2a INTEGER, fg3m INTEGER, fg3a INTEGER, ftm INTEGER, fta INTEGER, seconds INTEGER,
    source VARCHAR
)
"""
TEAM_BOX_DDL = (
    "CREATE TABLE team_box (game_id VARCHAR, team VARCHAR, total_points INTEGER, source VARCHAR)"
)
MISSING_DDL = (
    "CREATE TABLE team_games_missing "
    "(competition VARCHAR, season INTEGER, game_id VARCHAR, reason VARCHAR)"
)
XWALK_DDL = "CREATE TABLE player_xwalk (person_id VARCHAR, competition VARCHAR, source_id VARCHAR)"

GOOD_GAME = (
    "G1",
    "gbl",
    2024,
    "RS",
    "AAA",
    "BBB",
    80,
    70,
    True,
    False,
    False,
    "2024-10-05 18:00:00+00",
)


@pytest.fixture
def mart() -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect(":memory:")
    for ddl in (GAMES_DDL, TEAM_GAMES_DDL, PLAYER_BOX_DDL, TEAM_BOX_DDL, MISSING_DDL, XWALK_DDL):
        con.execute(ddl)
    con.execute("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list(GOOD_GAME))
    con.execute("INSERT INTO team_games VALUES ('G1','gbl',2024,'AAA',true,80,'esake')")
    con.execute("INSERT INTO team_games VALUES ('G1','gbl',2024,'BBB',false,70,'esake')")
    con.execute(
        """INSERT INTO player_box VALUES
        ('G1','AAA','p1',80,30,40,5,10,5,6,2400,'esake'),
        ('G1','BBB','p2',70,25,40,5,10,5,6,2400,'esake')"""
    )
    con.execute("INSERT INTO team_box VALUES ('G1','AAA',80,'esake'),('G1','BBB',70,'esake')")
    con.execute("INSERT INTO player_xwalk VALUES ('P:1','gbl','p1'),('P:2','gbl','p2')")
    yield con
    con.close()


def _counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {f.name: f.count for f in audit(con)}


def test_clean_mart_has_no_findings(mart: duckdb.DuckDBPyConnection) -> None:
    assert {name: n for name, n in _counts(mart).items() if n} == {}


def test_impossible_values_are_flagged(mart: duckdb.DuckDBPyConnection) -> None:
    mart.execute("INSERT INTO player_box VALUES ('G1','AAA','p3',-1,1,1,0,0,0,0,3782,'esake')")
    mart.execute("INSERT INTO player_box VALUES ('G1','AAA','p4',2,5,3,0,0,0,0,600,'esake')")
    counts = _counts(mart)
    assert counts["negative_stat"] == 1
    assert counts["made_above_attempted"] == 1
    assert counts["points_not_from_shots"] == 2
    assert counts["minutes_above_longest_game"] == 1


def test_team_total_and_score_mismatches_are_flagged(mart: duckdb.DuckDBPyConnection) -> None:
    mart.execute("UPDATE team_box SET total_points = 79 WHERE team = 'AAA'")
    mart.execute("UPDATE team_games SET points = 71 WHERE team = 'BBB'")
    counts = _counts(mart)
    assert counts["team_total_not_sum_of_players"] == 1
    assert counts["team_points_not_score"] == 1


def test_duplicates_and_null_keys_are_flagged(mart: duckdb.DuckDBPyConnection) -> None:
    mart.execute("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list(GOOD_GAME))
    mart.execute("INSERT INTO player_box VALUES ('G1','AAA','p1',0,0,0,0,0,0,0,0,'esake')")
    mart.execute(
        "INSERT INTO games VALUES ('G2', 'gbl', 2024, 'RS', NULL, 'CCC', 1, 2, true, false, false, "
        "'2024-10-06 18:00:00+00')"
    )
    counts = _counts(mart)
    assert counts["duplicate_game"] == 1
    assert counts["duplicate_player_box_row"] == 1
    assert counts["null_key"] == 1


def test_home_flag_and_dates_are_checked(mart: duckdb.DuckDBPyConnection) -> None:
    mart.execute("UPDATE team_games SET home = false WHERE team = 'AAA'")
    mart.execute(
        "INSERT INTO games VALUES ('G3','gbl',2024,'RS','CCC','DDD',1,2,true,false,false,"
        "'2025-08-01 18:00:00+00')"
    )
    counts = _counts(mart)
    assert counts["home_flag_not_venue"] == 1
    assert counts["date_outside_season"] == 1


def test_neutral_games_are_not_home_flag_faults(mart: duckdb.DuckDBPyConnection) -> None:
    mart.execute("UPDATE games SET neutral = true WHERE game_id = 'G1'")
    assert _counts(mart)["home_flag_not_venue"] == 0


def test_unlogged_missing_box_and_season_gaps(mart: duckdb.DuckDBPyConnection) -> None:
    mart.execute("DELETE FROM team_games WHERE game_id = 'G1'")
    mart.execute(
        "INSERT INTO games VALUES ('G9','gbl',2026,'RS','CCC','DDD',1,2,true,false,false,"
        "'2026-10-05 18:00:00+00')"
    )
    findings = {f.name: f for f in audit(mart)}
    assert findings["played_without_team_rows"].count == 2
    assert findings["played_game_unlisted_in_missing_log"].count == 2
    assert findings["season_gap"].count == 1
    assert "missing 2025" in findings["season_gap"].examples[0]


def test_player_without_person_is_flagged(mart: duckdb.DuckDBPyConnection) -> None:
    mart.execute("DELETE FROM player_xwalk WHERE source_id = 'p2'")
    assert _counts(mart)["player_id_without_person"] == 1
