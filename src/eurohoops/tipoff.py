"""The first confirmed, unplayed EuroLeague tip-off of a UTC day (match-day recorder clock)."""

from datetime import date, datetime

import pandas as pd


def first_tipoff_on(games: pd.DataFrame, day: date) -> datetime | None:
    """Earliest tip-off on ``day`` (UTC date) among games that are confirmed and not yet played.

    ``games`` is the games mart (``tipoff_utc`` tz-aware UTC). None when there is no such game.
    """
    tipoff = pd.to_datetime(games["tipoff_utc"], utc=True)
    open_games = games["confirmed_date"].astype(bool) & ~games["played"].astype(bool)
    pending = tipoff[(tipoff.dt.date == day) & open_games]
    if pending.empty:
        return None
    first: datetime = pending.min().to_pydatetime()
    return first
