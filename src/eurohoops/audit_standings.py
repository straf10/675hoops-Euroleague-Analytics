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


@dataclass(frozen=True)
class SourceResidual:
    """A standings row the source table gets wrong against its own games (documented).

    Explained only while both sides show exactly these numbers: the standings row (games, wins,
    losses, points for, points against) and the games (wins, losses, points for and against
    less the overtime points). A changed snapshot or changed results are unexplained again.
    """

    standing: tuple[int, int, int, int, int]
    results: tuple[int, int, int, int]
    reason: str  # str.format fields: pf, pa (standing); gw, gl, gpf, gpa (games)


SOURCE_RESIDUALS: dict[tuple[int, str], SourceResidual] = {
    (2022, "PAN"): SourceResidual(
        standing=(34, 9, 23, 2649, 2773),
        results=(11, 23, 2649, 2773),
        reason="source standings table inconsistent with its own results: 2022 PAN lists 9-23 "
        "with 34 games (W+L is 32); its own 34 games give {gw}-{gl}, while the points agree "
        "({gpf}-{gpa} from the games less overtime, standings {pf}-{pa}). No cached standings "
        "round or excluded game reproduces the table.",
    ),
    (2023, "BAS"): SourceResidual(
        standing=(34, 18, 16, 2847, 2865),
        results=(18, 16, 2849, 2867),
        reason="source standings table inconsistent with its own results: 2023 BAS points "
        "{pf}-{pa} against {gpf}-{gpa} from the games less overtime (both sides 2 points lower; "
        "W-L {gw}-{gl} agree; the raw box scores agree with the game scores). No forfeit or "
        "changed result found.",
    ),
    (2023, "ASV"): SourceResidual(
        standing=(34, 9, 25, 2646, 2859),
        results=(9, 25, 2648, 2861),
        reason="source standings table inconsistent with its own results: 2023 ASV points "
        "{pf}-{pa} against {gpf}-{gpa} from the games less overtime (both sides 2 points lower; "
        "W-L {gw}-{gl} agree; the raw box scores agree with the game scores). No forfeit or "
        "changed result found.",
    ),
}


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


def _residual_reason(
    row: Standing,
    got: _Totals,
    ot: tuple[int, int],
    residuals: Mapping[tuple[int, str], SourceResidual],
) -> str | None:
    """The documented reason for a mismatched row, when its numbers are exactly the documented
    ones on both sides; None otherwise."""
    known = residuals.get((row.season, row.team))
    if known is None:
        return None
    standing = (row.games, row.wins, row.losses, row.points_for, row.points_against)
    games = (got.wins, got.games - got.wins, got.points_for - ot[0], got.points_against - ot[1])
    if standing != known.standing or games != known.results:
        return None
    return known.reason.format(
        pf=row.points_for,
        pa=row.points_against,
        gw=got.wins,
        gl=got.games - got.wins,
        gpf=got.points_for - ot[0],
        gpa=got.points_against - ot[1],
    )


def standings_findings(
    standings: list[Standing],
    game_rows: Iterable[tuple[int, str, str, int, int]],
    overtime: Mapping[tuple[int, str], tuple[int, int]],
    expected_seasons: list[int],
    present_seasons: set[int],
    *,
    residuals: Mapping[tuple[int, str], SourceResidual] = SOURCE_RESIDUALS,
) -> list[Finding]:
    """Wins/losses/games and points (less overtime points) against the games, per team-season.

    ``overtime``: (season, team) -> (points for, points against) scored in overtime periods.
    """
    totals = results(game_rows)
    unexplained_rows: list[str] = []
    points_explained = 0
    source_explained: dict[str, int] = {}
    for row in standings:
        key = (row.season, row.team)
        got = totals.get(key)
        if got is None:
            unexplained_rows.append(f"{row.season} {row.team} not in the games")
            continue
        ot_for, ot_against = overtime.get(key, (0, 0))
        wl_ok = (row.games, row.wins, row.losses) == (got.games, got.wins, got.games - got.wins)
        points_ok = (row.points_for, row.points_against) == (
            got.points_for - ot_for,
            got.points_against - ot_against,
        )
        if wl_ok and points_ok:
            points_explained += bool(ot_for or ot_against)
            continue
        reason = _residual_reason(row, got, (ot_for, ot_against), residuals)
        if reason is not None:
            source_explained[reason] = source_explained.get(reason, 0) + 1
            continue
        if not wl_ok:
            unexplained_rows.append(f"{row.season} {row.team} W-L {row.wins}-{row.losses}")
        else:
            unexplained_rows.append(
                f"{row.season} {row.team} points {row.points_for}-{row.points_against} vs games "
                f"{got.points_for}-{got.points_against} less overtime {ot_for}-{ot_against}"
            )
    explained = {POINTS_REGULATION: points_explained} if points_explained else {}
    explained.update(source_explained)
    findings = [
        Finding(
            name="standings_vs_results",
            count=len(unexplained_rows) + points_explained + sum(source_explained.values()),
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
