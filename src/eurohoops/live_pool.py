"""Live POOL (EuroLeague only): an append-only, pre-tip-off shadow log of the equal-weight
logarithmic pool of the four live forecasts (docs/models/pool.md). POOL3 (docs/models/pool3.md)
is the same pool over ELOR, M1 and M5, written by ``predict_pool3``.

The pool reads only its component logs, at their pinned ``model_version`` (config
``POOL_COMPONENTS``). A game gets a pool row only when every component logged it, the rows
agree on the fixtures, the game has not tipped off by the time the row is written, and the
latest component stamp is strictly before tip-off. The pool row is stamped with that latest
component stamp, so it never postdates a component. Nothing is written while the model's
``*_LIVE_ENABLED`` flag in config is False.
"""

import csv
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eurohoops import config
from eurohoops.eval.common import tagged_version
from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.models.pool import COMPONENTS, pool_margin, pool_probabilities
from eurohoops.predict import LOG_COLUMNS, logged_keys

POOL_LOG_COLUMNS = LOG_COLUMNS  # the Elo log's shape: the pool has no totals

log = logging.getLogger(__name__)

Rows = dict[str, dict[str, str]]  # game_id -> the component's logged row


def _utc_now() -> datetime:
    return datetime.now(UTC)


def pool_version(members: tuple[str, ...] = COMPONENTS, model: str = "pool") -> str:
    """The pool's ``model_version``: the package version and a hash of the pinned components."""
    key = ";".join(f"{name}={config.POOL_COMPONENTS[name][1]}" for name in members)
    return tagged_version(model, key)


def read_component(path: Path, version: str) -> tuple[Rows, list[dict[str, str]]]:
    """The rows of one component log logged at ``version``, keyed by game, and the rows logged at
    any other version. An absent log is empty.

    A game logged twice at the pinned version is an error: the logs are append-only, so a second
    row means something was written by hand.
    """
    if not path.exists():
        return {}, []
    rows: Rows = {}
    others: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["model_version"] != version:
                others.append(row)
                continue
            game_id = row["game_id"]
            if game_id in rows:
                raise ValueError(f"{path}: game {game_id} logged twice at {version}")
            rows[game_id] = row
    return rows, others


def _stamp(text: str) -> datetime:
    return datetime.strptime(text, TIME_FORMAT).replace(tzinfo=UTC)


def pool_rows(
    components: Mapping[str, Rows],
    logged: set[tuple[str, str]],
    version: str,
    now: datetime,
    *,
    members: tuple[str, ...] = COMPONENTS,
    model: str = "pool",
) -> tuple[list[dict[str, Any]], int, int]:
    """Pool rows for every game all ``members`` logged, not yet logged at ``version``.

    The first member's log gives the games and their fixtures.

    ``now`` is the time the rows are written. A game whose tip-off is not after ``now`` is never
    pooled; those games are counted separately from the games skipped for a fixture disagreement
    or a component stamp at or after tip-off. Returns the rows, the skipped count and the count
    of games already tipped off. The probabilities are computed from the 4-decimal values in the
    logs, so a row can be reproduced from the logs alone.
    """
    base_rows = components[members[0]]
    rows: list[dict[str, Any]] = []
    skipped = 0
    past = 0
    for game_id, base in base_rows.items():
        if (game_id, version) in logged:
            continue
        if _stamp(base["tipoff_utc"]) <= now:
            past += 1
            continue
        if any(game_id not in components[name] for name in members):
            continue
        parts = [components[name][game_id] for name in members]
        fixture = (base["home"], base["away"], base["tipoff_utc"])
        if any((p["home"], p["away"], p["tipoff_utc"]) != fixture for p in parts):
            log.error("POOL: component rows disagree on the fixture of %s: not pooled", game_id)
            skipped += 1
            continue
        stamp = max(_stamp(p["predicted_at_utc"]) for p in parts)
        if not stamp < _stamp(base["tipoff_utc"]):
            skipped += 1
            continue
        p_home = pool_probabilities([[float(p["p_home"]) for p in parts]])[0]
        margin = pool_margin([[float(p["exp_margin"]) for p in parts]])[0]
        rows.append(
            {
                "game_id": game_id,
                "season": base["season"],
                "round": base["round"],
                "phase": base["phase"],
                "tipoff_utc": base["tipoff_utc"],
                "home": base["home"],
                "away": base["away"],
                "p_home": f"{float(p_home):.4f}",
                "exp_margin": f"{float(margin):.2f}",
                "model": model,
                "model_version": version,
                "predicted_at_utc": stamp.strftime(TIME_FORMAT),
            }
        )
    return rows, skipped, past


def predict_pool(
    *,
    log_path: Path,
    components: Mapping[str, tuple[Path, str]] | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> int:
    """Append the POOL rows that are due; return how many were written.

    Off unless ``config.POOL_LIVE_ENABLED`` is True (read at call time). Reads only the four
    component logs, so it never blocks or alters them. ``clock`` gives the write time.
    """
    if not config.POOL_LIVE_ENABLED:
        return 0
    return _append(
        log_path=log_path,
        members=COMPONENTS,
        model="pool",
        pins=config.POOL_COMPONENTS if components is None else components,
        clock=clock,
    )


def predict_pool3(
    *,
    log_path: Path,
    components: Mapping[str, tuple[Path, str]] | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> int:
    """Append the POOL3 rows that are due (the pool of ELOR, M1 and M5); return how many.

    Off unless ``config.POOL3_LIVE_ENABLED`` is True (read at call time). The same code path as
    ``predict_pool``, over ``config.POOL3_MEMBERS``.
    """
    if not config.POOL3_LIVE_ENABLED:
        return 0
    return _append(
        log_path=log_path,
        members=config.POOL3_MEMBERS,
        model="pool3",
        pins=config.POOL_COMPONENTS if components is None else components,
        clock=clock,
    )


def _append(
    *,
    log_path: Path,
    members: tuple[str, ...],
    model: str,
    pins: Mapping[str, tuple[Path, str]],
    clock: Callable[[], datetime],
) -> int:
    now = clock()
    version = pool_version(members, model)
    loaded: dict[str, Rows] = {}
    for name in members:
        path, pinned = pins[name]
        component_rows, others = read_component(path, pinned)
        loaded[name] = component_rows
        upcoming = sorted({r["model_version"] for r in others if _stamp(r["tipoff_utc"]) > now})
        if upcoming:
            log.warning(
                "POOL: %s logged upcoming games at %s, not the pinned %s: those games are not "
                "pooled (a new POOL version must be declared)",
                name,
                ", ".join(upcoming),
                pinned,
            )
    rows, skipped, past = pool_rows(
        loaded, logged_keys(log_path), version, now, members=members, model=model
    )
    if past:
        log.info("POOL: %d games already tipped off at %s: not logged", past, now)
    if skipped:
        log.warning("POOL: %d games skipped (fixtures disagree or logged after tip-off)", skipped)
    if not rows:
        return 0
    append_rows(log_path, POOL_LOG_COLUMNS, rows)
    log.info("POOL: %d rows appended to %s", len(rows), log_path)
    return len(rows)
