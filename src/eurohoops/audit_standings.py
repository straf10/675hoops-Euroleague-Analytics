"""Standings checks of the audit: the cached final regular-season tables vs the games.

The EuroLeague standings files (``raw/euroleague/standings/E{season}_r{round}.xml``) give each
team's wins, losses, games and points for and against. Wins, losses and games must equal the
regular-season results. Points must equal the game scores less the overtime points: the published
table counts the 40 regulation minutes only (checked season by season, with the overtime points
taken from each box score's EndOfQuarter table). A season without a standings file is unexplained
unless it was cancelled or is the live season.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from eurohoops.audit import Finding

POINTS_REGULATION = "points are regulation only: standings omit the overtime points"
SEASON_CANCELLED = "season cancelled (COVID, 2019-20): no final standings were published"
LIVE = "live season 2026-27: standings not final yet"
FROM_RESULTS = (
    "no standings file; the site ranks the season from its results "
    "(stats.export.regular_season_standings falls back to standings.rank)"
)


@dataclass(frozen=True)
class Standing:
    season: int
    team: str
    wins: int
    losses: int
    games: int
    points_for: int
    points_against: int


@dataclass
class _Totals:
    games: int = 0
    wins: int = 0
    points_for: int = 0
    points_against: int = 0


def results(rows: Iterable[tuple[int, str, str, int, int]]) -> dict[tuple[int, str], _Totals]:
    """Per (season, team) totals from ``(season, home, away, home_score, away_score)`` rows of
    played regular-season games (forfeits excluded by the caller)."""
    totals: dict[tuple[int, str], _Totals] = {}
    for season, home, away, home_score, away_score in rows:
        for team, scored, allowed in (
            (home, home_score, away_score),
            (away, away_score, home_score),
        ):
            entry = totals.setdefault((season, team), _Totals())
            entry.games += 1
            entry.wins += scored > allowed
            entry.points_for += scored
            entry.points_against += allowed
    return totals


def standings_findings(
    standings: list[Standing],
    game_rows: Iterable[tuple[int, str, str, int, int]],
    overtime: Mapping[tuple[int, str], tuple[int, int]],
    expected_seasons: list[int],
    present_seasons: set[int],
) -> list[Finding]:
    """Wins/losses/games and points (less overtime points) against the games, per team-season.

    ``overtime``: (season, team) -> (points for, points against) scored in overtime periods.
    """
    totals = results(game_rows)
    unexplained_rows: list[str] = []
    points_explained = 0
    for row in standings:
        key = (row.season, row.team)
        got = totals.get(key)
        if got is None:
            unexplained_rows.append(f"{row.season} {row.team} not in the games")
            continue
        if (row.games, row.wins, row.losses) != (got.games, got.wins, got.games - got.wins):
            unexplained_rows.append(f"{row.season} {row.team} W-L {row.wins}-{row.losses}")
            continue
        ot_for, ot_against = overtime.get(key, (0, 0))
        if (row.points_for, row.points_against) == (
            got.points_for - ot_for,
            got.points_against - ot_against,
        ):
            points_explained += bool(ot_for or ot_against)
        else:
            unexplained_rows.append(
                f"{row.season} {row.team} points {row.points_for}-{row.points_against} vs games "
                f"{got.points_for}-{got.points_against} less overtime {ot_for}-{ot_against}"
            )
    explained = {POINTS_REGULATION: points_explained} if points_explained else {}
    findings = [
        Finding(
            name="standings_vs_results",
            count=len(unexplained_rows) + points_explained,
            unexplained=len(unexplained_rows),
            examples=unexplained_rows[:5],
            reasons=explained,
        )
    ]
    reasons: dict[str, int] = {}
    for season in expected_seasons:
        if season in present_seasons:
            continue
        if season == 2019:
            reasons[SEASON_CANCELLED] = reasons.get(SEASON_CANCELLED, 0) + 1
        elif season == 2026:
            reasons[LIVE] = reasons.get(LIVE, 0) + 1
        else:
            reasons[FROM_RESULTS] = reasons.get(FROM_RESULTS, 0) + 1
    findings.append(
        Finding(
            name="standings_season_missing",
            count=sum(reasons.values()),
            unexplained=0,
            examples=[],
            reasons=reasons,
        )
    )
    return findings
