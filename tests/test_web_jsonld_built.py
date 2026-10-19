"""The built site's SportsEvent markup: every event has a name, a startDate with a time zone (or a
bare date while the time is unconfirmed) and a location, and no nested event lacks them.

Reads the static build in site/ (a build output, not in git); skipped until the site is built."""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import REPO

SITE = REPO / "site"
BLOCK = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.DOTALL)
# An ISO date, or a date and time with a zone (Z or an offset).
START = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2}))?$")


def _blocks(page: Path) -> list[Any]:
    return [json.loads(match) for match in BLOCK.findall(page.read_text(encoding="utf-8"))]


def _events(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _events(item)
    elif isinstance(node, dict):
        if node.get("@type") == "SportsEvent":
            yield node
        for value in node.values():
            yield from _events(value)


def _game_pages() -> list[Path]:
    games = SITE / "games"
    if not games.is_dir():
        return []
    chosen = [games / "E2023_115" / "index.html", games / "E2025_219" / "index.html"]
    rest = sorted(p for p in games.glob("*/index.html") if p not in chosen)
    return [p for p in [*chosen, *rest[:2]] if p.is_file()]


@pytest.fixture
def pages() -> list[Path]:
    found = _game_pages()
    if not found:
        pytest.skip("site/ is not built (run astro build in web/)")
    return found


def test_every_game_page_event_has_name_start_and_location(pages: list[Path]) -> None:
    checked = 0
    for page in pages:
        for block in _blocks(page):
            for event in _events(block):
                checked += 1
                assert event.get("name"), f"{page}: event without a name"
                assert START.match(str(event.get("startDate", ""))), f"{page}: bad startDate"
                assert event.get("location", {}).get("name"), f"{page}: event without a location"
                assert "superEvent" not in event, f"{page}: nested season event"
    assert checked >= len(pages), "no SportsEvent found on the game pages"


def test_game_page_event_is_completed_with_a_zoned_start(pages: list[Path]) -> None:
    page = next((p for p in pages if p.parent.name == "E2023_115"), pages[0])
    (event,) = [e for b in _blocks(page) for e in _events(b)]
    assert event["eventStatus"] == "https://schema.org/EventCompleted"
    assert re.search(r"(Z|[+-]\d{2}:\d{2})$", event["startDate"]), event["startDate"]
    assert event["eventAttendanceMode"] == "https://schema.org/OfflineEventAttendanceMode"
    assert "offers" not in event
    assert event["image"].endswith("/og.png")


def test_home_page_events_have_location_and_start(pages: list[Path]) -> None:
    home = SITE / "index.html"
    if not home.is_file():
        pytest.skip("site/index.html is not built")
    for block in _blocks(home):
        for event in _events(block):
            assert event.get("location", {}).get("name"), "home page event without a location"
            assert START.match(str(event.get("startDate", "")))
