"""``eurohoops build``, ``continuity``, ``stints`` and ``possessions``: marts and their checks."""

from typing import Annotated

import pandas as pd
import typer

from eurohoops.cli._shared import log
from eurohoops.config import (
    EUROLEAGUE,
    LIVE_SEASON,
    MART_PATH,
    POSSESSION_REPORT,
    SQL_DIR,
    STINT_REPORT,
    STINTS_MART_REPORT,
    TEAM_CONTINUITY_REPORT,
)
from eurohoops.logs import write_json
from eurohoops.marts import build_marts, read_games, read_table, write_tables
from eurohoops.parse.continuity import continuity_report
from eurohoops.parse.possession_report import possession_report
from eurohoops.parse.stints import validate_sample
from eurohoops.parse.stints_mart import build_stints_mart, mart_report
from eurohoops.parse.team_box import build_team_games
from eurohoops.publish import DISPLAY_CODES


def build() -> None:
    """Build the DuckDB marts from staging (and ``team_games`` from the raw box-score cache)."""
    build_marts(MART_PATH, SQL_DIR)
    team_games = build_team_games(read_games(MART_PATH, EUROLEAGUE.name), EUROLEAGUE.raw_dir)
    write_tables(
        MART_PATH, {"team_games": team_games.table, "team_games_missing": team_games.missing}
    )
    typer.echo(
        f"team_games: {team_games.table['game_id'].nunique()} games, "
        f"{len(team_games.missing)} played games without box lines"
    )
    _team_continuity()
    typer.echo(f"marts written to {MART_PATH}")


def _team_continuity() -> None:
    """Stage-to-marts ``team_seasons`` and print the live season's team changes (skipped before
    the first ingest that stages team seasons). The report file is ``eurohoops continuity``:
    the daily workflow stages fewer seasons, so ``build`` never rewrites it."""
    if not EUROLEAGUE.staging_team_seasons.exists():
        return
    team_seasons = pd.read_parquet(EUROLEAGUE.staging_team_seasons).assign(
        competition=EUROLEAGUE.name
    )
    write_tables(MART_PATH, {"team_seasons": team_seasons})
    report = continuity_report(team_seasons)
    for competition, block in report.items():
        live = block["seasons"].get(str(LIVE_SEASON))
        if live is None or live.get("first_season_in_data"):
            continue
        shown = DISPLAY_CODES.get(competition, {})
        changes = ", ".join(
            f"{kind} {' '.join(shown.get(e['team'], e['team']) for e in live[kind])}"
            for kind in ("new", "returning", "left")
            if live[kind]
        )
        typer.echo(f"{competition} {LIVE_SEASON} teams: {changes or 'no changes'}")
    flagged = sum(len(block["review_name_changes"]) for block in report.values())
    if flagged:
        typer.echo(f"team continuity: {flagged} name changes to review (eurohoops continuity)")


def continuity() -> None:
    """Write reports/team_continuity.json from the marts: new, returning and departed codes per
    season, and name changes to review (a code another club took over would show up there)."""
    team_seasons = read_table(MART_PATH, "team_seasons")
    if team_seasons is None:
        log.error("no team_seasons in the marts; run: eurohoops ingest, then eurohoops build")
        raise typer.Exit(1)
    report = continuity_report(team_seasons)
    write_json(TEAM_CONTINUITY_REPORT, report)
    for competition, block in report.items():
        for item in block["review_name_changes"]:  # the names are in the file
            typer.echo(f"review: {competition} {item['season']} {item['team']} changed name")
    typer.echo(f"wrote {TEAM_CONTINUITY_REPORT}")


def stints(
    mart: Annotated[
        bool,
        typer.Option(help="Build the 2011+ stints mart and write reports/stints_mart.json instead"),
    ] = False,
) -> None:
    """Validate EuroLeague stints on the seeded 50-game sample (reads the local raw cache).

    With ``--mart``: build the ``stints`` and ``stint_game_checks`` tables for every cached
    game from 2011-12 (needs ``eurohoops build`` first for ``team_games``).
    """
    if mart:
        games = read_games(MART_PATH, EUROLEAGUE.name)
        team_games = read_table(MART_PATH, "team_games", EUROLEAGUE.name)
        if team_games is None:
            log.error("no team_games in the marts; run: eurohoops build")
            raise typer.Exit(code=1)
        built = build_stints_mart(EUROLEAGUE.raw_dir, games)
        write_tables(MART_PATH, {"stints": built.stints, "stint_game_checks": built.checks})
        summary = mart_report(built, games, team_games)
        write_json(STINTS_MART_REPORT, summary)
        spans = {
            span: "no games" if rate is None else f"{rate:.1%}"
            for span, rate in (
                ("2011-14", summary["pass_rate_2011_2014"]),
                ("2015+", summary["pass_rate_2015_on"]),
            )
        }
        typer.echo(
            f"{summary['games']} games, {summary['stints']} stints; pass rate 2011-14 "
            f"{spans['2011-14']}, 2015+ {spans['2015+']}; wrote {STINTS_MART_REPORT}"
        )
        return
    report = validate_sample(EUROLEAGUE.raw_dir)
    write_json(STINT_REPORT, report)
    rates = ", ".join(f"{check} {rate:.0%}" for check, rate in report["pass_rate"].items())
    typer.echo(
        f"{report['games']} games: all checks {report['all_checks_pass_rate']:.0%} ({rates}); "
        f"wrote {STINT_REPORT}"
    )


def possessions() -> None:
    """Validate ``team_games``: coverage, points, box vs play-by-play possessions."""
    table = read_table(MART_PATH, "team_games")
    missing = read_table(MART_PATH, "team_games_missing")
    if table is None or missing is None:
        log.error("no team_games in the marts; run: eurohoops build")
        raise typer.Exit(code=1)
    report = possession_report(
        table,
        missing=missing,
        games=read_games(MART_PATH, EUROLEAGUE.name).assign(competition=EUROLEAGUE.name),
        euroleague_raw=EUROLEAGUE.raw_dir,
    )
    write_json(POSSESSION_REPORT, report)
    sample = report["euroleague_pbp_sample"]
    agreement = (
        "no EuroLeague play-by-play cached"
        if sample is None
        else f"EuroLeague sample within 2: {sample['within_tolerance_share_of_teams']:.1%} of teams"
    )
    typer.echo(
        f"{len(report['missing_games'])} games missing, "
        f"{len(report['points_mismatches'])} points mismatches; {agreement}; "
        f"wrote {POSSESSION_REPORT}"
    )
