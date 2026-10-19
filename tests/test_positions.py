"""Positions from the EuroLeague people listing, and the daily live-season refresh."""

import gzip
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest
from typer.testing import CliRunner

from eurohoops import cli
from eurohoops.cli import ingest as ingest_mod
from eurohoops.ingest.bios import el_people_path, refresh_people
from eurohoops.ingest.http import Fetcher
from eurohoops.stats.positions import games_by_club, season_positions

runner = CliRunner()


def person(code: str, pos: str, club: str, start: str = "2024-09-01", kind: str = "J") -> dict:
    return {
        "person": {"code": code},
        "type": kind,
        "positionName": pos,
        "startDate": start,
        "club": {"code": club},
    }


def write_people(el_raw: Path, season: int, rows: list[dict]) -> None:
    path = el_people_path(el_raw, season)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps({"data": rows}).encode()))


def test_each_season_uses_its_own_listing(tmp_path: Path) -> None:
    write_people(tmp_path, 2023, [person("000001", "Guard", "AAA")])
    write_people(tmp_path, 2024, [person("000001", "Forward", "AAA")])
    played = {"P000001": {2023: {"AAA": 20}, 2024: {"AAA": 20}}}
    assert season_positions(tmp_path, played) == {"P000001": {2023: "G", 2024: "F"}}


def test_two_listings_in_a_season_take_the_club_with_most_games(tmp_path: Path) -> None:
    write_people(
        tmp_path,
        2024,
        [
            person("000002", "Forward", "AAA", "2024-09-01"),
            person("000002", "Center", "BBB", "2025-01-10"),
        ],
    )
    played = {"P000002": {2024: {"AAA": 25, "BBB": 5}}}
    assert season_positions(tmp_path, played)["P000002"] == {2024: "F"}
    played = {"P000002": {2024: {"AAA": 5, "BBB": 25}}}
    assert season_positions(tmp_path, played)["P000002"] == {2024: "C"}
    # a tie goes to the later signing
    played = {"P000002": {2024: {"AAA": 5, "BBB": 5}}}
    assert season_positions(tmp_path, played)["P000002"] == {2024: "C"}


def test_season_without_a_listing_falls_back_to_the_latest_earlier_one(tmp_path: Path) -> None:
    write_people(tmp_path, 2020, [person("000003", "Guard", "AAA")])
    write_people(tmp_path, 2022, [person("000003", "Center", "AAA")])
    played = {"P000003": {2020: {"AAA": 9}, 2021: {"AAA": 9}, 2023: {"AAA": 9}}}
    assert season_positions(tmp_path, played)["P000003"] == {
        2020: "G",
        2021: "G",
        2022: "C",
        2023: "C",
    }


def test_season_before_every_listing_takes_the_earliest_later_one(tmp_path: Path) -> None:
    write_people(tmp_path, 2022, [person("000004", "Forward", "AAA")])
    write_people(tmp_path, 2024, [person("000004", "Center", "AAA")])
    played = {"P000004": {2019: {"AAA": 3}}}
    assert season_positions(tmp_path, played)["P000004"][2019] == "F"


def test_no_listing_at_all_is_absent_and_staff_are_ignored(tmp_path: Path) -> None:
    write_people(tmp_path, 2024, [person("000005", "Guard", "AAA", kind="A")])
    positions = season_positions(tmp_path, {"P000006": {2024: {"AAA": 4}}})
    assert positions == {}


def test_games_by_club_counts_player_lines() -> None:
    lines = pd.DataFrame(
        {
            "player_id": ["P1", "P1", "P1", "P2"],
            "season": [2024, 2024, 2024, 2024],
            "team": ["AAA", "AAA", "BBB", "AAA"],
        }
    )
    assert games_by_club(lines) == {"P1": {2024: {"AAA": 2, "BBB": 1}}, "P2": {2024: {"AAA": 1}}}


def test_refresh_overwrites_the_cached_file_with_one_call(tmp_path: Path) -> None:
    write_people(tmp_path, 2026, [person("000001", "Guard", "AAA")])
    calls: list[str] = []
    new = {"data": [person("000001", "Center", "AAA"), person("000007", "Guard", "BBB")]}

    def api(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=json.dumps(new).encode())

    fetcher = Fetcher(httpx.Client(transport=httpx.MockTransport(api)), 0.0)
    assert refresh_people(fetcher, el_raw=tmp_path, season=2026) == 2
    assert len(calls) == 1 and "E2026" in calls[0]
    assert season_positions(tmp_path, {})["P000001"] == {2026: "C"}
    assert not list(tmp_path.glob("people/*.tmp"))


def test_refresh_keeps_the_cache_when_the_payload_is_junk(tmp_path: Path) -> None:
    write_people(tmp_path, 2026, [person("000001", "Guard", "AAA")])
    fetcher = Fetcher(
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'{"data": 1}'))
        ),
        0.0,
    )
    with pytest.raises(ValueError, match="no data list"):
        refresh_people(fetcher, el_raw=tmp_path, season=2026)
    assert season_positions(tmp_path, {})["P000001"] == {2026: "G"}


@pytest.mark.usefixtures("no_sleep")
def test_people_command_refetches_only_the_live_season(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ingest_mod, "LIVE_SEASON", 2026)
    monkeypatch.setattr(ingest_mod, "SITE_SEASONS", 5)  # the window this test caches
    body = json.dumps({"data": [person("000001", "Forward", "AAA")]}).encode()
    urls: list[str] = []

    def api(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, content=body)

    monkeypatch.setattr(
        ingest_mod, "make_client", lambda: httpx.Client(transport=httpx.MockTransport(api))
    )
    raw = ingest_mod.EUROLEAGUE.raw_dir
    for season in (2022, 2023, 2024, 2025):  # earlier site seasons already cached
        write_people(raw, season, [person("000001", "Guard", "AAA")])
    result = runner.invoke(cli.app, ["people"])
    assert result.exit_code == 0, result.output
    assert "E2026: 1 rows" in result.output
    assert len(urls) == 1 and "seasons/E2026/people" in urls[0]


@pytest.mark.usefixtures("no_sleep")
def test_people_command_fills_missing_earlier_seasons_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ingest_mod, "LIVE_SEASON", 2026)
    monkeypatch.setattr(ingest_mod, "SITE_SEASONS", 3)
    body = json.dumps({"data": [person("000001", "Forward", "AAA")]}).encode()
    urls: list[str] = []

    def api(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, content=body)

    monkeypatch.setattr(
        ingest_mod, "make_client", lambda: httpx.Client(transport=httpx.MockTransport(api))
    )
    raw = ingest_mod.EUROLEAGUE.raw_dir
    write_people(raw, 2025, [person("000001", "Guard", "AAA")])
    result = runner.invoke(cli.app, ["people"])
    assert result.exit_code == 0, result.output
    assert "1 missing earlier season(s) cached" in result.output
    assert [u.split("/seasons/")[1].split("/")[0] for u in urls] == ["E2024", "E2026"]
    assert sorted(p.name for p in (raw / "people").iterdir()) == [
        "E2024.json.gz",
        "E2025.json.gz",
        "E2026.json.gz",
    ]
