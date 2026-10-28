"""The live season's schedule is refetched daily, so a bad response must never replace the good
cached schedule: after rollover that cache is what the season is read from, for good."""

import json
from pathlib import Path

import httpx
import pytest

from eurohoops.ingest.cache import read_cached
from eurohoops.ingest.euroleague import MIN_INTERVAL_S, ScheduleRejectedError, ingest_seasons
from eurohoops.ingest.http import Fetcher
from eurohoops.parse.games import build_games_table
from tests.conftest import FIXTURES

LIVE = 2026
GOOD = (FIXTURES / "schedule_E2026.json").read_bytes()


class ScheduleReply:
    """Serves ``reply`` (HTTP 200) for every request."""

    def __init__(self, reply: bytes) -> None:
        self.reply = reply

    def __call__(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=self.reply)


def fetcher_for(api: ScheduleReply) -> Fetcher:
    return Fetcher(httpx.Client(transport=httpx.MockTransport(api)), MIN_INTERVAL_S)


@pytest.fixture
def cached_good(tmp_path: Path) -> Path:
    ingest_seasons(fetcher_for(ScheduleReply(GOOD)), tmp_path, [LIVE], False, LIVE)
    return tmp_path / "schedule" / f"E{LIVE}.json.gz"


@pytest.mark.usefixtures("no_sleep")
def test_empty_200_schedule_is_rejected_and_the_good_cache_kept(
    tmp_path: Path, cached_good: Path
) -> None:
    before = read_cached(cached_good)
    with pytest.raises(ScheduleRejectedError, match="has no games"):
        ingest_seasons(fetcher_for(ScheduleReply(b'{"data": []}')), tmp_path, [LIVE], False, LIVE)
    assert read_cached(cached_good) == before


@pytest.mark.usefixtures("no_sleep")
def test_malformed_schedule_is_rejected_and_the_good_cache_kept(
    tmp_path: Path, cached_good: Path
) -> None:
    before = read_cached(cached_good)
    with pytest.raises(ScheduleRejectedError, match="not a schedule"):
        ingest_seasons(fetcher_for(ScheduleReply(b"{not json")), tmp_path, [LIVE], False, LIVE)
    assert read_cached(cached_good) == before


@pytest.mark.usefixtures("no_sleep")
def test_normal_schedule_is_cached_byte_for_byte(tmp_path: Path) -> None:
    schedules = ingest_seasons(fetcher_for(ScheduleReply(GOOD)), tmp_path, [LIVE], False, LIVE)
    assert len(schedules[LIVE]) == len(json.loads(GOOD)["data"])
    assert read_cached(tmp_path / "schedule" / f"E{LIVE}.json.gz") == GOOD


def test_an_empty_games_table_is_what_an_empty_season_would_build() -> None:
    # Downstream of the fetch: an empty season builds an empty games table without an error,
    # which is why the guard has to sit at the fetch.
    assert len(build_games_table({LIVE: []})) == 0
