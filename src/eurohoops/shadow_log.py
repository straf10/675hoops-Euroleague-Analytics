"""The shadow log: one lifecycle for every model that logs next to the Elo log.

``is_active`` answers whether a model's log is on; ``run_shadows`` runs the active ones in
order, isolating failures so one model never blocks the next. ``append_shadow_log`` picks the
confirmed, unplayed games of the open rounds that this model version has not logged yet, asks the
model for its forecast of just those games, stamps the rows, refuses a stamp at or after any
tip-off (``LatePredictionError``, nothing written) and
appends. A model supplies only its forecast; what rows look like, which games are due and when a
stamp is late live here (rule 1: logs are append-only).
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from eurohoops import config
from eurohoops.config import Competition
from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.predict import LatePredictionError, logged_keys, refuse_late, upcoming_games

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


# The owner's switch (``config.py``) of each model that has one. M1 and M5 have none: they log
# whenever their gate-passing report exists.
_FLAGS = {"m5inj": "M5INJ_LIVE_ENABLED", "eloc": "ELOC_LIVE_ENABLED", "eloh": "ELOH_LIVE_ENABLED"}


def is_active(tag: str, comp: Competition) -> bool:
    """Whether model ``tag`` (``m1``, ``m5``, ``m5inj``, ``eloc``, ``eloh``) logs for ``comp``: it
    has a log path there and its ``config.py`` flag, if it has one, is on. The one place that
    answers it, for the CLI, the read model and the export check alike."""
    flag = _FLAGS.get(tag)
    on = True if flag is None else bool(getattr(config, flag))
    return on and getattr(comp, f"{tag}_prediction_log") is not None


@dataclass(frozen=True)
class Shadow:
    """One model's turn in a ``predict`` run. ``run`` returns the rows it added, or None when the
    model is not active here (it has said why). A ``required`` model's failure fails the run."""

    label: str
    log_path: Path | None
    run: Callable[[], int | None]
    required: bool = False


@dataclass(frozen=True)
class Outcome:
    label: str
    status: Literal["logged", "inactive", "failed"]
    rows: int
    required: bool

    @property
    def blocking(self) -> bool:
        """A required model failed: the run must end non-zero."""
        return self.status == "failed" and self.required


def run_shadows(shadows: Sequence[Shadow], echo: Callable[[str], None]) -> list[Outcome]:
    """Run ``shadows`` in order. A failure is logged with its traceback and the next model still
    runs, except ``LatePredictionError``, which always propagates (a late stamp must never be
    swallowed). The outcomes tell the caller which required model failed."""
    outcomes = []
    for shadow in shadows:
        try:
            added = shadow.run()
        except LatePredictionError:
            raise
        except Exception:
            if shadow.required:
                log.exception(
                    "%s failed: nothing appended to its log; the other logs go on", shadow.label
                )
            else:
                log.exception(
                    "%s skipped: its forecast failed; nothing appended to its log", shadow.label
                )
            outcomes.append(Outcome(shadow.label, "failed", 0, shadow.required))
            continue
        if added is None:
            outcomes.append(Outcome(shadow.label, "inactive", 0, shadow.required))
            continue
        echo(f"{added} {shadow.label} predictions appended to {shadow.log_path}")
        outcomes.append(Outcome(shadow.label, "logged", added, shadow.required))
    return outcomes
