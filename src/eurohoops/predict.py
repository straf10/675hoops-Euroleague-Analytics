"""Append-only, idempotent log of pre-tip-off predictions for the live season."""

import csv
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd

from eurohoops.eval.backtest import TunedModel
from eurohoops.inputs import (
    INPUT_COLUMNS,
    SOURCE_LOGGED,
    elo_strings,
    input_row,
)
from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.models.elo import prepare, replay_with_ratings

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

log = logging.getLogger(__name__)


class LatePredictionError(RuntimeError):
    """A prediction would be stamped at or after its game's tip-off."""


def logged_keys(log_path: Path) -> set[tuple[str, str]]:
    if not log_path.exists():
        return set()
    with log_path.open(newline="", encoding="utf-8") as fh:
        return {(row["game_id"], row["model_version"]) for row in csv.DictReader(fh)}


def upcoming_games(
    games: pd.DataFrame, season: int, now: datetime, round_lead: timedelta
) -> npt.NDArray[np.bool_]:
    """Confirmed, unplayed ``season`` games of every round whose first tip-off is within
    ``round_lead`` after ``now``, and that tip off after ``now``.

    A round is a ``(phase, round)`` pair of the season. Its first tip-off is the earliest
    confirmed tip-off among its games (played or not), so a round already in progress keeps
    selecting its remaining unplayed games, and a game with an unconfirmed time is never
    selected (nor does it set its round's start).
    """
    in_season = games["season"] == season
    confirmed = games["confirmed_date"].astype(bool)
    starts = games.loc[in_season & confirmed].groupby(["phase", "round"])["tipoff_utc"].min()
    keys = pd.MultiIndex.from_arrays([games["phase"], games["round"]])
    round_start = pd.Series(pd.to_datetime(starts.reindex(keys).to_numpy(), utc=True))
    open_round = (round_start <= pd.Timestamp(now + round_lead)).to_numpy()
    selected = in_season & ~games["played"] & confirmed & (games["tipoff_utc"] > now) & open_round
    return np.asarray(selected, dtype=np.bool_)


def refuse_late(predicted_at: datetime, targets: list[tuple[str, pd.Timestamp]]) -> None:
    """Raise LatePredictionError unless ``predicted_at`` is strictly before every tip-off."""
    late = [game_id for game_id, tipoff in targets if predicted_at >= tipoff]
    if late:
        raise LatePredictionError(f"predicted_at {predicted_at} is not before tip-off of {late}")


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
    (see ``upcoming_games``); return rows added.

    Ratings come from replaying Elo over every completed game from season ``replay_from`` on
    (the tuned model's first warm-up season, so extra history cannot shift live ratings).
    The selection time and the ``predicted_at_utc`` stamp are separate clock reads; if the stamp
    is not strictly before a game's tip-off, nothing is written and LatePredictionError is raised.

    With ``inputs_log``, each row appended to the Elo log also gets a model-input snapshot row
    there (same stamp, same p_home and exp_margin strings), unless that game and version are
    already in the inputs log.
    """
    now = clock()
    games = games[games["season"] >= replay_from]
    diffs, home_ratings, away_ratings = replay_with_ratings(prepare(games), model.params)
    upcoming = upcoming_games(games, season, now, round_lead)
    model_version = model.version()
    logged = logged_keys(log_path)
    targets = [
        (game, float(diff), float(home), float(away))
        for game, diff, home, away in zip(
            games[upcoming].to_dict("records"),
            diffs[upcoming],
            home_ratings[upcoming],
            away_ratings[upcoming],
            strict=True,
        )
        if (game["game_id"], model_version) not in logged
    ]
    predicted_at = clock()
    refuse_late(predicted_at, [(game["game_id"], game["tipoff_utc"]) for game, *_ in targets])
    stamp = predicted_at.strftime(TIME_FORMAT)
    elo_rows, snapshots = [], []
    for game, diff, home_rating, away_rating in targets:
        p_home, exp_margin = elo_strings(diff, model.margin_scale)
        tipoff = game["tipoff_utc"].strftime(TIME_FORMAT)
        elo_rows.append(
            {
                "game_id": game["game_id"],
                "season": game["season"],
                "round": game["round"],
                "phase": game["phase"],
                "tipoff_utc": tipoff,
                "home": game["home"],
                "away": game["away"],
                "p_home": p_home,
                "exp_margin": exp_margin,
                "model": "elo",
                "model_version": model_version,
                "predicted_at_utc": stamp,
            }
        )
        if inputs_log is not None:
            neutral = bool(game["neutral"])
            snapshots.append(
                input_row(
                    game=game,
                    tipoff_utc=tipoff,
                    home_rating=home_rating,
                    away_rating=away_rating,
                    hca=0.0 if neutral else model.params.hca,
                    neutral=neutral,
                    diff=diff,
                    margin_scale=model.margin_scale,
                    p_home=p_home,
                    exp_margin=exp_margin,
                    model_version=model_version,
                    predicted_at_utc=stamp,
                    source=SOURCE_LOGGED,
                )
            )
    append_rows(log_path, LOG_COLUMNS, elo_rows)
    if inputs_log is not None:
        known = logged_keys(inputs_log)
        fresh = [r for r in snapshots if (r["game_id"], r["model_version"]) not in known]
        append_rows(inputs_log, INPUT_COLUMNS, fresh)
    log.info(
        "%d upcoming games in open rounds, %d already logged, %d rows appended",
        int(upcoming.sum()),
        int(upcoming.sum()) - len(elo_rows),
        len(elo_rows),
    )
    return len(elo_rows)
