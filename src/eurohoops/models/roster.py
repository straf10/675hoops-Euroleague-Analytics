"""EuroLeague season roster lists for the ELOR roster prior (docs/models/elo_roster_prior.md).

Source: the cached people listing of each season, ``data/raw/euroleague/people/E{season}.json.gz``
(``ingest.bios``). Only rows with ``type == "J"`` (players) count. Each row gives the player
(``person.code``; the box-score id is ``"P" + code``, as ``bios.parse_el_people``), the club
(``club.code``, the source code the ``games`` mart uses) and the registration window
``startDate`` / ``endDate`` (``endDate`` may be empty; one 2014 row has no ``startDate`` either
and counts from before the season, declared). This module only reads the cache: a
missing season file is an error, never a fetch.

**Times.** The listing's stamps carry no time zone. They are read as UTC (declared): most are
midnight stamps, and the cutoffs they are compared with are tip-offs in the evening.

**Membership at a cutoff (protocol decision 0, option A).** A player is on a club's roster for a
game when his ``startDate`` is before the game's cutoff (``minutes.round_cutoffs``: the first
tip-off of its ``(season, phase, round)``) and his ``endDate``, if any, is after it. A
registration stamped while the season's first round is under way follows the same rule
(``FIRST_ROUND_RULE``, strict, owner decision 5): it counts from round 2.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa

from eurohoops.ingest.bios import EL_PLAYER_TYPE, el_people_path
from eurohoops.ingest.cache import read_cached
from eurohoops.models.minutes import round_cutoffs
from eurohoops.parse.schemas import validated

ROSTER_SCHEMA = pa.DataFrameSchema(
    {
        "season": pa.Column("int64"),
        "club": pa.Column(str),
        "player_id": pa.Column(str),
        "start": pa.Column("float64", nullable=True),  # epoch seconds (UTC); NaN = no stamp
        "end": pa.Column("float64", nullable=True),  # epoch seconds; NaN = open-ended
    },
    strict=True,
)

# Registrations stamped during the season's first round (Build addendum; owner decision 5,
# 2026-10-15): strict, a stamp counts from its own time only, so such a player joins from round 2.
FIRST_ROUND_RULE = "strict"


class RosterCacheError(FileNotFoundError):
    """A season's roster list is not in the raw cache (it is never fetched here)."""


def _stamp(text: str | None) -> float:
    if not text:
        return float("nan")
    stamp = pd.Timestamp(text)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return float(stamp.timestamp())


def parse_roster(payload: bytes, season: int) -> pd.DataFrame:
    """Player rows of one season's people listing (``ROSTER_SCHEMA``)."""
    rows = json.loads(payload)["data"]
    out = [
        {
            "season": season,
            "club": str(row["club"]["code"]).strip(),
            "player_id": "P" + str(row["person"]["code"]).strip(),
            "start": _stamp(row.get("startDate")),
            "end": _stamp(row.get("endDate")),
        }
        for row in rows
        if row.get("type") == EL_PLAYER_TYPE
    ]
    return validated(pd.DataFrame(out, columns=list(ROSTER_SCHEMA.columns)), ROSTER_SCHEMA)


def read_rosters(el_raw: Path, seasons: Iterable[int]) -> pd.DataFrame:
    """The cached roster lists of ``seasons`` (cache only; a missing file raises)."""
    frames = []
    for season in seasons:
        path = el_people_path(el_raw, season)
        if not path.exists():
            raise RosterCacheError(f"no cached roster list {path}; run: eurohoops ingest-bios")
        frames.append(parse_roster(read_cached(path), season))
    if not frames:
        return validated(pd.DataFrame(columns=list(ROSTER_SCHEMA.columns)), ROSTER_SCHEMA)
    return pd.concat(frames, ignore_index=True)


def unmatched_clubs(roster: pd.DataFrame, games: pd.DataFrame) -> dict[int, dict[str, list[str]]]:
    """Per season, roster clubs absent from the ``games`` mart and game clubs absent from the
    roster list (empty dict: the codes agree; both use the EuroLeague source codes)."""
    out: dict[int, dict[str, list[str]]] = {}
    for season in sorted(set(roster["season"].astype(int)) & set(games["season"].astype(int))):
        listed = set(roster.loc[roster["season"] == season, "club"])
        part = games[games["season"] == season]
        playing = set(part["home"].astype(str)) | set(part["away"].astype(str))
        if listed != playing:
            out[season] = {
                "roster_only": sorted(listed - playing),
                "games_only": sorted(playing - listed),
            }
    return out


@dataclass(frozen=True)
class SeasonRounds:
    """Each season's first and second round cutoffs (epoch seconds; NaN with one round)."""

    first: dict[int, float]
    second: dict[int, float]


def season_rounds(games: pd.DataFrame) -> SeasonRounds:
    cutoffs = round_cutoffs(games)
    first: dict[int, float] = {}
    second: dict[int, float] = {}
    for season, values in cutoffs.groupby(games["season"].astype(int)):
        distinct = np.unique(values.to_numpy(dtype=np.float64))
        first[int(season)] = float(distinct[0])
        second[int(season)] = float(distinct[1]) if len(distinct) > 1 else float("nan")
    return SeasonRounds(first, second)


def on_roster(roster: pd.DataFrame, cutoff: float, season: int) -> pd.DataFrame:
    """Roster rows of ``season`` in force at ``cutoff`` (``FIRST_ROUND_RULE``, strict): start
    before it (a missing start counts from before the season), end (if any) after it."""
    part = roster[roster["season"] == season]
    start = part["start"].astype("float64").fillna(-np.inf)
    end = part["end"]
    keep = (start < cutoff) & (end.isna() | (end > cutoff))
    out: pd.DataFrame = part[keep]
    return out


def start_date_counts(roster: pd.DataFrame, games: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Per season: player rows, rows whose ``startDate`` is at or after the season's first
    cutoff (round 1 has begun), and of those the ones before the second round's cutoff."""
    rounds = season_rounds(games)
    out: dict[str, dict[str, int]] = {}
    for season in sorted(set(roster["season"].astype(int)) & set(rounds.first)):
        part = roster[roster["season"] == season]
        first, second = rounds.first[season], rounds.second[season]
        after = part["start"] >= first
        in_first = after & ((part["start"] < second) if not np.isnan(second) else True)
        out[str(season)] = {
            "players": len(part),
            "start_after_round1_began": int(after.sum()),
            "start_during_round1": int(in_first.sum()),
            "start_after_round1": int((after & ~in_first).sum()),
        }
    return out
