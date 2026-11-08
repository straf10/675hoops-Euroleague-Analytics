"""``eurohoops ingest``, ``ingest-bios`` and ``people``: fetch raw data into the local cache."""

from typing import Annotated

import typer

from eurohoops.cli._shared import log
from eurohoops.config import (
    BIO_EL_SEASONS,
    EUROCUP,
    EUROLEAGUE,
    LIVE_SEASON,
    PLAYER_BIOS,
    SITE_SEASONS,
    Competition,
)
from eurohoops.ingest import euroleague
from eurohoops.ingest.bios import build_bios, ingest_bios, refresh_people
from eurohoops.ingest.euroleague import RawGame
from eurohoops.ingest.http import Fetcher, make_client
from eurohoops.parse.games import (
    build_games_table,
    build_team_seasons,
    build_teams_table,
    write_table,
)


def ingest(
    ctx: typer.Context,
    *,
    seasons: Annotated[
        list[int] | None,
        typer.Option(help="Season start years, space-separated: --seasons 2023 2024 2025 2026"),
    ] = None,
    details: Annotated[
        bool,
        typer.Option(help="Also cache game details (box/PBP/shots)"),
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
    competition: Annotated[
        str,
        typer.Option(
            help="euroleague (default) or eurocup (research only: experiments/eurocup.md)"
        ),
    ] = "euroleague",
    fetch_missing: Annotated[
        bool,
        typer.Option(
            help="Seeding only: fetch a finished season's schedule that is not cached yet (once)"
        ),
    ] = False,
    box_and_pbp_only: Annotated[
        bool,
        typer.Option(
            help="With --details, fetch only Boxscore and PlaybyPlay (EuroCup M1/M5 inputs)"
        ),
    ] = False,
) -> None:
    """Fetch EuroLeague results into the raw cache and rebuild the staging tables.

    With no season options the default seasons are staged (2007 to the live one).
    Past seasons are read from the raw cache only; the live season goes to the network.
    ``--competition eurocup`` stages EuroCup into its own files; the EuroLeague files are untouched.
    """
    comp = _COMPETITIONS.get(competition)
    if comp is None:
        raise typer.BadParameter(f"unknown competition {competition!r}; use euroleague or eurocup")
    try:
        extra = [int(arg) for arg in ctx.args]
    except ValueError as exc:
        raise typer.BadParameter(f"unexpected arguments {ctx.args}") from exc
    history = range(from_season, LIVE_SEASON + 1) if from_season is not None else ()
    if current_only and (seasons or extra or from_season is not None):
        raise typer.BadParameter("--current-only cannot be combined with season options")
    if current_only:
        chosen = [LIVE_SEASON]
    else:
        chosen = sorted({*(seasons or []), *extra, *history}) or list(comp.default_seasons)
    with make_client() as client:
        fetcher = Fetcher(client, euroleague.MIN_INTERVAL_S)
        try:
            schedules = euroleague.ingest_seasons(
                fetcher,
                comp.raw_dir,
                chosen,
                details,
                LIVE_SEASON,
                code=comp.code,
                fetch_missing=fetch_missing,
                endpoints=_BOX_PBP if box_and_pbp_only else euroleague.DETAIL_ENDPOINTS,
            )
        except euroleague.PastSeasonNotCachedError as exc:
            log.error("%s", exc)
            raise typer.Exit(code=1) from exc
    if box_and_pbp_only:
        # Fetch-only mode: a season subset must not overwrite the full staged schedule.
        log.info("box scores and play-by-play cached; staging not rewritten")
        return
    if comp is EUROCUP:
        schedules = _without_tied_finals(schedules)
    games, teams = build_games_table(schedules), build_teams_table(schedules)
    team_seasons = build_team_seasons(schedules)
    write_table(games, comp.staging_games)
    write_table(teams, comp.staging_teams)
    write_table(team_seasons, comp.staging_team_seasons)
    log.info(
        "wrote %d games (%d played) to %s",
        len(games),
        games["played"].sum(),
        comp.staging_games,
    )


_COMPETITIONS: dict[str, Competition] = {"euroleague": EUROLEAGUE, "eurocup": EUROCUP}
_BOX_PBP = ("Boxscore", "PlaybyPlay")


def _without_tied_finals(schedules: dict[int, list[RawGame]]) -> dict[int, list[RawGame]]:
    """Leave out EuroCup games played with equal final scores. A basketball game cannot end level
    and the schedule still names a winner, so the real score is unknown: such a game is not rated
    (experiments/eurocup.md). EuroLeague has no such game; its schema would reject one."""
    kept: dict[int, list[RawGame]] = {}
    for season, games in schedules.items():
        ties = [g for g in games if g["played"] and g["local"]["score"] == g["road"]["score"]]
        if ties:
            log.warning(
                "EuroCup %d: %d played games with equal scores left out: %s",
                season,
                len(ties),
                ", ".join(g["identifier"] for g in ties),
            )
        tied = {g["identifier"] for g in ties}
        kept[season] = [g for g in games if g["identifier"] not in tied]
    return kept


def ingest_bios_command() -> None:
    """Cache the EuroLeague people listings and stage their birth dates and countries.

    Local backfill, like ``ingest --details``: never run in CI.
    """
    with make_client() as client:
        fetched = ingest_bios(
            Fetcher(client, euroleague.MIN_INTERVAL_S),
            el_raw=EUROLEAGUE.raw_dir,
            el_seasons=BIO_EL_SEASONS,
        )
    bios = build_bios(EUROLEAGUE.raw_dir)
    write_table(bios, PLAYER_BIOS)
    dated = int(bios["birth_date"].notna().sum())
    typer.echo(
        f"fetched {fetched} EuroLeague seasons; {len(bios)} bios, with a birth date: {dated}; "
        f"wrote {PLAYER_BIOS}"
    )


def people() -> None:
    """Refetch the live season's EuroLeague people listing (one call; positions for the stats
    site). Overwrites ``people/E{LIVE_SEASON}.json.gz`` atomically. Earlier site seasons are
    fetched once if missing from the cache (a cold CI cache) and never refetched."""
    with make_client() as client:
        fetcher = Fetcher(client, euroleague.MIN_INTERVAL_S)
        past = range(LIVE_SEASON - SITE_SEASONS + 1, LIVE_SEASON)
        filled = ingest_bios(fetcher, el_raw=EUROLEAGUE.raw_dir, el_seasons=past)
        count = refresh_people(fetcher, el_raw=EUROLEAGUE.raw_dir, season=LIVE_SEASON)
    if filled:
        typer.echo(f"people: {filled} missing earlier season(s) cached")
    typer.echo(f"people E{LIVE_SEASON}: {count} rows")
