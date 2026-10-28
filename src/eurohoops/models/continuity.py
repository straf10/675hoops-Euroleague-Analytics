"""Roster continuity, minutes-weighted.

A club's returning-minutes share for a season: of last season's minutes for the club, the share
played by players on this season's roster. Roster membership is the ELOR protocol's
(``docs/models/elo_roster_prior.md``, ``models/roster.py``): the season roster list, read at the
season's first-round cutoff. A 25-minute starter who left counts about 25 times a 1-minute player.

A player who moved between two clubs keeps his last-season minutes with the club he played for.
He is on the new club's roster, but his old minutes are not the new club's, so he adds nothing to
that club's share, and he is a departure for the old club.

``parse/continuity.py`` is about club codes, not players, and is not this module.
"""

from __future__ import annotations

import pandas as pd

from eurohoops.models.minutes import round_cutoffs
from eurohoops.models.roster import on_roster

PLAYER_COLUMNS = ["season", "team", "player_id", "last_sec", "returning"]
CLUB_COLUMNS = ["team", "last_sec", "returning_sec", "share"]


def season_start_roster(roster: pd.DataFrame, games: pd.DataFrame, season: int) -> pd.DataFrame:
    """The season's roster rows in force at its first round (``models/roster.py:on_roster``)."""
    cutoffs = round_cutoffs(games[games["season"].astype(int) == season])
    if cutoffs.empty:
        return roster.iloc[0:0]
    return on_roster(roster, float(cutoffs.min()), season)


def player_continuity(minutes: pd.DataFrame, roster: pd.DataFrame, season: int) -> pd.DataFrame:
    """One row per player who played for a club in ``season - 1`` (``PLAYER_COLUMNS``).

    ``minutes``: box player lines (``season``, ``team``, ``player_id``, ``sec``), any phase.
    ``roster``: the season's start roster (``club``, ``player_id``), as ``season_start_roster``.
    ``returning`` is true when he is on that same club's roster this season.
    """
    lines = minutes[minutes["season"].astype(int) == season - 1]
    totals = lines.groupby(["team", "player_id"], as_index=False)["sec"].sum()
    last = totals[totals["sec"] > 0]
    on_club = set(zip(roster["club"].astype(str), roster["player_id"].astype(str), strict=True))
    returning = [
        (str(team), str(pid)) in on_club
        for team, pid in zip(last["team"], last["player_id"], strict=True)
    ]
    out = pd.DataFrame(
        {
            "season": pd.Series([season] * len(last), dtype="int64"),
            "team": last["team"].astype(str).to_numpy(),
            "player_id": last["player_id"].astype(str).to_numpy(),
            "last_sec": last["sec"].astype("int64").to_numpy(),
            "returning": pd.Series(returning, dtype=bool),
        }
    )
    return out.reset_index(drop=True)[PLAYER_COLUMNS]


def club_share(players: pd.DataFrame) -> pd.DataFrame:
    """Per club (``CLUB_COLUMNS``): last season's seconds, the returning seconds, and the share.

    A club with no last-season minutes (a new club, or a first season) has no row.
    """
    played = players.assign(ret_sec=players["last_sec"].where(players["returning"], 0))
    out = played.groupby("team", as_index=False).agg(
        last_sec=("last_sec", "sum"), returning_sec=("ret_sec", "sum")
    )
    out = out[out["last_sec"] > 0].copy()
    out["share"] = out["returning_sec"] / out["last_sec"]
    return out[CLUB_COLUMNS].reset_index(drop=True)
