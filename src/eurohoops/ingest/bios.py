"""Player bios (birth date, country) of the EuroLeague people listings, cached like every raw page.

Cache layout:
  data/raw/euroleague/people/E{season}.json.gz     every person of a EuroLeague season (one call)

Birth dates are a matching feature only: they stay in ``data/`` and never reach a committed file,
a report or the site.
"""

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path

import pandas as pd

from eurohoops.ingest.cache import read_cached, write_atomic
from eurohoops.ingest.http import Fetcher

EL_PEOPLE_URL = (
    "https://api-live.euroleague.net/v2/competitions/E/seasons/E{season}/people?limit=2000"
)
EL_PLAYER_TYPE = "J"  # people rows also hold coaches, staff and referees
BIO_COLUMNS = ["competition", "source_id", "birth_date", "country"]


def el_people_path(el_raw: Path, season: int) -> Path:
    return el_raw / "people" / f"E{season}.json.gz"


def ingest_bios(el_fetcher: Fetcher, *, el_raw: Path, el_seasons: Iterable[int]) -> int:
    """Cache the missing EuroLeague people listings; return how many were fetched."""
    fetched = 0
    for season in el_seasons:
        path = el_people_path(el_raw, season)
        if not path.exists():
            write_atomic(path, el_fetcher.get(EL_PEOPLE_URL.format(season=season)))
            fetched += 1
    return fetched


def refresh_people(fetcher: Fetcher, *, el_raw: Path, season: int) -> int:
    """Refetch one season's people listing (one call), replacing the cached file atomically.

    Returns the number of rows in the new listing. A payload without a ``data`` list is rejected
    before it can replace a good cache.
    """
    payload = fetcher.get(EL_PEOPLE_URL.format(season=season))
    rows = json.loads(payload)["data"]
    if not isinstance(rows, list):
        raise ValueError(f"people listing for E{season} has no data list")
    write_atomic(el_people_path(el_raw, season), payload)
    return len(rows)


def parse_el_people(payload: bytes) -> list[tuple[str, date | None, str | None]]:
    """(box-score player id, birth date, country) of each player row of a season's people."""
    rows = json.loads(payload)["data"]
    out = []
    for row in rows:
        if row.get("type") != EL_PLAYER_TYPE:
            continue
        person = row["person"]
        born = person.get("birthDate")
        country = (person.get("country") or {}).get("code")
        out.append(
            (
                "P" + str(person["code"]).strip(),
                date.fromisoformat(born[:10]) if born else None,
                country,
            )
        )
    return out


def build_bios(el_raw: Path) -> pd.DataFrame:
    """One row per cached source id (``BIO_COLUMNS``); the first non-empty birth date wins."""
    rows: list[tuple[str, str, date | None, str | None]] = []
    for path in sorted((el_raw / "people").glob("E*.json.gz")):
        rows.extend(
            ("euroleague", pid, born, country)
            for pid, born, country in parse_el_people(read_cached(path))
        )
    table = pd.DataFrame(rows, columns=BIO_COLUMNS)
    table["has_date"] = table["birth_date"].notna()
    table = table.sort_values(
        ["competition", "source_id", "has_date"], ascending=[True, True, False]
    )
    return (
        table.drop_duplicates(["competition", "source_id"])
        .drop(columns="has_date")
        .reset_index(drop=True)
    )
