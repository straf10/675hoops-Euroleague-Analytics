"""The Store and what every read function loads through it: marts, logs, committed reports.

The domain modules ask the Store for what they need in domain terms (``store.games(comp)``,
``store.team(comp, code)``, ``store.log(relative)``, ``store.report(relative)``, ...). What it
loads it keeps for its lifetime; a domain module keeps a value it derives the same way by
decorating the function that derives it with ``cached``.
"""

import functools
import json
import math
from collections.abc import Callable, Hashable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar, cast, overload

import numpy as np
import pandas as pd
import pandera.pandas as pa

from eurohoops.config import (
    EUROLEAGUE,
    MART_PATH,
    Competition,
)
from eurohoops.eval.backtest import TunedModel, load_tuned_model
from eurohoops.logs import TIME_FORMAT, read_log
from eurohoops.marts import read_games, read_teams
from eurohoops.models.elo import prepare, season_ratings
from eurohoops.parse.schemas import validated
from eurohoops.publish import team_identity
from eurohoops.stats.box import BoxGames, build_box_games
from eurohoops.stats.export import (
    load_cached_games,
)

T = TypeVar("T")


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
    Marts, box scores and committed reports are loaded once per Store; logs on every call.
    """

    root: Path = Path()
    from_cache: bool = False
    _memo: dict[Hashable, Any] = field(default_factory=dict, init=False, repr=False, compare=False)
    _lock: Any = field(default_factory=RLock, init=False, repr=False, compare=False)

    def _once(self, key: Hashable, make: Callable[[], T]) -> T:
        with self._lock:
            if key not in self._memo:
                self._memo[key] = make()
            return cast(T, self._memo[key])

    def path(self, relative: Path) -> Path:
        """``relative`` (a repo-root-relative path from ``eurohoops.config``) under the root."""
        return self.root / relative

    def competition(self, name: str) -> Competition:
        """The competition a route names; any other name is ``NotFound``."""
        if name != EUROLEAGUE.name:
            raise NotFound(f"unknown competition '{name}'; expected '{EUROLEAGUE.name}'")
        return EUROLEAGUE

    def mart(self) -> Path:
        """The DuckDB marts file; ``NotFound`` when it is not built."""
        path = self.path(MART_PATH)
        if not path.exists():
            raise NotFound(f"the marts are not built: {MART_PATH.as_posix()} is missing")
        return path

    def games(self, comp: Competition) -> pd.DataFrame:
        """The competition's games mart (every season, played or not)."""
        return self._once(("games", comp.name), lambda: read_games(self.mart(), comp.name))

    def team_names(self, comp: Competition) -> dict[str, str]:
        """Source code -> full club name, from the teams mart."""
        return self._once(
            ("names", comp.name),
            lambda: dict(read_teams(self.mart(), comp.name).itertuples(index=False)),
        )

    def team(self, comp: Competition, code: str) -> dict[str, str]:
        """A team as the API returns it (``publish.team_identity``): ``code`` is the source code,
        ``display_code`` the site's."""
        return asdict(team_identity(comp.name, code, self.team_names(comp)))

    def log(self, relative: Path | None) -> pd.DataFrame:
        """A forecast log (``logs.read_log``), read on every call; no rows when it is missing."""
        return read_log(None if relative is None else self.path(relative))

    def report(self, relative: Path) -> dict[str, Any] | None:
        """A committed JSON report, read once per Store; None when it has not been written."""
        path = self.path(relative)
        if not path.exists():
            return None
        return self._once(("report", relative), lambda: _load(path))

    def required_report(self, relative: Path, what: str) -> dict[str, Any]:
        """``report``, or ``NotFound`` naming the file and ``what`` it holds."""
        report = self.report(relative)
        if report is None:
            raise NotFound(f"{relative.as_posix()} not found: {what} has not been written")
        return report

    def live_model(self, comp: Competition) -> TunedModel:
        """The live Elo's tuned parameters (the competition's live backtest report)."""
        report = comp.live_backtest.report
        if not self.path(report).exists():
            raise NotFound(
                f"{report.as_posix()} not found: the {comp.name} Elo has no tuned parameters"
            )
        return load_tuned_model(self.path(report))

    def elo(self, comp: Competition, season: int) -> dict[str, tuple[float, float]]:
        """Each ``season`` team's (rating, rating at the season's start) as ``publish`` shows
        them: the live Elo replayed from the backtest's first warm-up season through ``season``."""

        def make() -> dict[str, tuple[float, float]]:
            first = comp.live_backtest.warmup[0]
            if season < first:
                raise NotFound(
                    f"the {comp.name} Elo is replayed from {first}; no rating for {season}"
                )
            games = self.games(comp)
            window = games[games["season"].between(first, season)]
            return season_ratings(prepare(window), self.live_model(comp).params, season)

        return self._once(("elo", comp.name, season), make)

    def euroleague_games(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """EuroLeague games and teams: the cached schedules (``from_cache``) or the marts."""

        def make() -> tuple[pd.DataFrame, pd.DataFrame]:
            if self.from_cache:
                return load_cached_games(self.path(EUROLEAGUE.raw_dir))
            return self.games(EUROLEAGUE), read_teams(self.mart(), EUROLEAGUE.name)

        return self._once("euroleague_games", make)

    def euroleague_box(self) -> BoxGames:
        """The EuroLeague box scores (players and teams) of ``euroleague_games``."""
        return self._once(
            "euroleague_box",
            lambda: build_box_games(self.path(EUROLEAGUE.raw_dir), self.euroleague_games()[0]),
        )


@overload
def cached[F: Callable[..., Any]](make: F, /) -> F: ...


@overload
def cached[F: Callable[..., Any]](*, key: Callable[..., Hashable]) -> Callable[[F], F]: ...


def cached[F: Callable[..., Any]](
    make: F | None = None, /, *, key: Callable[..., Hashable] | None = None
) -> F | Callable[[F], F]:
    """Compute ``make(store, *args)`` once per Store and arguments (which must be hashable).

    ``key`` picks the arguments that matter (it gets them all but the store): ``key=lambda now:
    ()`` keeps the first call's value whatever ``now`` later calls pass."""

    def decorate(make: F) -> F:
        @functools.wraps(make)
        def once(store: Store, *args: Any, **kwargs: Any) -> Any:
            which = (args, tuple(sorted(kwargs.items()))) if key is None else key(*args, **kwargs)
            return store._once((make, which), lambda: make(store, *args, **kwargs))

        return cast(F, once)

    return decorate if make is None else decorate(make)


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


def stamp(moment: datetime) -> str:
    """A moment as the API writes times (UTC, ``logs.TIME_FORMAT``)."""
    return moment.astimezone(UTC).strftime(TIME_FORMAT)


def forecast_fields(row: Mapping[Any, Any]) -> dict[str, Any]:
    """A log row without the game's own columns."""
    skip = {"game_id", "season", "round", "phase", "tipoff_utc", "home", "away"}
    return {str(k): jsonable(v) for k, v in row.items() if k not in skip}


def check_rows(rows: list[Any], schema: pa.DataFrameSchema) -> None:
    """Validate a report's row list against ``schema`` (the rows themselves are served as is)."""
    validated(pd.DataFrame(rows, columns=list(schema.columns)), schema)


def _load(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return report
