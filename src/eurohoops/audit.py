"""Cross-table data audit of the DuckDB marts: impossible values, duplicates, gaps, inconsistencies.

Each check is one SQL query that returns the offending rows. ``audit`` runs them all and reports
a count and a few examples per check. Checks never change data: ``scripts/data_audit.py`` prints
the report, and the regression tests build a small mart with known faults.

A check that counts rows the pipeline already handles on purpose (for example the PBP fill of
short 2018-19 GBL box scores) says so in its ``note``; its count is still reported.
"""

from dataclasses import dataclass, field

import duckdb

# A player cannot play more than 40 regulation minutes plus 5 per overtime; four overtimes is
# the longest game in the data. Anything above is a parse error, whatever the overtime count.
MAX_PLAYER_SECONDS = 60 * 60


@dataclass(frozen=True)
class Check:
    name: str
    sql: str  # a SELECT of offending rows; the first column is the row's label
    note: str = ""


@dataclass(frozen=True)
class Finding:
    name: str
    count: int
    examples: list[str] = field(default_factory=list)
    note: str = ""


CHECKS: tuple[Check, ...] = (
    Check(
        "negative_stat",
        """SELECT game_id || ' ' || player_id FROM player_box
        WHERE points < 0 OR fg2m < 0 OR fg2a < 0 OR fg3m < 0 OR fg3a < 0
           OR ftm < 0 OR fta < 0 OR seconds < 0""",
    ),
    Check(
        "made_above_attempted",
        """SELECT game_id || ' ' || player_id FROM player_box
        WHERE fg2m > fg2a OR fg3m > fg3a OR ftm > fta""",
    ),
    Check(
        "points_not_from_shots",
        """SELECT game_id || ' ' || player_id FROM player_box
        WHERE points <> 2 * fg2m + 3 * fg3m + ftm""",
    ),
    Check(
        "minutes_above_longest_game",
        f"""SELECT game_id || ' ' || team || ' ' || player_id || ' ' || seconds
        FROM player_box WHERE seconds > {MAX_PLAYER_SECONDS}""",
    ),
    Check(
        "team_total_not_sum_of_players",
        """SELECT t.game_id || ' ' || t.team FROM team_box t
        JOIN (SELECT game_id, team, sum(points) AS p FROM player_box
              WHERE source = 'esake' GROUP BY 1, 2) s USING (game_id, team)
        WHERE t.source = 'esake' AND s.p <> t.total_points""",
    ),
    Check(
        "official_box_total_not_score",
        """SELECT t.game_id || ' ' || t.team FROM team_box t JOIN games g USING (game_id)
        WHERE t.source = 'esake' AND g.played
          AND ((t.team = g.home AND t.total_points <> g.home_score)
            OR (t.team = g.away AND t.total_points <> g.away_score))""",
        note="ESAKE's printed total vs the result: 2018-19 short boxes (PBP-filled), 2022 unfilled",
    ),
    Check(
        "team_points_not_score",
        """SELECT g.game_id || ' ' || t.team FROM team_games t
        JOIN games g USING (game_id)
        WHERE g.played AND t.team = g.home AND t.points <> g.home_score
           OR g.played AND t.team = g.away AND t.points <> g.away_score""",
    ),
    Check(
        "home_flag_not_venue",
        """SELECT t.game_id || ' ' || t.team FROM team_games t JOIN games g USING (game_id)
        WHERE NOT g.neutral AND t.home <> (t.team = g.home)""",
    ),
    Check(
        "duplicate_game",
        "SELECT game_id FROM games GROUP BY 1 HAVING count(*) > 1",
    ),
    Check(
        "duplicate_player_box_row",
        """SELECT game_id || ' ' || team || ' ' || player_id FROM player_box
        GROUP BY 1 HAVING count(*) > 1""",
    ),
    Check(
        "null_key",
        """SELECT game_id FROM games
        WHERE game_id IS NULL OR season IS NULL OR home IS NULL OR away IS NULL""",
    ),
    Check(
        "home_equals_away",
        "SELECT game_id FROM games WHERE home = away",
    ),
    Check(
        "date_outside_season",
        """SELECT game_id FROM games
        WHERE tipoff_utc < make_timestamptz(season, 7, 1, 0, 0, 0, 'UTC')
           OR tipoff_utc >= make_timestamptz(season + 1, 7, 1, 0, 0, 0, 'UTC')""",
        note="a season runs from 1 July of its label year to 30 June of the next",
    ),
    Check(
        "played_without_team_rows",
        """SELECT g.game_id FROM games g
        WHERE g.played AND NOT g.forfeit
          AND NOT EXISTS (SELECT 1 FROM team_games t WHERE t.game_id = g.game_id)""",
        note="expected only for games in team_games_missing (reason recorded there)",
    ),
    Check(
        "played_game_unlisted_in_missing_log",
        """SELECT g.game_id FROM games g
        WHERE g.played AND NOT g.forfeit
          AND NOT EXISTS (SELECT 1 FROM team_games t WHERE t.game_id = g.game_id)
          AND NOT EXISTS (SELECT 1 FROM team_games_missing m WHERE m.game_id = g.game_id)""",
    ),
    Check(
        "player_id_without_person",
        """SELECT DISTINCT p.player_id FROM player_box p
        WHERE p.source = 'esake' AND p.game_id NOT LIKE 'GBL2026%'
          AND NOT EXISTS (SELECT 1 FROM player_xwalk x WHERE x.source_id = p.player_id)""",
        note="the 2026-27 season is not in the crosswalk yet",
    ),
)

GAP_SQL = """
SELECT competition, min(season) AS first, max(season) AS last, count(DISTINCT season) AS seen
FROM games GROUP BY competition
"""


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[str]:
    return [" | ".join(str(v) for v in row) for row in con.execute(sql).fetchall()]


def season_gaps(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Competition seasons missing between its first and last season."""
    gaps: list[str] = []
    for competition, first, last, seen in con.execute(GAP_SQL).fetchall():
        expected = int(last) - int(first) + 1
        if seen != expected:
            present = {
                int(s)
                for (s,) in con.execute(
                    "SELECT DISTINCT season FROM games WHERE competition = ?", [competition]
                ).fetchall()
            }
            missing = [str(s) for s in range(int(first), int(last) + 1) if s not in present]
            gaps.append(f"{competition}: missing {', '.join(missing)}")
    return gaps


def audit(con: duckdb.DuckDBPyConnection, examples: int = 5) -> list[Finding]:
    """Run every check; each finding holds the count and up to ``examples`` offending rows."""
    findings: list[Finding] = []
    for check in CHECKS:
        rows = _rows(con, check.sql)
        findings.append(Finding(check.name, len(rows), rows[:examples], check.note))
    gaps = season_gaps(con)
    findings.append(Finding("season_gap", len(gaps), gaps, "seasons absent between first and last"))
    return findings


def run_audit(path: str, examples: int = 5) -> list[Finding]:
    """Open a mart read-only and audit it."""
    with duckdb.connect(path, read_only=True) as con:
        return audit(con, examples)
