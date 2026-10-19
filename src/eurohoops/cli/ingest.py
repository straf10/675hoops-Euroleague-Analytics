"""``eurohoops ingest``, ``ingest-bios`` and ``people``: fetch raw data into the local cache."""

from typing import Annotated

import pandas as pd
import typer

from eurohoops.cli._shared import CompetitionName, CompetitionOption, log
from eurohoops.config import (
    BIO_EL_SEASONS,
    COMPETITIONS,
    EUROLEAGUE,
    GBL,
    GBL_BOX_FILL,
    GBL_MINUTES_REPORT,
    GBL_PBP,
    GBL_PLAYER_BOX,
    GBL_TEAM_BOX,
    GREEK_EL_CLUBS,
    LIVE_SEASON,
    PLAYER_BIOS,
    SITE_SEASONS,
)
from eurohoops.ingest import euroleague, gbl
from eurohoops.ingest.bios import build_bios, ingest_bios, refresh_people
from eurohoops.ingest.http import Fetcher, make_client
from eurohoops.parse.box import build_box_tables
from eurohoops.parse.games import (
    build_games_table,
    build_gbl_tables,
    build_gbl_team_seasons,
    build_team_seasons,
    build_teams_table,
    write_table,
)
from eurohoops.parse.gbl_pbp import build_pbp_table


def ingest(
    ctx: typer.Context,
    *,
    competition: CompetitionOption = CompetitionName.euroleague,
    seasons: Annotated[
        list[int] | None,
        typer.Option(help="Season start years, space-separated: --seasons 2023 2024 2025 2026"),
    ] = None,
    details: Annotated[
        bool,
        typer.Option(help="Also cache game details (EuroLeague: box/PBP/shots; GBL: box scores)"),
    ] = False,
    pbp: Annotated[
        bool,
        typer.Option(help="GBL: also cache the chosen seasons' play-by-play (local backfill)"),
    ] = False,
    from_season: Annotated[
        int | None,
        typer.Option(help="Stage every season from this start year to the live one"),
    ] = None,
    current_only: Annotated[
        bool,
        typer.Option(
            help="Stage only the live season (fast local runs). The staged tables then lack the "
            "history: run a plain ingest before build, or M5 cannot run"
        ),
    ] = False,
) -> None:
    """Fetch results into the raw cache and rebuild the competition's staging tables.

    With no season options the default seasons are staged (EuroLeague: 2007 to the live one).
    Past seasons are read from the raw cache only; the live season goes to the network.

    With ``--pbp`` the chosen seasons only select which games get play-by-play; the staging
    tables still cover every default season.
    """
    try:
        extra = [int(arg) for arg in ctx.args]
    except ValueError as exc:
        raise typer.BadParameter(f"unexpected arguments {ctx.args}") from exc
    comp = COMPETITIONS[competition]
    history = range(from_season, LIVE_SEASON + 1) if from_season is not None else ()
    if current_only and (seasons or extra or from_season is not None):
        raise typer.BadParameter("--current-only cannot be combined with season options")
    if current_only:
        chosen = [LIVE_SEASON]
    else:
        chosen = sorted({*(seasons or []), *extra, *history}) or list(comp.default_seasons)
    if pbp and comp is not GBL:
        raise typer.BadParameter("--pbp is for --competition gbl (EuroLeague PBP: --details)")
    with make_client() as client:
        if comp is GBL:
            fetcher = Fetcher(client, gbl.MIN_INTERVAL_S)
            staged = sorted({*chosen, *comp.default_seasons}) if pbp else chosen
            rounds = gbl.ingest_gbl(
                fetcher,
                comp.raw_dir,
                staged,
                details,
                LIVE_SEASON,
                pbp_seasons=chosen if pbp else (),
            )
            games, teams = build_gbl_tables(rounds)
            team_seasons = build_gbl_team_seasons(rounds)
            if details or pbp:
                tables = build_box_tables(comp.raw_dir, games)
                write_table(tables.player_box, GBL_PLAYER_BOX)
                write_table(tables.team_box, GBL_TEAM_BOX)
                write_table(tables.fill, GBL_BOX_FILL)
                tables.minutes.to_csv(GBL_MINUTES_REPORT, index=False)
            if pbp:
                write_table(build_pbp_table(comp.raw_dir, games), GBL_PBP)
        else:
            fetcher = Fetcher(client, euroleague.MIN_INTERVAL_S)
            try:
                schedules = euroleague.ingest_seasons(
                    fetcher, comp.raw_dir, chosen, details, LIVE_SEASON
                )
            except euroleague.PastSeasonNotCachedError as exc:
                log.error("%s", exc)
                raise typer.Exit(code=1) from exc
            games, teams = build_games_table(schedules), build_teams_table(schedules)
            team_seasons = build_team_seasons(schedules)
    write_table(games, comp.staging_games)
    write_table(teams, comp.staging_teams)
    write_table(team_seasons, comp.staging_team_seasons)
    log.info(
        "wrote %d games (%d played) to %s", len(games), games["played"].sum(), comp.staging_games
    )


def ingest_bios_command() -> None:
    """Cache player bios for entity resolution (ESAKE player pages for every staged GBL player,
    EuroLeague season people 2007-2025) and stage their birth dates and countries.

    Local backfill, like ``ingest --pbp``: never run in CI. Needs the GBL box scores staged.
    """
    if not GBL_PLAYER_BOX.exists():
        log.error("no staged GBL box scores; run: eurohoops ingest --competition gbl --details")
        raise typer.Exit(code=1)
    box = pd.read_parquet(GBL_PLAYER_BOX, columns=["player_id", "team", "seconds"])
    per_player = box.assign(big_two=box["team"].isin(GREEK_EL_CLUBS)).groupby("player_id")
    order = per_player.agg(big_two=("big_two", "any"), seconds=("seconds", "sum"))
    # the Greek EuroLeague clubs' players first (the silver set), then by GBL minutes
    gbl_ids = order.sort_values(["big_two", "seconds"], ascending=False, kind="stable").index
    with make_client() as client:
        fetched = ingest_bios(
            Fetcher(client, gbl.MIN_INTERVAL_S),
            Fetcher(client, euroleague.MIN_INTERVAL_S),
            gbl_raw=GBL.raw_dir,
            el_raw=EUROLEAGUE.raw_dir,
            gbl_ids=gbl_ids,
            el_seasons=BIO_EL_SEASONS,
        )
    bios = build_bios(GBL.raw_dir, EUROLEAGUE.raw_dir)
    write_table(bios, PLAYER_BIOS)
    dated = bios.groupby("competition")["birth_date"].apply(lambda s: int(s.notna().sum()))
    typer.echo(
        f"fetched {fetched[0]} ESAKE pages, {fetched[1]} EuroLeague seasons; "
        f"{len(bios)} bios, with a birth date: {dated.to_dict()}; wrote {PLAYER_BIOS}"
    )


def people() -> None:
    """Refetch the live season's EuroLeague people listing (one call; positions for the stats
    site). Overwrites ``people/E{LIVE_SEASON}.json.gz`` atomically. Earlier site seasons are
    fetched once if missing from the cache (a cold CI cache) and never refetched."""
    with make_client() as client:
        fetcher = Fetcher(client, euroleague.MIN_INTERVAL_S)
        past = range(LIVE_SEASON - SITE_SEASONS + 1, LIVE_SEASON)
        _, filled = ingest_bios(
            fetcher,
            fetcher,
            gbl_raw=GBL.raw_dir,
            el_raw=EUROLEAGUE.raw_dir,
            gbl_ids=(),
            el_seasons=past,
        )
        count = refresh_people(fetcher, el_raw=EUROLEAGUE.raw_dir, season=LIVE_SEASON)
    if filled:
        typer.echo(f"people: {filled} missing earlier season(s) cached")
    typer.echo(f"people E{LIVE_SEASON}: {count} rows")
