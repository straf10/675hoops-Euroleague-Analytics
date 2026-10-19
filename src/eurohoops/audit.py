"""Cross-table data audit of the DuckDB marts: impossible values, duplicates, gaps, inconsistencies.

Each check is one SQL query that returns the offending rows, labelled by a short key. A check may
also have an ``explain`` query that gives a reason for some of those keys (a PBP fill, a logged
missing box, a documented correction, a cancelled season). Every failing row is then either
EXPLAINED (with its reason) or UNEXPLAINED. The number to drive to zero is the unexplained count.

Checks never change data: ``scripts/data_audit.py`` prints the report, and the regression tests
build a small mart with known faults. ``corrections/gbl_box.csv`` documents the per-player box
corrections; its rows are passed in as ``corrections`` and explain the matching ``minutes`` keys.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

import duckdb

# A player cannot play more than 40 regulation minutes plus 5 per overtime; four overtimes is
# the longest game in the data. Anything above is a parse error, whatever the overtime count.
MAX_PLAYER_SECONDS = 60 * 60

# Season cancellations and removals (see the research notes); a row is explained only if its
# tip-off falls inside the event, so an unplayed game outside every event stays unexplained.
COVID_EL_2019 = "2019-20 EuroLeague cancelled (COVID, from 12 March 2020)"
COVID_GBL_2019 = "2019-20 GBL cancelled (COVID; no game played after 8 March 2020)"
RUSSIA_EL_2021 = "2021-22 EuroLeague: Russian clubs removed, games from 24 Feb 2022 not played"
LIVE_BOX = "live season 2026-27: box score not yet ingested (no cached ESAKE page)"
PBP_FILL = "PBP fill: one missing player added, filled points equal the result"
PBP_TOTALS = "PBP fill: team total from PBP events (no ESAKE box cached)"

RUSSIAN_CLUBS = "('CSK', 'UNK', 'DYR', 'KHI')"


@dataclass(frozen=True)
class Check:
    name: str
    sql: str  # SELECT label FROM ... : one row per failing item
    explain: str = ""  # SELECT label, reason FROM ... : reason NULL when not explained
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
        f"""SELECT game_id || ' ' || team || ' ' || player_id FROM player_box
        WHERE seconds > {MAX_PLAYER_SECONDS}""",
        note="explained only by corrections/gbl_box.csv (passed in, not read from the mart)",
    ),
    Check(
        "official_box_total_not_score",
        """SELECT t.game_id || ' ' || t.team FROM team_box t JOIN games g USING (game_id)
        WHERE t.source = 'esake' AND g.played
          AND ((t.team = g.home AND t.total_points <> g.home_score)
            OR (t.team = g.away AND t.total_points <> g.away_score))""",
        explain=f"""SELECT f.game_id || ' ' || f.team,
          CASE f.fill WHEN 'missing_player_from_pbp' THEN '{PBP_FILL}'
                      WHEN 'team_totals_from_pbp' THEN '{PBP_TOTALS}' END
        FROM box_fill f""",
        note="ESAKE's printed total vs the result; explained when the PBP fill log covers it",
    ),
    Check(
        "team_points_not_score",
        """SELECT g.game_id || ' ' || t.team FROM team_games t JOIN games g USING (game_id)
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
        explain=f"""SELECT g.game_id,
          CASE WHEN g.season = 2026 AND m.reason LIKE 'no cached ESAKE box score%'
               THEN '{LIVE_BOX}'
               ELSE m.reason END
        FROM games g LEFT JOIN team_games_missing m ON m.game_id = g.game_id""",
        note="every played game without team rows must be logged in team_games_missing",
    ),
    Check(
        "unplayed_past_game",
        """SELECT game_id FROM games
        WHERE NOT played AND NOT forfeit AND tipoff_utc < now()""",
        explain=f"""SELECT game_id, CASE
          WHEN competition = 'euroleague' AND season = 2019
               AND tipoff_utc >= TIMESTAMPTZ '2020-03-12 00:00:00+03' THEN '{COVID_EL_2019}'
          WHEN competition = 'gbl' AND season = 2019
               AND tipoff_utc >= TIMESTAMPTZ '2020-03-09 00:00:00+03' THEN '{COVID_GBL_2019}'
          WHEN competition = 'euroleague' AND season = 2021
               AND (home IN {RUSSIAN_CLUBS} OR away IN {RUSSIAN_CLUBS})
               AND tipoff_utc >= TIMESTAMPTZ '2022-02-24 00:00:00+03' THEN '{RUSSIA_EL_2021}'
        END FROM games WHERE NOT played AND NOT forfeit AND tipoff_utc < now()""",
        note="expected only inside the three events above; anything else is a finding",
    ),
    Check(
        "person_with_two_ids_in_one_league",
        """SELECT person_id || ' ' || competition FROM player_xwalk
        GROUP BY person_id, competition HAVING count(*) > 1""",
        note="explained only by a documented match decision in entity/overrides.csv",
    ),
    Check(
        "source_id_with_two_persons",
        """SELECT competition || ' ' || source_id FROM player_xwalk
        GROUP BY competition, source_id HAVING count(DISTINCT person_id) > 1""",
    ),
    Check(
        "player_id_without_person",
        """SELECT DISTINCT p.player_id FROM player_box p
        WHERE p.source = 'esake' AND p.game_id NOT LIKE 'GBL2026%'
          AND NOT EXISTS (SELECT 1 FROM player_xwalk x WHERE x.source_id = p.player_id)""",
    ),
)

GAP_SQL = """
SELECT competition, min(season) AS first, max(season) AS last, count(DISTINCT season) AS seen
FROM games GROUP BY competition
"""


@dataclass(frozen=True)
class Finding:
    name: str
    count: int  # failing items, explained or not
    unexplained: int
    examples: list[str] = field(default_factory=list)  # unexplained items, first few
    reasons: dict[str, int] = field(default_factory=dict)  # explanation -> items
    note: str = ""


def _labels(con: duckdb.DuckDBPyConnection, sql: str) -> list[str]:
    return [str(row[0]) for row in con.execute(sql).fetchall()]


def _explanations(con: duckdb.DuckDBPyConnection, sql: str) -> dict[str, str]:
    if not sql:
        return {}
    return {
        str(label): str(reason)
        for label, reason in con.execute(sql).fetchall()
        if reason is not None
    }


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


def audit(
    con: duckdb.DuckDBPyConnection,
    corrections: Mapping[str, str] | None = None,
    examples: int = 5,
) -> list[Finding]:
    """Run every check and split its failures into explained and unexplained.

    ``corrections`` maps a documented item's label (for example ``game team player`` for a box
    correction, or ``person_id competition`` for a documented match) to its reason; it explains
    that label in whichever check reports it.
    """
    documented = dict(corrections or {})
    findings: list[Finding] = []
    for check in CHECKS:
        labels = _labels(con, check.sql)
        explained = _explanations(con, check.explain)
        explained.update({k: v for k, v in documented.items() if k in labels})
        reasons: dict[str, int] = {}
        unexplained: list[str] = []
        for label in labels:
            if label in explained:
                reasons[explained[label]] = reasons.get(explained[label], 0) + 1
            else:
                unexplained.append(label)
        findings.append(
            Finding(
                check.name,
                len(labels),
                len(unexplained),
                unexplained[:examples],
                reasons,
                check.note,
            )
        )
    gaps = season_gaps(con)
    findings.append(
        Finding(
            "season_gap",
            len(gaps),
            len(gaps),
            gaps,
            {},
            "seasons absent between first and last",
        )
    )
    return findings


def run_audit(
    path: str, corrections: Mapping[str, str] | None = None, examples: int = 5
) -> list[Finding]:
    """Open a mart read-only and audit it."""
    with duckdb.connect(path, read_only=True) as con:
        return audit(con, corrections, examples)
