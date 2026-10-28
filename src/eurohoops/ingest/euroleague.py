"""EuroLeague ingestion into an immutable, gzip-compressed raw cache.

Cache layout (``root`` = data/raw/euroleague):
  schedule/E{season}.json.gz                  final for past seasons; the live one is refreshed
  {endpoint}/E{season}/{game_code}.json.gz    completed games only; written once, never refetched
"Already have it" is a file-existence check; there is no index file.
"""

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eurohoops.config import SCHEDULE_MAX_DROP_GAMES, SCHEDULE_MAX_DROP_SHARE
from eurohoops.ingest.cache import read_cached, write_atomic
from eurohoops.ingest.http import Fetcher

SCHEDULE_URL = "https://api-live.euroleague.net/v2/competitions/E/seasons/E{season}/games"
DETAIL_URL = "https://live.euroleague.net/api/{endpoint}?gamecode={game_code}&seasoncode=E{season}"
DETAIL_ENDPOINTS = ("Boxscore", "PlaybyPlay", "Points")
MIN_INTERVAL_S = 1.0

log = logging.getLogger(__name__)

RawGame = dict[str, Any]


class ScheduleRejectedError(RuntimeError):
    """A live-schedule response that must not replace the cached one: not a schedule, no games,
    or a drop beyond the thresholds. ``new_games`` is what the response held (0 if unreadable)."""

    def __init__(self, message: str, new_games: int = 0) -> None:
        super().__init__(message)
        self.new_games = new_games


class PastSeasonNotCachedError(RuntimeError):
    """A finished season's schedule is not in the raw cache. Past seasons are read from the cache
    only, so the cache must be restored (the seed workflow) instead of refetched."""


@dataclass
class CacheStats:
    schedule_hits: int = 0
    schedule_fetches: int = 0
    detail_hits: int = 0
    detail_fetches: int = 0
    detail_empty: int = 0

    def summary(self) -> str:
        return (
            f"schedules: {self.schedule_hits} cached, {self.schedule_fetches} fetched; "
            f"details: {self.detail_hits} cached, {self.detail_fetches} fetched, "
            f"{self.detail_empty} empty (not cached)"
        )


def _game_code(value: object) -> int:
    """The API's gameCode as a positive int, so it cannot steer a cache path or the URL."""
    if isinstance(value, bool) or not isinstance(value, int | str) or not str(value).isdigit():
        raise ValueError(f"unexpected EuroLeague gameCode {value!r}")
    return int(value)


def _schedule_games(payload: bytes) -> list[RawGame]:
    games: list[RawGame] = json.loads(payload)["data"]
    return games


def _checked_schedule(payload: bytes) -> list[RawGame]:
    """The games of a live-season response; ``ScheduleRejectedError`` if it is not a schedule."""
    try:
        games = _schedule_games(payload)
    except (ValueError, KeyError, TypeError) as exc:
        raise ScheduleRejectedError(f"response is not a schedule ({type(exc).__name__})") from exc
    if not isinstance(games, list) or not games:
        raise ScheduleRejectedError("response has no games")
    return games


def _refuse_shrink(games: list[RawGame], cached: list[RawGame] | None) -> None:
    """A response that drops too many games from the cached schedule is refused: it is far more
    likely a truncated or partial API answer than a real change of the schedule."""
    if cached is None:
        return
    drop = len(cached) - len(games)
    if drop > SCHEDULE_MAX_DROP_GAMES or drop > SCHEDULE_MAX_DROP_SHARE * len(cached):
        raise ScheduleRejectedError(
            f"drops {drop} games ({drop / len(cached):.1%}) from the cached schedule",
            new_games=len(games),
        )


def _annotate(title: str, message: str) -> None:
    """A GitHub Actions warning: it shows in the run summary; in a local shell it is plain text."""
    sys.stdout.write(f"::warning title={title}::{message}\n")
    sys.stdout.flush()


def _cached_games(path: Path) -> list[RawGame] | None:
    return _schedule_games(read_cached(path)) if path.exists() else None


def _load_schedule(
    fetcher: Fetcher, root: Path, season: int, live_season: int, stats: CacheStats
) -> list[RawGame]:
    """Past seasons are final even with unplayed games (2019-20 cancelled, 2021-22 voided).

    Only the live season goes to the network: a finished season missing from the cache is an
    error, never a fetch.
    """
    path = root / "schedule" / f"E{season}.json.gz"
    if season < live_season:
        if not path.exists():
            raise PastSeasonNotCachedError(
                f"EuroLeague {season} schedule is not in the raw cache ({path}): restore the cache"
            )
        stats.schedule_hits += 1
        return _schedule_games(read_cached(path))
    cached = _cached_games(path)
    payload = fetcher.get(SCHEDULE_URL.format(season=season))
    try:
        games = _checked_schedule(payload)
        _refuse_shrink(games, cached)
    except ScheduleRejectedError as exc:
        # The cache stays as it is: the run goes on with the cached schedule.
        kept = cached or []
        log.warning(
            "EuroLeague %d schedule rejected: %s; cached %d games kept", season, exc, len(kept)
        )
        if cached is None:
            log.warning(
                "EuroLeague %d has no cached schedule: this run has no games for it", season
            )
        _annotate(
            "Schedule rejected", f"{season} {exc}: cached {len(kept)} games, new {exc.new_games}"
        )
        return kept
    stats.schedule_fetches += 1
    write_atomic(path, payload)
    return games


def _fetch_details(
    fetcher: Fetcher, root: Path, season: int, games: list[RawGame], stats: CacheStats
) -> None:
    for game in games:
        if not game["played"]:
            continue
        game_code = _game_code(game["gameCode"])
        for endpoint in DETAIL_ENDPOINTS:
            path = root / endpoint.lower() / f"E{season}" / f"{game_code}.json.gz"
            if path.exists():
                stats.detail_hits += 1
                continue
            url = DETAIL_URL.format(endpoint=endpoint, game_code=game_code, season=season)
            payload = fetcher.get(url)
            stats.detail_fetches += 1
            if payload.strip():
                write_atomic(path, payload)
            else:
                stats.detail_empty += 1
                log.warning("empty %s body for E%d game %s", endpoint, season, game_code)


def ingest_seasons(
    fetcher: Fetcher, root: Path, seasons: list[int], details: bool, live_season: int
) -> dict[int, list[RawGame]]:
    """Return raw schedules per season; with ``details``, also cache detail JSON of played games."""
    stats = CacheStats()
    schedules = {
        season: _load_schedule(fetcher, root, season, live_season, stats) for season in seasons
    }
    if details:
        for season, games in schedules.items():
            _fetch_details(fetcher, root, season, games, stats)
    log.info(stats.summary())
    return schedules
