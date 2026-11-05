"""The stats site's inputs and payloads."""

import json
from datetime import datetime
from typing import Any

import pandas as pd

from eurohoops.api.read.store import NotFound, Store, cached
from eurohoops.config import (
    EUROLEAGUE,
    LIVE_SEASON,
    WP_REPORT,
)
from eurohoops.eval.backtest import load_tuned_model
from eurohoops.ingest.bios import el_people_path
from eurohoops.models.roster import read_rosters
from eurohoops.publish import DISPLAY_CODES
from eurohoops.stats.assists import game_assists
from eurohoops.stats.coach_style import StyleIndex, game_styles
from eurohoops.stats.coaches import coach_games, with_elo
from eurohoops.stats.export import (
    Inputs,
    build_payloads,
    load_cached_standings,
    site_window,
)
from eurohoops.stats.positions import games_by_club, season_positions
from eurohoops.stats.runs import game_runs
from eurohoops.stats.shots import build_shots
from eurohoops.stats.units import load_units
from eurohoops.stats.win_shares import box_win_shares
from eurohoops.stats.wp import WpLines, logged_pre, wp_lines


@cached
def stats_inputs(store: Store) -> Inputs:
    """The stats site's inputs, built once per Store (the validation reads the same frames)."""
    games, teams = store.euroleague_games()
    box = store.euroleague_box()
    window = site_window(box.players["season"].unique())
    played = games[games["played"] & games["season"].isin(window)]
    raw = store.path(EUROLEAGUE.raw_dir)
    seasons = (int(s) for s in box.players["season"].unique())
    rostered = [s for s in seasons if el_people_path(raw, s).exists()]
    # Every played game's assists, not only the site window: the splits keep full careers, and
    # Win Shares need the assisted field goals of every box score.
    assists = game_assists(raw, games[games["played"]])
    return Inputs(
        games=games,
        names=dict(teams.itertuples(index=False)),
        box=box,
        shots=build_shots(raw, games),
        codes=DISPLAY_CODES[EUROLEAGUE.name],
        live_season=LIVE_SEASON,
        official_standings=load_cached_standings(raw),
        positions=season_positions(raw, games_by_club(box.players)),
        runs=game_runs(raw, played),
        roster=read_rosters(raw, sorted(rostered)),
        units=load_units(raw, games, window, DISPLAY_CODES[EUROLEAGUE.name]),
        assists=assists,
        win_shares=box_win_shares(box.players, box.teams),
        wp=_wp_lines(store),
        coaches=coach_rows(store, games),
        styles=_coach_styles(store),
    )


def coach_rows(store: Store, games: pd.DataFrame) -> pd.DataFrame | None:
    """Team-game coach rows with the walk-forward history Elo's pre-game probabilities (its tuned
    parameters, replayed from the first warm-up season); None without the history report."""
    history = EUROLEAGUE.history_backtests[0]
    if not store.path(history.report).exists():
        return None
    params = load_tuned_model(store.path(history.report)).params
    return coach_games(store.path(EUROLEAGUE.raw_dir), with_elo(games, params, history.warmup[0]))


def _coach_styles(store: Store) -> StyleIndex | None:
    """Per-game coaching style of the EuroLeague games from the cached play-by-play and box scores,
    once per Store; None without the coach history report (no coach pages)."""
    if not store.path(EUROLEAGUE.history_backtests[0].report).exists():
        return None
    return _game_styles(store)


@cached
def _game_styles(store: Store) -> StyleIndex:
    return game_styles(store.path(EUROLEAGUE.raw_dir), store.euroleague_games()[0])


@cached
def _wp_lines(store: Store) -> WpLines | None:
    """The frozen WP v1 lines (stats/wp.py) of the EuroLeague games, once per Store; None without
    its gate report."""
    if not store.path(WP_REPORT).exists():
        return None
    report = json.loads(store.path(WP_REPORT).read_text(encoding="utf-8"))
    logged = logged_pre(store.path(EUROLEAGUE.prediction_log))
    return wp_lines(store.euroleague_games()[0], store.path(EUROLEAGUE.raw_dir), report, logged)


@cached(key=lambda now: ())
def stats_payloads(store: Store, now: datetime) -> dict[str, dict[str, Any]]:
    """Every stats file by relative path (``stats.export.build_payloads``), built once per Store;
    ``meta.json`` carries the time of that (first) build."""
    return build_payloads(stats_inputs(store), now)


def stats_index(store: Store, now: datetime) -> dict[str, Any]:
    return {"files": sorted(stats_payloads(store, now))}


def stats_file(store: Store, path: str, now: datetime) -> dict[str, Any]:
    files = stats_payloads(store, now)
    if path not in files:
        raise NotFound(f"no stats file '{path}'; GET /stats lists the {len(files)} files")
    return files[path]
