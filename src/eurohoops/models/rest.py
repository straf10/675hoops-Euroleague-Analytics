"""Rest features for game forecasts (M5): how long each team has rested, in EuroLeague games.

For a team and a game with tip-off ``t`` (all times are tip-offs):

- **days_rest**: days (fractional) since the team's previous game, capped at 7; 7.0 when the
  team has no previous game at all.
- **short_rest**: the previous game was at most 2.5 days earlier (D1: no game in the data is
  within 1.5 days, so a back-to-back flag would never fire).
- **games_last_7d**: the team's games with tip-off in ``[t - 7 days, t)``.
- **other_comp_prev**: always False (EuroLeague only since 2026-10-28). The column stays so the
  M5 feature layout is unchanged.

A previous game is a row with ``played`` True and a tip-off strictly before ``t``; forfeits count
when ``played`` is True, unplayed or postponed rows never do, and a game at the same tip-off is
not previous. Scores are never read, so nothing after ``t`` can reach a feature. Every game in
``games`` gets both sides, played or not.
"""

import numpy as np
import pandas as pd
import pandera.pandas as pa

from eurohoops.models.elo import FloatArray
from eurohoops.parse.schemas import validated

SIDES = ("home", "away")
DAY = 86400.0
CAP_DAYS = 7.0
SHORT_REST_DAYS = 2.5

REST_SCHEMA = pa.DataFrameSchema(
    {
        "game_id": pa.Column(str),
        "side": pa.Column(str, pa.Check.isin(SIDES)),
        "team": pa.Column(str),
        "days_rest": pa.Column("float64", [pa.Check.gt(0.0), pa.Check.le(CAP_DAYS)]),
        "short_rest": pa.Column(bool),
        "games_last_7d": pa.Column("int64", pa.Check.ge(0)),
        "other_comp_prev": pa.Column(bool),
    },
    unique=["game_id", "side"],
    strict=True,
)


def _epoch(times: pd.Series) -> FloatArray:
    """Epoch seconds, whatever the timestamps' resolution (s from literals, ns from DuckDB)."""
    epoch = pd.Timestamp(0, tz="UTC")
    seconds: FloatArray = (
        (times.dt.tz_convert("UTC") - epoch).dt.total_seconds().to_numpy(dtype=np.float64)
    )
    return seconds


def _team_rows(games: pd.DataFrame) -> pd.DataFrame:
    """One row per (played game, side): the team's code, and the tip-off in epoch seconds."""
    played = games[games["played"].to_numpy(dtype=bool)]
    time = _epoch(played["tipoff_utc"])
    parts = [pd.DataFrame({"team": played[side].astype(str), "time": time}) for side in SIDES]
    return pd.concat(parts, ignore_index=True)


def rest_features(games: pd.DataFrame) -> pd.DataFrame:
    """Rest features of both sides of every game in ``games`` (see the module docstring)."""
    history = _team_rows(games).sort_values("time", kind="stable")
    by_team = {
        str(team): frame["time"].to_numpy(dtype=np.float64)
        for team, frame in history.groupby("team")
    }
    empty = np.empty(0, dtype=np.float64)
    out: list[dict[str, object]] = []
    for game_id, home, away, time in zip(
        games["game_id"], games["home"], games["away"], _epoch(games["tipoff_utc"]), strict=True
    ):
        for side, team in zip(SIDES, (str(home), str(away)), strict=True):
            times = by_team.get(team, empty)
            before = int(np.searchsorted(times, time, side="left"))
            since = np.inf if before == 0 else (time - times[before - 1]) / DAY
            out.append(
                {
                    "game_id": str(game_id),
                    "side": side,
                    "team": team,
                    "days_rest": min(CAP_DAYS, float(since)),
                    "short_rest": bool(since <= SHORT_REST_DAYS),
                    "games_last_7d": before
                    - int(np.searchsorted(times, time - CAP_DAYS * DAY, side="left")),
                    "other_comp_prev": False,
                }
            )
    return validated(pd.DataFrame(out, columns=list(REST_SCHEMA.columns)), REST_SCHEMA)
