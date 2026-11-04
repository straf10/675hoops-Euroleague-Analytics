"""The stats site's inputs and payloads."""

import json
from datetime import datetime
from typing import Any

import pandas as pd

from eurohoops.api.read.store import NotFound, Store, _el_box, _el_games
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


def stats_inputs(store: Store) -> Inputs:
    """The stats site's inputs, built once per Store (the validation reads the same frames)."""

    def make() -> Inputs:
        games, teams = _el_games(store)
        box = _el_box(store)
        window = site_window(box.players["season"].unique())
        played = games[games["played"] & games["season"].isin(window)]
        raw = store.path(EUROLEAGUE.raw_dir)
        seasons = (int(s) for s in box.players["season"].unique())
        cached = [s for s in seasons if el_people_path(raw, s).exists()]
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
            roster=read_rosters(raw, sorted(cached)),
            units=load_units(raw, games, window, DISPLAY_CODES[EUROLEAGUE.name]),
            assists=assists,
            win_shares=box_win_shares(box.players, box.teams),
            wp=_wp_lines(store, games),
            coaches=_coach_games(store, games),
            styles=_coach_styles(store, games),
        )

    return store.memo("stats_inputs", make)


def _coach_games(store: Store, games: pd.DataFrame) -> pd.DataFrame | None:
    """Team-game coach rows with the walk-forward history Elo's pre-game probabilities (its tuned
    parameters, replayed from the first warm-up season); None without the history report."""
    history = EUROLEAGUE.history_backtests[0]
    if not store.path(history.report).exists():
        return None
    params = load_tuned_model(store.path(history.report)).params
    return coach_games(store.path(EUROLEAGUE.raw_dir), with_elo(games, params, history.warmup[0]))


def _coach_styles(store: Store, games: pd.DataFrame) -> StyleIndex | None:
    """Per-game coaching style from the cached play-by-play and box scores, once per Store; None
    without the coach history report (no coach pages)."""

    def make() -> StyleIndex:
        return game_styles(store.path(EUROLEAGUE.raw_dir), games)

    if not store.path(EUROLEAGUE.history_backtests[0].report).exists():
        return None
    return store.memo("coach_styles", make)


def _wp_lines(store: Store, games: pd.DataFrame) -> WpLines | None:
    """The frozen WP v1 lines (stats/wp.py), once per Store; None without its gate report."""

    def make() -> WpLines | None:
        if not store.path(WP_REPORT).exists():
            return None
        report = json.loads(store.path(WP_REPORT).read_text(encoding="utf-8"))
        logged = logged_pre(store.path(EUROLEAGUE.prediction_log))
        return wp_lines(games, store.path(EUROLEAGUE.raw_dir), report, logged)

    return store.memo("wp_lines", make)


def stats_payloads(store: Store, now: datetime) -> dict[str, dict[str, Any]]:
    """Every stats file by relative path (``stats.export.build_payloads``), built once per Store;
    ``meta.json`` carries the time of that build."""
    return store.memo("stats", lambda: build_payloads(stats_inputs(store), now))


def stats_index(store: Store, now: datetime) -> dict[str, Any]:
    return {"files": sorted(stats_payloads(store, now))}


def stats_file(store: Store, path: str, now: datetime) -> dict[str, Any]:
    files = stats_payloads(store, now)
    if path not in files:
        raise NotFound(f"no stats file '{path}'; GET /stats lists the {len(files)} files")
    return files[path]
