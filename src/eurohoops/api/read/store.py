"""The Store and what every read function loads through it: marts, logs, committed reports."""

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar, cast

import numpy as np
import pandas as pd
import pandera.pandas as pa

from eurohoops.config import (
    EUROLEAGUE,
    MART_PATH,
    Competition,
)
from eurohoops.eval.backtest import TunedModel, load_tuned_model
from eurohoops.logs import TIME_FORMAT
from eurohoops.marts import read_games, read_teams
from eurohoops.models.elo import prepare, season_ratings
from eurohoops.parse.schemas import validated
from eurohoops.publish import DISPLAY_CODES, short_name
from eurohoops.stats.box import BoxGames, build_box_games
from eurohoops.stats.export import (
    load_cached_games,
)

T = TypeVar("T")


PREDICTION_LOG_SCHEMA = pa.DataFrameSchema(
    {
        "game_id": pa.Column(str),
        "season": pa.Column("int64"),
        "round": pa.Column("int64"),
        "phase": pa.Column(str),
        "tipoff_utc": pa.Column(str),
        "home": pa.Column(str),
        "away": pa.Column(str),
        "p_home": pa.Column("float64", pa.Check.in_range(0.0, 1.0)),
        "exp_margin": pa.Column("float64"),
        "model": pa.Column(str),
        "model_version": pa.Column(str),
        "predicted_at_utc": pa.Column(str),
    },
    strict=False,  # M1 and M5 rows carry extra forecast columns
)


class NotFound(LookupError):
    """A route's 404: ``reason`` is the body's ``detail``; ``extra`` is merged into the body."""

    def __init__(self, reason: str, **extra: Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.extra = extra


@dataclass(frozen=True)
class Store:
    """Where the data lives, and what has been loaded from it.

    ``root`` holds the repository layout (``data/``, ``reports/``, ``predictions/``); tests point
    it at a temporary tree. With ``from_cache`` the ``/stats`` routes read games from the cached
    schedules and never open DuckDB (the daily workflow's mode); other routes still read the marts.
    """

    root: Path = Path()
    from_cache: bool = False
    _memo: dict[str, Any] = field(default_factory=dict, init=False, repr=False, compare=False)
    _lock: Any = field(default_factory=RLock, init=False, repr=False, compare=False)

    def path(self, relative: Path) -> Path:
        return self.root / relative

    def memo(self, key: str, make: Callable[[], T]) -> T:
        with self._lock:
            if key not in self._memo:
                self._memo[key] = make()
            return cast(T, self._memo[key])


def jsonable(value: Any) -> Any:
    """Plain Python for ``json.dumps``: numpy and pandas scalars unwrapped, NaN and NaT -> None."""
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | np.ndarray):
        return [jsonable(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.tz_convert("UTC").strftime(TIME_FORMAT)
    if isinstance(value, float | np.floating):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.generic):
        return value.item()
    return None if value is pd.NaT else value


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(TIME_FORMAT)


def _competition(name: str) -> Competition:
    if name != EUROLEAGUE.name:
        raise NotFound(f"unknown competition '{name}'; expected '{EUROLEAGUE.name}'")
    return EUROLEAGUE


def _mart(store: Store) -> Path:
    path = store.path(MART_PATH)
    if not path.exists():
        raise NotFound(f"the marts are not built: {MART_PATH.as_posix()} is missing")
    return path


def _report(store: Store, relative: Path) -> dict[str, Any] | None:
    path = store.path(relative)
    if not path.exists():
        return None
    return store.memo(f"report:{relative}", lambda: _load(path))  # read once per Store


def _load(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return report


def _required(store: Store, relative: Path, what: str) -> dict[str, Any]:
    report = _report(store, relative)
    if report is None:
        raise NotFound(f"{relative.as_posix()} not found: {what} has not been written")
    return report


def _check(rows: list[Any], schema: pa.DataFrameSchema) -> None:
    """Validate a report's row list against ``schema`` (the rows themselves are served as is)."""
    validated(pd.DataFrame(rows, columns=list(schema.columns)), schema)


def _games(store: Store, comp: Competition) -> pd.DataFrame:
    return store.memo(f"games:{comp.name}", lambda: read_games(_mart(store), comp.name))


def _names(store: Store, comp: Competition) -> dict[str, str]:
    return store.memo(
        f"names:{comp.name}",
        lambda: dict(read_teams(_mart(store), comp.name).itertuples(index=False)),
    )


def _team(comp: Competition, code: str, names: Mapping[str, str]) -> dict[str, str]:
    shown = DISPLAY_CODES.get(comp.name, {}).get(code, code)
    name = names.get(code, code)
    return {
        "code": code,
        "display_code": shown,
        "name": name,
        "short": short_name(comp.name, code, name),
    }


def _read_log(store: Store, relative: Path | None) -> pd.DataFrame:
    """A prediction log (Elo, M1 or M5); empty when the file is missing or has no rows."""
    path = None if relative is None else store.path(relative)
    if path is None or not path.exists() or not path.stat().st_size:
        return validated(
            pd.DataFrame(columns=list(PREDICTION_LOG_SCHEMA.columns)), PREDICTION_LOG_SCHEMA
        )
    return validated(pd.read_csv(path, dtype={"game_id": str}), PREDICTION_LOG_SCHEMA)


def _ordered(log: pd.DataFrame) -> pd.DataFrame:
    """Rows with ``late`` (stamped at or after tip-off), latest stamp first. A game's counted row
    is its first on-time row (the latest before tip-off), else its first row (the scorecard's
    rule, ``eval.scorecard.latest_per_model_game``)."""
    late = pd.to_datetime(log["predicted_at_utc"], utc=True) >= pd.to_datetime(
        log["tipoff_utc"], utc=True
    )
    stamped = pd.to_datetime(log["predicted_at_utc"], utc=True)
    ordered = log.assign(late=late, _stamped=stamped).sort_values(
        ["late", "_stamped"], ascending=[True, False], kind="stable"
    )
    return ordered.drop(columns="_stamped")


def _forecast(row: Mapping[Any, Any]) -> dict[str, Any]:
    """A log row without the game's own columns."""
    skip = {"game_id", "season", "round", "phase", "tipoff_utc", "home", "away"}
    return {str(k): jsonable(v) for k, v in row.items() if k not in skip}


def _live_model(store: Store, comp: Competition) -> TunedModel:
    report = comp.live_backtest.report
    if not store.path(report).exists():
        raise NotFound(
            f"{report.as_posix()} not found: the {comp.name} Elo has no tuned parameters"
        )
    return load_tuned_model(store.path(report))


def _elo(store: Store, comp: Competition, season: int) -> dict[str, tuple[float, float]]:
    """Each ``season`` team's (rating, rating at the season's start) as ``publish`` shows them:
    the live Elo replayed from the backtest's first warm-up season through ``season``."""

    def make() -> dict[str, tuple[float, float]]:
        first = comp.live_backtest.warmup[0]
        if season < first:
            raise NotFound(f"the {comp.name} Elo is replayed from {first}; no rating for {season}")
        games = _games(store, comp)
        window = games[games["season"].between(first, season)]
        return season_ratings(prepare(window), _live_model(store, comp).params, season)

    return store.memo(f"elo:{comp.name}:{season}", make)


def _el_games(store: Store) -> tuple[pd.DataFrame, pd.DataFrame]:
    """EuroLeague games and teams: the cached schedules (``from_cache``) or the marts."""

    def make() -> tuple[pd.DataFrame, pd.DataFrame]:
        if store.from_cache:
            return load_cached_games(store.path(EUROLEAGUE.raw_dir))
        return _games(store, EUROLEAGUE), read_teams(_mart(store), EUROLEAGUE.name)

    return store.memo("el_games", make)


def _el_box(store: Store) -> BoxGames:
    return store.memo(
        "el_box",
        lambda: build_box_games(store.path(EUROLEAGUE.raw_dir), _el_games(store)[0]),
    )
