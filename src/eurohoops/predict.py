"""The pre-registered Elo log: Elo's forecast rows and their model-input snapshots, appended
through the shadow-log module's lifecycle (``shadow_log.append_log``)."""

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from eurohoops.eval.backtest import TunedModel
from eurohoops.inputs import (
    INPUT_COLUMNS,
    SOURCE_LOGGED,
    elo_strings,
    input_row,
)
from eurohoops.logs import append_rows
from eurohoops.models.elo import prepare, replay_with_ratings
from eurohoops.shadow_log import Row, append_log, logged_keys

LOG_COLUMNS = (
    "game_id",
    "season",
    "round",
    "phase",
    "tipoff_utc",
    "home",
    "away",
    "p_home",
    "exp_margin",
    "model",
    "model_version",
    "predicted_at_utc",
)


def predict_upcoming(
    games: pd.DataFrame,
    model: TunedModel,
    *,
    log_path: Path,
    season: int,
    replay_from: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
    inputs_log: Path | None = None,
) -> int:
    """Log confirmed, unplayed ``season`` games of the rounds starting within ``round_lead``
    (see ``shadow_log.upcoming_games``); return rows added.

    Ratings come from replaying Elo over every completed game from season ``replay_from`` on
    (the tuned model's first warm-up season, so extra history cannot shift live ratings).
    Selection, stamping and the late refusal are ``shadow_log.append_log``'s.

    With ``inputs_log``, each row appended to the Elo log also gets a model-input snapshot row
    there (same stamp, same p_home and exp_margin strings), unless that game and version are
    already in the inputs log.
    """
    games = games[games["season"] >= replay_from]
    version = model.version()
    # game_id -> (game, diff, home rating, away rating) of each forecast game, for its snapshot
    seen: dict[str, tuple[dict[Any, Any], float, float, float]] = {}

    def forecast(due: pd.DataFrame) -> dict[str, dict[str, str]]:
        diffs, home_ratings, away_ratings = replay_with_ratings(prepare(games), model.params)
        position = {str(g): i for i, g in enumerate(games["game_id"])}  # replay rows = game rows
        out = {}
        for game in due.to_dict("records"):
            game_id = str(game["game_id"])
            i = position[game_id]
            diff = float(diffs[i])
            p_home, exp_margin = elo_strings(diff, model.margin_scale)
            seen[game_id] = (game, diff, float(home_ratings[i]), float(away_ratings[i]))
            out[game_id] = {"p_home": p_home, "exp_margin": exp_margin}
        return out

    def snapshot(rows: list[Row]) -> None:
        if inputs_log is None:
            return
        known = logged_keys(inputs_log)
        fresh = []
        for row in rows:
            game, diff, home_rating, away_rating = seen[str(row["game_id"])]
            if (str(row["game_id"]), version) in known:
                continue
            neutral = bool(game["neutral"])
            fresh.append(
                input_row(
                    game=game,
                    tipoff_utc=str(row["tipoff_utc"]),
                    home_rating=home_rating,
                    away_rating=away_rating,
                    hca=0.0 if neutral else model.params.hca,
                    neutral=neutral,
                    diff=diff,
                    margin_scale=model.margin_scale,
                    p_home=str(row["p_home"]),
                    exp_margin=str(row["exp_margin"]),
                    model_version=version,
                    predicted_at_utc=str(row["predicted_at_utc"]),
                    source=SOURCE_LOGGED,
                )
            )
        append_rows(inputs_log, INPUT_COLUMNS, fresh)

    return append_log(
        games,
        forecast,
        tag="elo",
        label="Elo",
        version=version,
        columns=LOG_COLUMNS,
        log_path=log_path,
        season=season,
        round_lead=round_lead,
        clock=clock,
        after_append=snapshot,
    )
