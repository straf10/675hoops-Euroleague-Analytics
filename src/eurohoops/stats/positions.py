"""Player positions from the cached EuroLeague people listing (``people/E{season}.json.gz``).

Each listing row gives a player one of Guard, Forward or Center for a season and a club. The
rules (owner-decided, SITE_FEEDBACK "Decided 2026-10-10"):

- a season uses its own listing;
- two listings in one season: the club he played the most games for (the later-signed one on a tie);
- no listing that season: his latest listing from an earlier season, else the earliest later one;
- no listing at all: absent (the site shows him only under "All").
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from eurohoops.ingest.bios import EL_PLAYER_TYPE
from eurohoops.ingest.cache import read_cached

POS = {"Guard": "G", "Forward": "F", "Center": "C"}

# player id -> season -> club -> games played (source club codes)
GamesByClub = Mapping[str, Mapping[int, Mapping[str, int]]]


def _listings(el_raw: Path) -> dict[str, dict[int, list[tuple[str, str, str]]]]:
    """player id -> season -> [(club, sign date, G/F/C)] from every cached people file."""
    out: dict[str, dict[int, list[tuple[str, str, str]]]] = {}
    for path in sorted((el_raw / "people").glob("E*.json.gz")):
        season = int(path.name.removeprefix("E").split(".")[0])
        rows: list[dict[str, Any]] = json.loads(read_cached(path))["data"]
        for row in rows:
            pos = POS.get(str(row.get("positionName")))
            if row.get("type") != EL_PLAYER_TYPE or pos is None:
                continue
            pid = "P" + str(row["person"]["code"]).strip()
            club = str((row.get("club") or {}).get("code") or "")
            out.setdefault(pid, {}).setdefault(season, []).append(
                (club, str(row.get("startDate") or ""), pos)
            )
    return out


def season_positions(el_raw: Path, games_by_club: GamesByClub) -> dict[str, dict[int, str]]:
    """player id -> season -> "G" | "F" | "C", for every season he played or was listed."""
    out: dict[str, dict[int, str]] = {}
    for pid, by_season in _listings(el_raw).items():
        played = games_by_club.get(pid, {})
        own: dict[int, str] = {}
        for season, rows in by_season.items():
            own[season] = max(rows, key=lambda r: (played.get(season, {}).get(r[0], 0), r[1]))[2]
        resolved = dict(own)
        for season in set(played) - set(own):
            earlier = [s for s in own if s < season]
            later = [s for s in own if s > season]
            resolved[season] = own[max(earlier)] if earlier else own[min(later)]
        out[pid] = dict(sorted(resolved.items()))
    return out


def games_by_club(players: pd.DataFrame) -> dict[str, dict[int, dict[str, int]]]:
    """Games per player, season and club from the box-score player lines."""
    out: dict[str, dict[int, dict[str, int]]] = {}
    counts = players.groupby(["player_id", "season", "team"], sort=False).size().reset_index()
    for pid, season, team, n in counts.itertuples(index=False):
        out.setdefault(str(pid), {}).setdefault(int(season), {})[str(team)] = int(n)
    return out
