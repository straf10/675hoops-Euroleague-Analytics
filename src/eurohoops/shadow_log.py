"""The prediction logs' one lifecycle: the Elo log and every shadow model that logs next to it.

``append_log`` picks the confirmed, unplayed games of the open rounds (``upcoming_games``) that
this model version has not logged yet (``logged_keys``), asks the model for its forecast of just
those games, stamps the rows, refuses them if the stamp or the clock right before writing is at or
after any tip-off (``LatePredictionError``, nothing written) and appends. ``append_shadow_log`` is
the same for a shadow model that can be gated off. ``run_shadows`` runs the shadows in order,
isolating failures so one model never blocks the next (which models are on: ``model_catalog``).
A model supplies only its forecast; what rows look like, which games are due and when a row is
late live here (rule 1: logs are append-only).
"""

import csv
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd

from eurohoops.logs import TIME_FORMAT, append_rows

log = logging.getLogger(__name__)

# What a model returns for the games it forecasts: ``game_id`` -> the model's own columns, as the
# strings the log holds. A game it leaves out has no forecast and is skipped with a warning.
# ``None`` means the model has nothing to log this run and has said why.
Forecast = Callable[[pd.DataFrame], Mapping[str, Mapping[str, str]] | None]
# A row as written to a log: column -> value.
Row = dict[str, object]


class LatePredictionError(RuntimeError):
    """A prediction would be stamped, or written, at or after its game's tip-off."""


def logged_keys(log_path: Path) -> set[tuple[str, str]]:
    """The ``(game_id, model_version)`` pairs already in the log at ``log_path``."""
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


def append_log(
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
    as_of: datetime | None = None,
    after_append: Callable[[list[Row]], None] | None = None,
) -> int:
    """Append this model's rows for the due games to ``log_path``; return the rows added.

    ``tag`` is the ``model`` column and ``label`` the name in log messages. Due games are the
    ``upcoming_games`` of ``season`` not yet logged at ``version``; ``forecast`` is called with
    them only when there are any. ``clock`` is the real clock, read twice: once to select and once
    right before writing. Rows are stamped with that second read, or with ``as_of`` for a model
    that forecasts as of an earlier instant (M5-INJ's injury cutoff). The write is refused if the
    stamp or the write-time read is at or after a tip-off, so a slow forecast that runs past a
    tip-off is never written, whatever its stamp. ``after_append`` gets the rows just appended
    (the Elo log's inputs snapshot).
    """
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
    written_at = clock()
    predicted_at = written_at if as_of is None else as_of
    tipoffs = [(r["game_id"], r["tipoff_utc"]) for r in targets]
    refuse_late(predicted_at, tipoffs)
    refuse_late(written_at, tipoffs)
    rows: list[Row] = [
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
    if after_append is not None:
        after_append(rows)
    return len(rows)


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
    as_of: datetime | None = None,
    skip_reason: str | None = None,
) -> int | None:
    """``append_log`` for a shadow model. ``skip_reason`` (a model that is gated off) logs it and
    returns None, so ``run_shadows`` reports the model inactive; nothing is built or written."""
    if skip_reason is not None:
        log.info(skip_reason)
        return None
    return append_log(
        games,
        forecast,
        tag=tag,
        label=label,
        version=version,
        columns=columns,
        log_path=log_path,
        season=season,
        round_lead=round_lead,
        clock=clock,
        as_of=as_of,
    )


@dataclass(frozen=True)
class Shadow:
    """One model's turn in a ``predict`` run. ``run`` returns the rows it added, or None when the
    model is not active here or is gated off (it has said why). A ``required`` model's failure
    fails the run."""

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
