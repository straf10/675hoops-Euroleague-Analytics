"""The site payload, the upcoming games and one game's predictions."""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from eurohoops.api.read.store import NotFound, Store, forecast_fields, jsonable, stamp
from eurohoops.config import (
    EUROLEAGUE,
    LIVE_SEASON,
    MART_PATH,
    SITE_FORECAST_MODEL,
    Competition,
)
from eurohoops.eval.forecasts import build_forecasts
from eurohoops.logs import displayed_rows, is_late
from eurohoops.marts import data_volume
from eurohoops.model_catalog import CATALOG, active_logs
from eurohoops.publish import Section, site_data

# The page leads with SITE_FORECAST_MODEL; the team models appear only in its small comparison.
FORECAST_MODELS = {
    **{m.tag: m.label for m in CATALOG if m.label is not None},
    "mkt": "MKT",  # benchmark: the bookmakers' pre-tip line
}


def _path_or_none(store: Store, relative: Path | None) -> Path | None:
    return None if relative is None else store.path(relative)


def site(store: Store, now: datetime) -> dict[str, Any]:
    """``site.json``: the payload ``publish.site_data`` builds from the EuroLeague logs,
    scorecard, tuned Elo parameters and games (as ``eurohoops publish`` assembles it)."""
    sections = []
    for title, comp in (("EuroLeague", EUROLEAGUE),):
        games = store.games(comp)
        scorecard = store.required_report(comp.scorecard, f"the {comp.name} live scorecard")
        backtest = store.required_report(comp.live_backtest.report, f"the {comp.name} Elo backtest")
        log = store.log(comp.prediction_log)
        model = store.live_model(comp)
        sections.append(
            Section(
                key=comp.name,
                title=title,
                log=log,
                scorecard=scorecard,
                backtest=backtest,
                games=games,
                names=store.team_names(comp),
                model=model,
                season=LIVE_SEASON,
                replay_from=comp.live_backtest.warmup[0],
                forecasts=build_forecasts(
                    {tag: store.path(path) for tag, path in active_logs(comp, shown=True).items()},
                    FORECAST_MODELS,
                    games,
                    LIVE_SEASON,
                    comp.manual_pushes,
                    odds_log=_path_or_none(store, comp.odds_log),
                    published=SITE_FORECAST_MODEL,
                    baseline=model,
                ),
            )
        )
    return site_data(
        sections, now, data_volume(store.mart(), store.path(EUROLEAGUE.raw_dir / "playbyplay"))
    )


def upcoming_games(store: Store, competition: str, now: datetime) -> dict[str, Any]:
    """The live season's unplayed games that tip off after ``now``, each with its pre-registered
    Elo forecast when one is logged."""
    comp = store.competition(competition)
    games = store.games(comp)
    log = store.log(comp.prediction_log)
    first = displayed_rows(log).set_index("game_id")
    ahead = games[(games["season"] == LIVE_SEASON) & ~games["played"] & (games["tipoff_utc"] > now)]
    rows = []
    for g in ahead.to_dict("records"):
        logged = first.loc[g["game_id"]].to_dict() if g["game_id"] in first.index else None
        rows.append(
            {
                "game_id": g["game_id"],
                "round": int(g["round"]),
                "phase": g["phase"],
                "tipoff_utc": jsonable(g["tipoff_utc"]),
                "tipoff_time_confirmed": bool(g["confirmed_date"]),
                "home": store.team(comp, g["home"]),
                "away": store.team(comp, g["away"]),
                "prediction": None if logged is None else forecast_fields(logged),
            }
        )
    return {
        "competition": comp.name,
        "season": LIVE_SEASON,
        "as_of": stamp(now),
        "games": rows,
    }


def prediction(store: Store, game_id: str) -> dict[str, Any]:
    """Every logged forecast of one game, per model: the row the site shows
    (``logs.displayed_rows``: the pre-registered row, else the earliest late row, ``late``) and
    the game's other rows, oldest first."""
    for comp in (EUROLEAGUE,):
        logs = active_logs(comp, shown=True)
        models: dict[str, Any] = {}
        head: Mapping[Any, Any] | None = None
        for model, relative in logs.items():
            log = store.log(relative)
            rows = log[log["game_id"] == game_id]
            if rows.empty:
                continue
            picked = displayed_rows(rows)  # keeps the log's index
            (shown,) = picked.to_dict("records")
            others = rows.drop(index=picked.index)
            others = others.assign(late=is_late(others)).sort_values(
                "predicted_at_utc", key=lambda t: pd.to_datetime(t, utc=True), kind="stable"
            )
            head = head or shown
            models[model] = {
                "pre_registered": {**forecast_fields(shown), "late": bool(shown["late"])},
                "later": [
                    {**forecast_fields(r), "late": bool(r["late"])}
                    for r in others.to_dict("records")
                ],
            }
        if head is not None:
            return {
                "game_id": game_id,
                "competition": comp.name,
                "season": int(head["season"]),
                "round": int(head["round"]),
                "phase": head["phase"],
                "tipoff_utc": head["tipoff_utc"],
                "home": head["home"],
                "away": head["away"],
                "result": _result(store, comp, game_id),
                "models": models,
            }
    raise NotFound(f"no prediction is logged for game '{game_id}'")


def _result(store: Store, comp: Competition, game_id: str) -> dict[str, Any] | None:
    if not store.path(MART_PATH).exists():
        return None
    games = store.games(comp)
    played = games[(games["game_id"] == game_id) & games["played"]]
    if played.empty:
        return None
    g = played.iloc[0]
    return {
        "home_score": int(g["home_score"]),
        "away_score": int(g["away_score"]),
        "forfeit": bool(g["forfeit"]),
    }
