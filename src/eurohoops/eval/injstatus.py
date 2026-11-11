"""Injury-status diagnostic (B3, research only): how often a player listed with each BasketNews
status played in his club's next game. Rule and declaration: docs/models/diag_injstatus.md.

Pure functions. The injury rows come matched from ``models.availability.match_injuries``, and the
player minutes from ``stats.box.build_box_games``; nothing is read or written here.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from eurohoops.logs import TIME_FORMAT
from eurohoops.models.availability import MATCHED, latest_snapshot

MAX_SNAPSHOT_AGE = timedelta(hours=24)
MIN_N = 30
Z95 = 1.959963984540054
_ROUND = 6


@dataclass(frozen=True)
class PlayerGames:
    table: pd.DataFrame  # one row per (game, club, matched player) listed in the side's snapshot
    sides_without_snapshot: int
    unmatched_rows: int  # listed rows that name no roster player (never in the table)


def finished_sides(games: pd.DataFrame, season: int) -> pd.DataFrame:
    """One row per club side of a played, non-forfeit game of ``season``: game_id, club, tipoff_utc.

    ``games`` needs game_id, season, home, away, tipoff_utc, played and forfeit.
    """
    done = games[
        (games["season"] == season) & games["played"].astype(bool) & ~games["forfeit"].astype(bool)
    ]
    sides = [
        done.assign(club=done[side])[["game_id", "club", "tipoff_utc"]] for side in ("home", "away")
    ]
    return pd.concat(sides, ignore_index=True).astype({"game_id": str, "club": str})


def side_snapshot(matched: pd.DataFrame, tipoff: datetime) -> pd.Timestamp | None:
    """The snapshot a side uses: the latest one stamped strictly before tip-off, if it is at most
    24 hours before tip-off. None when there is none, or when it is older (no fallback)."""
    stamp = latest_snapshot(matched, tipoff)
    if stamp is None or pd.Timestamp(tipoff) - stamp > MAX_SNAPSHOT_AGE:
        return None
    return stamp


def player_games(matched: pd.DataFrame, sides: pd.DataFrame, box: pd.DataFrame) -> PlayerGames:
    """The matched players listed for each side in its snapshot, with status, position, seconds.

    A matched player with no box row for the game did not play (seconds 0). ``box`` needs game_id,
    player_id and sec (``build_box_games`` players: a DNP line is absent).
    """
    stamps = pd.to_datetime(matched["snapshot_utc"], format=TIME_FORMAT, utc=True)
    frames: list[pd.DataFrame] = []
    without = 0
    for game_id, club, tipoff in sides.itertuples(index=False):
        stamp = side_snapshot(matched, tipoff)
        if stamp is None:
            without += 1
            continue
        rows = matched[(stamps == stamp) & (matched["team"] == club)].copy()
        rows["game_id"] = game_id
        frames.append(rows)
    listed = pd.concat(frames, ignore_index=True) if frames else matched.iloc[:0].assign(game_id="")
    known = listed[listed["match"] == MATCHED]
    seen = box[["game_id", "player_id", "sec"]].astype({"game_id": str, "player_id": str})
    table = known.merge(seen, on=["game_id", "player_id"], how="left")
    table["seconds"] = table["sec"].fillna(0).astype("int64")
    table["played"] = table["seconds"] > 0
    table = table.rename(columns={"team": "club"})
    cols = ["game_id", "club", "player_id", "status", "position", "played", "seconds"]
    return PlayerGames(table[cols], without, len(listed) - len(known))


def wilson(k: int, n: int) -> tuple[float, float]:
    """The 95% Wilson score interval for k successes in n trials."""
    if n <= 0:
        raise ValueError("wilson needs n > 0")
    p = k / n
    z2 = Z95 * Z95
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return centre - half, centre + half


def _status_summary(table: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Per status: n; with n >= MIN_N also the played count, the rate and its Wilson interval."""
    out: dict[str, dict[str, Any]] = {}
    for status, part in table.groupby("status"):
        n = len(part)
        if n < MIN_N:
            out[str(status)] = {"n": n}
            continue
        played = int(part["played"].sum())
        low, high = wilson(played, n)
        out[str(status)] = {
            "n": n,
            "played": played,
            "rate": round(played / n, _ROUND),
            "ci95": [round(low, _ROUND), round(high, _ROUND)],
        }
    return dict(sorted(out.items()))


def build_report(
    games: pd.DataFrame, matched: pd.DataFrame, box: pd.DataFrame, season: int
) -> dict[str, Any]:
    """The diagnostic for one season: totals, then the played rate per BasketNews status."""
    sides = finished_sides(games, season)
    found = player_games(matched, sides, box)
    return {
        "season": season,
        "totals": {
            "games": int(sides["game_id"].nunique()),
            "club_sides": len(sides),
            "sides_with_snapshot": len(sides) - found.sides_without_snapshot,
            "sides_without_snapshot": found.sides_without_snapshot,
            "listed_matched": len(found.table),
            "listed_unmatched": found.unmatched_rows,
        },
        "statuses": _status_summary(found.table),
    }
