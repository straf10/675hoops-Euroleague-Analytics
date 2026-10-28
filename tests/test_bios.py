from datetime import date
from pathlib import Path

import httpx
import pytest

from eurohoops.ingest.bios import (
    build_bios,
    el_people_path,
    ingest_bios,
    parse_el_people,
)
from eurohoops.ingest.http import Fetcher

FIXTURES = Path(__file__).parent / "fixtures" / "bios"
EL_PEOPLE = (FIXTURES / "el_people_E2024.json").read_bytes()


def test_el_people_keeps_players_and_prefixes_the_box_id() -> None:
    assert parse_el_people(EL_PEOPLE) == [
        ("P900002", date(1998, 11, 24), "GRE"),
        ("P900003", None, None),
    ]


@pytest.mark.usefixtures("no_sleep")
def test_ingest_caches_once(tmp_path: Path) -> None:
    calls: list[str] = []

    def api(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=EL_PEOPLE)

    fetcher = Fetcher(httpx.Client(transport=httpx.MockTransport(api)), 0.0)
    el_raw = tmp_path / "euroleague"
    assert ingest_bios(fetcher, el_raw=el_raw, el_seasons=[2024]) == 1
    assert ingest_bios(fetcher, el_raw=el_raw, el_seasons=[2024]) == 0
    assert len(calls) == 1
    assert "limit=2000" in calls[0]
    assert el_people_path(el_raw, 2024).exists()

    bios = build_bios(el_raw).astype(object)
    assert bios.where(bios.notna(), None).to_dict("records") == [
        {
            "competition": "euroleague",
            "source_id": "P900002",
            "birth_date": date(1998, 11, 24),
            "country": "GRE",
        },
        {"competition": "euroleague", "source_id": "P900003", "birth_date": None, "country": None},
    ]
