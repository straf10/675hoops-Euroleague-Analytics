"""``eurohoops publish`` and ``export-stats``: the site and stats-site data."""

import json
from pathlib import Path
from typing import Annotated

import typer
from fastapi.testclient import TestClient

from eurohoops.api.app import create_app
from eurohoops.api.export import (
    WEB_DIR,
    RawStore,
    publish_files,
    stats_files,
    write_publish,
    write_stats_files,
)
from eurohoops.api.readmodel import Store, stats_inputs
from eurohoops.cli._shared import utc_now
from eurohoops.config import EUROLEAGUE, MART_PATH, SITE_DATA
from eurohoops.stats.downloads import DOWNLOADS_DIR, build_downloads, write_downloads
from eurohoops.stats.export import STATS_DIR, site_window
from eurohoops.stats.onoff import load_onoff, write_onoff
from eurohoops.stats.validate import write_validation


def publish() -> None:
    """Write the site data (site.json and api/) the Astro front-end renders, from the API."""
    now = utc_now()
    store = Store()
    client = TestClient(create_app(store, lambda: now))
    files = publish_files(client, store, typer.echo)
    write_publish(WEB_DIR, files)
    typer.echo(f"wrote {SITE_DATA} and {len(files) - 1} API files")


def export_stats(
    from_cache: Annotated[
        bool,
        typer.Option(help="Read games from the cached schedules instead of the marts (no DuckDB)"),
    ] = False,
    raw_dir: Annotated[Path, typer.Option(help="EuroLeague raw cache")] = EUROLEAGUE.raw_dir,
    out: Annotated[Path, typer.Option(help="Where the stats JSON goes")] = STATS_DIR,
) -> None:
    """Write the EuroLeague stats-site data (players, teams, game logs, shots), from the API."""
    now = utc_now()
    store = RawStore(from_cache=from_cache, raw_dir=raw_dir)
    files = stats_files(TestClient(create_app(store, lambda: now)))
    write_stats_files(out, files)
    inputs = stats_inputs(store)
    window = site_window(inputs.box.players["season"].unique())
    onoff = load_onoff(MART_PATH, raw_dir, inputs.games, window)
    write_onoff(out, onoff)
    # validation first: on an error it writes validation.json, then fails the export
    write_validation(out, stats_inputs(store), now)
    write_downloads(DOWNLOADS_DIR, build_downloads(stats_inputs(store), now))
    seasons = json.loads(files["meta.json"])["seasons"]
    typer.echo(
        f"wrote {len(files)} files to {out}: {len(seasons)} seasons, "
        f"{len(json.loads(files['players.json'])['players'])} players, "
        f"{sum(s['games_without_box'] for s in seasons)} played games without a box score"
    )
