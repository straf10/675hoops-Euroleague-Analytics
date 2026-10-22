"""M5-INJ availability: BasketNews "Out" statuses applied to M5's projected minute shares
(docs/models/m5_inj.md, the declared player-matching rule and the information cutoff).

Pure functions. ``read_roster_names`` and ``read_injuries`` only read the caches the daily job
already has; nothing is fetched here.
"""

import json
from collections import defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.entity.translit import latin_key
from eurohoops.ingest.cache import read_cached
from eurohoops.logs import TIME_FORMAT

OUT = "Out"
MATCHED, AMBIGUOUS, NO_MATCH = "matched", "ambiguous", "no_roster_match"
INJURY_DTYPES = {
    "snapshot_utc": str,
    "team": str,
    "player": str,
    "bn_player_id": str,
    "status": str,
}


@dataclass(frozen=True)
class RosterPlayer:
    player_id: str  # the box-score id: "P" + the people listing's code
    club: str  # the source club code, as the games mart uses
    name: str  # the listing's name, "SURNAME, NAME"


def parse_roster_names(payload: bytes) -> list[RosterPlayer]:
    """Players (``type == "J"``) of a season's people listing, as roster names."""
    rows = json.loads(payload)["data"]
    return [
        RosterPlayer(
            "P" + str(row["person"]["code"]).strip(),
            str(row["club"]["code"]).strip(),
            str(row["person"]["name"]),
        )
        for row in rows
        if row.get("type") == "J"
    ]


def read_roster_names(path: Path) -> list[RosterPlayer]:
    """The cached people listing of a season (a missing file is an error, never a fetch)."""
    return parse_roster_names(read_cached(path))


def read_injuries(path: Path) -> pd.DataFrame:
    """The injury log; an absent log is empty (no statuses, so M5-INJ equals M5)."""
    if not path.exists():
        return pd.DataFrame(columns=list(INJURY_DTYPES))
    return pd.read_csv(path, dtype=INJURY_DTYPES, keep_default_na=False)


def match_injuries(injuries: pd.DataFrame, roster: Iterable[RosterPlayer]) -> pd.DataFrame:
    """Each injury row with the roster player it names, or why it names none.

    A row matches iff exactly one roster player has the same club code and the same
    ``latin_key`` of the name. Two or more such players: ``ambiguous``; none: ``no_roster_match``.
    Columns: the injury row's columns plus ``player_id`` (empty unless matched) and ``match``.
    """
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for p in roster:
        by_key[(p.club, latin_key(p.name))].add(p.player_id)
    out = injuries.copy()
    ids = []
    verdicts = []
    for team, name in zip(out["team"], out["player"], strict=True):
        found = sorted(by_key.get((str(team), latin_key(str(name))), set()))
        if len(found) == 1:
            ids.append(found[0])
            verdicts.append(MATCHED)
        else:
            ids.append("")
            verdicts.append(AMBIGUOUS if found else NO_MATCH)
    out["player_id"] = ids
    out["match"] = verdicts
    return out


def out_players(matched: pd.DataFrame, cutoff: datetime) -> set[str]:
    """Player ids whose latest status before ``cutoff`` is ``Out``.

    Only snapshots stamped strictly before ``cutoff`` count. A player's status is that of the
    latest such snapshot in which he is listed; he is ``Out`` if any of his rows in that snapshot
    says ``Out``. Unmatched rows are ignored.
    """
    if matched.empty:
        return set()
    rows = matched[matched["match"] == MATCHED]
    stamps = pd.to_datetime(rows["snapshot_utc"], format=TIME_FORMAT, utc=True)
    limit = pd.Timestamp(cutoff)
    limit = limit.tz_localize("UTC") if limit.tzinfo is None else limit
    before = rows[stamps < limit]
    if before.empty:
        return set()
    latest = before.assign(stamp=stamps[before.index])
    out: set[str] = set()
    for _, group in latest.groupby("player_id"):
        newest = group[group["stamp"] == group["stamp"].max()]
        if (newest["status"] == OUT).any():
            out.add(str(group["player_id"].iloc[0]))
    return out


def apply_out(shares: pd.DataFrame, game_ids: Collection[str], out: set[str]) -> pd.DataFrame:
    """M5's projected shares with the ``out`` players set to zero in the ``game_ids`` games.

    Per (game, side): the out players are dropped and the rest are scaled so the side's share
    total is unchanged, then capped at 1 (as ``rotation._drop_absent``). A side where nobody is
    out, or where every player is out, is left unchanged. Other games are never touched.
    """
    if not out or not len(game_ids):
        return shares
    result = shares.reset_index(drop=True)
    targets = result["game_id"].isin(set(map(str, game_ids)))
    drop_index: list[int] = []
    for _, group in result[targets].groupby(["game_id", "side"]):
        is_out = group["player_id"].isin(out).to_numpy()
        if not is_out.any() or is_out.all():
            continue
        kept = group[~is_out]
        kept_sum = float(kept["share"].sum())
        if kept_sum <= 0:
            continue
        scale = float(group["share"].sum()) / kept_sum
        result.loc[kept.index, "share"] = np.minimum(1.0, kept["share"].to_numpy() * scale)
        drop_index.extend(group.index[is_out].tolist())
    return result.drop(index=drop_index).reset_index(drop=True)
