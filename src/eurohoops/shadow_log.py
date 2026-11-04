"""The shadow log: one lifecycle for every model that logs next to the Elo log.

``append_shadow_log`` picks the confirmed, unplayed games of the open rounds that this model
version has not logged yet, asks the model for its forecast of just those games, stamps the
rows, refuses a stamp at or after any tip-off (``LatePredictionError``, nothing written) and
appends. A model supplies only its forecast; what rows look like, which games are due and when a
stamp is late live here (rule 1: logs are append-only).
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.predict import logged_keys, refuse_late, upcoming_games

log = logging.getLogger(__name__)

# What a model returns for the games it forecasts: ``game_id`` -> the model's own columns, as the
# strings the log holds. A game it leaves out has no forecast and is skipped with a warning.
# ``None`` means the model has nothing to log this run and has said why.
Forecast = Callable[[pd.DataFrame], Mapping[str, Mapping[str, str]] | None]


def append_shadow_log(
    games: pd.DataFrame,
    forecast: Forecast,
    *,
    tag: str,
    label: str,
    version: str,
    columns: Sequence[str],
    log_path: Path,
    season: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
    skip_reason: str | None = None,
) -> int:
    """Append this model's rows for the due games to ``log_path``; return the rows added.

    ``tag`` is the ``model`` column and ``label`` the name in log messages. Due games are the
    ``upcoming_games`` of ``season`` not yet logged at ``version``; ``forecast`` is called with
    them only when there are any. ``skip_reason`` (a model that is gated off) logs it and returns
    0. The clock is read twice, once to select and once to stamp, so a slow forecast that runs
    past a tip-off is refused.
    """
    if skip_reason is not None:
        log.info(skip_reason)
        return 0
    upcoming = upcoming_games(games, season, clock(), round_lead)
    logged = logged_keys(log_path)
    fresh = np.array([(str(g), version) not in logged for g in games["game_id"]], dtype=bool)
    due = games[upcoming & fresh]
    if due.empty:
        return 0
    forecasts = forecast(due)
    if forecasts is None:
        return 0
    targets = [r for r in due.to_dict("records") if str(r["game_id"]) in forecasts]
    if len(targets) < len(due):
        log.warning("%s: %d upcoming games have no forecast", label, len(due) - len(targets))
    predicted_at = clock()
    refuse_late(predicted_at, [(r["game_id"], r["tipoff_utc"]) for r in targets])
    rows = [
        {
            "game_id": r["game_id"],
            "season": r["season"],
            "round": r["round"],
            "phase": r["phase"],
            "tipoff_utc": r["tipoff_utc"].strftime(TIME_FORMAT),
            "home": r["home"],
            "away": r["away"],
            **forecasts[str(r["game_id"])],
            "model": tag,
            "model_version": version,
            "predicted_at_utc": predicted_at.strftime(TIME_FORMAT),
        }
        for r in targets
    ]
    append_rows(log_path, columns, rows)
    log.info("%s: %d rows appended to %s", label, len(rows), log_path)
    return len(rows)
