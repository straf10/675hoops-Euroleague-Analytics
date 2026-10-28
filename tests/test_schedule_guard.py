"""The live season's schedule is refetched daily. A response that is empty, malformed, or drops too
many games must not replace the cached schedule: after rollover that cache is what the season is
read from, for good. The run goes on with the cached schedule and says so in a warning."""

import copy
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from eurohoops.cli import app as cli_app
from eurohoops.ingest.cache import read_cached
from eurohoops.ingest.euroleague import MIN_INTERVAL_S, ingest_seasons
from eurohoops.ingest.http import Fetcher
from eurohoops.parse.games import build_games_table
from tests.conftest import FIXTURES

LIVE = 2026
GOOD = (FIXTURES / "schedule_E2026.json").read_bytes()
BASE_GAME = json.loads(GOOD)["data"][0]


def schedule_of(n: int) -> bytes:
    """A schedule of ``n`` distinct games (the fixture's first game, renumbered)."""
    games = []
    for code in range(1, n + 1):
        game = copy.deepcopy(BASE_GAME)
        game["identifier"], game["gameCode"] = f"E{LIVE}_{code}", code
        games.append(game)
    return json.dumps({"data": games}).encode()


class ScheduleReply:
    """Serves ``reply`` (HTTP 200) for every request."""

    def __init__(self, reply: bytes) -> None:
        self.reply = reply

    def __call__(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=self.reply)


def fetcher_for(reply: bytes) -> Fetcher:
    return Fetcher(
        httpx.Client(transport=httpx.MockTransport(ScheduleReply(reply))), MIN_INTERVAL_S
    )


def cache_path(root: Path) -> Path:
    return root / "schedule" / f"E{LIVE}.json.gz"


def seed(root: Path, payload: bytes) -> bytes:
    """Cache ``payload`` as the live schedule (a first fetch is always accepted)."""
    ingest_seasons(fetcher_for(payload), root, [LIVE], False, LIVE)
    return read_cached(cache_path(root))


def fetch(root: Path, reply: bytes) -> list:
    return ingest_seasons(fetcher_for(reply), root, [LIVE], False, LIVE)[LIVE]


def warning_lines(output: str) -> list[str]:
    return [
        line
        for line in output.splitlines()
        if line.startswith("::warning title=Schedule rejected::")
    ]


@pytest.mark.usefixtures("no_sleep")
def test_an_empty_response_keeps_the_cached_schedule(tmp_path: Path, capsys) -> None:
    before = seed(tmp_path, GOOD)
    games = fetch(tmp_path, b'{"data": []}')  # does not raise
    assert read_cached(cache_path(tmp_path)) == before
    assert len(games) == len(json.loads(GOOD)["data"])
    assert warning_lines(capsys.readouterr().out) == [
        "::warning title=Schedule rejected::2026 response has no games: cached 2 games, new 0"
    ]


@pytest.mark.usefixtures("no_sleep")
def test_a_malformed_response_keeps_the_cached_schedule(tmp_path: Path, capsys) -> None:
    before = seed(tmp_path, GOOD)
    games = fetch(tmp_path, b"{not json")
    assert read_cached(cache_path(tmp_path)) == before
    assert len(games) == 2
    assert warning_lines(capsys.readouterr().out) == [
        "::warning title=Schedule rejected::2026 response is not a schedule (JSONDecodeError): "
        "cached 2 games, new 0"
    ]


@pytest.mark.usefixtures("no_sleep")
def test_a_shrink_of_four_games_is_refused(tmp_path: Path, capsys) -> None:
    before = seed(tmp_path, schedule_of(100))
    games = fetch(tmp_path, schedule_of(96))
    assert read_cached(cache_path(tmp_path)) == before
    assert len(games) == 100
    assert "drops 4 games (4.0%)" in warning_lines(capsys.readouterr().out)[0]


@pytest.mark.usefixtures("no_sleep")
def test_a_shrink_of_eleven_percent_is_refused(tmp_path: Path) -> None:
    before = seed(tmp_path, schedule_of(300))
    games = fetch(tmp_path, schedule_of(267))  # 33 of 300 games: 11%
    assert read_cached(cache_path(tmp_path)) == before
    assert len(games) == 300


@pytest.mark.usefixtures("no_sleep")
def test_a_shrink_of_three_games_is_accepted(tmp_path: Path) -> None:
    seed(tmp_path, schedule_of(100))
    reply = schedule_of(97)
    games = fetch(tmp_path, reply)
    assert read_cached(cache_path(tmp_path)) == reply
    assert len(games) == 97


@pytest.mark.usefixtures("no_sleep")
def test_growth_is_accepted(tmp_path: Path) -> None:
    seed(tmp_path, schedule_of(100))
    reply = schedule_of(110)
    assert len(fetch(tmp_path, reply)) == 110
    assert read_cached(cache_path(tmp_path)) == reply


@pytest.mark.usefixtures("no_sleep")
def test_the_share_rule_also_applies_to_small_caches(tmp_path: Path) -> None:
    # 3 of 20 games is 15%: within the 3-game rule, beyond the 10% rule
    before = seed(tmp_path, schedule_of(20))
    assert len(fetch(tmp_path, schedule_of(17))) == 20
    assert read_cached(cache_path(tmp_path)) == before


@pytest.mark.usefixtures("no_sleep")
def test_a_first_fetch_that_is_empty_writes_nothing(tmp_path: Path, capsys) -> None:
    games = fetch(tmp_path, b'{"data": []}')  # does not raise
    assert games == []
    assert not cache_path(tmp_path).exists()
    assert warning_lines(capsys.readouterr().out) == [
        "::warning title=Schedule rejected::2026 response has no games: cached 0 games, new 0"
    ]


@pytest.mark.usefixtures("no_sleep")
def test_a_first_fetch_that_is_malformed_writes_nothing(tmp_path: Path) -> None:
    assert fetch(tmp_path, b"{not json") == []
    assert not cache_path(tmp_path).exists()


@pytest.mark.usefixtures("no_sleep")
def test_a_normal_schedule_is_cached_byte_for_byte(tmp_path: Path) -> None:
    schedules = ingest_seasons(fetcher_for(GOOD), tmp_path, [LIVE], False, LIVE)
    assert len(schedules[LIVE]) == len(json.loads(GOOD)["data"])
    assert read_cached(cache_path(tmp_path)) == GOOD


@pytest.mark.usefixtures("no_sleep")
def test_the_daily_ingest_finishes_with_exit_0_when_the_schedule_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The daily job runs `eurohoops ingest`; relative data paths resolve under tmp_path.
    monkeypatch.chdir(tmp_path)
    before = seed(tmp_path / "data" / "raw" / "euroleague", GOOD)
    transport = httpx.MockTransport(ScheduleReply(b'{"data": []}'))
    monkeypatch.setattr(
        "eurohoops.cli.ingest.make_client", lambda: httpx.Client(transport=transport)
    )
    result = CliRunner().invoke(cli_app, ["ingest", "--current-only"])
    assert result.exit_code == 0, result.output
    assert warning_lines(result.output) == [
        "::warning title=Schedule rejected::2026 response has no games: cached 2 games, new 0"
    ]
    assert read_cached(cache_path(tmp_path / "data" / "raw" / "euroleague")) == before


def test_an_empty_games_table_is_what_an_empty_season_would_build() -> None:
    # Downstream of the fetch: an empty season builds an empty games table without an error.
    assert len(build_games_table({LIVE: []})) == 0
