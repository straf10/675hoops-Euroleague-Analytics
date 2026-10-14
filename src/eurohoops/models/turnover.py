"""M5 retune roster turnover: player-minute continuity (not club-level continuity)."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
import pandera as pa

from eurohoops.models.elo import FloatArray
from eurohoops.models.m5 import ResidualFit
from eurohoops.models.minutes import _rated, _team_games, round_cutoffs
from eurohoops.parse.schemas import validated

CONTINUITY_SCHEMA = pa.DataFrameSchema(  # type: ignore[no-untyped-call]
    {
        "game_id": pa.Column(str),
        "c_home": pa.Column(float, checks=pa.Check.in_range(0.0, 1.0)),
        "c_away": pa.Column(float, checks=pa.Check.in_range(0.0, 1.0)),
    },
    strict=True,
    unique=["game_id"],
)


def roster_continuity(games: pd.DataFrame, player_games: pd.DataFrame) -> pd.DataFrame:
    """Per game, carry-over share of last season's team seconds (docs/models/m5.md addendum)."""
    ordered = games.sort_values("tipoff_utc").reset_index(drop=True)
    cutoffs = round_cutoffs(ordered)
    rated_pg = player_games[player_games["sec"] > 0].copy()
    rated_pg = rated_pg.merge(_rated(ordered)[["game_id", "season"]], on="game_id", how="inner")
    player_season = rated_pg.groupby(["season", "team", "player_id"], as_index=False)["sec"].sum()
    team_season = rated_pg.groupby(["season", "team"], as_index=False).agg(team_sec=("sec", "sum"))
    rows_by = {(str(g), str(t)): frame for (g, t), frame in rated_pg.groupby(["game_id", "team"])}
    team_game_rows = _team_games(ordered, player_games)
    by_team: dict[tuple[str, int], pd.DataFrame] = {}
    for (team, season), frame in team_game_rows.groupby(["team", "season"]):
        by_team[(str(team), cast(int, season))] = frame

    def c_for(team: str, season: int, cutoff: float) -> float:
        played = by_team.get((team, season))
        earlier = played[played["time"] < cutoff] if played is not None else None
        if earlier is None or earlier.empty:
            return 1.0
        prev = team_season[(team_season["team"] == team) & (team_season["season"] == season - 1)]
        if prev.empty or float(prev["team_sec"].iloc[0]) <= 0:
            return 1.0
        total_prev = float(prev["team_sec"].iloc[0])
        active: set[str] = set()
        for gid in earlier["game_id"]:
            frame = rows_by.get((str(gid), team))
            if frame is not None:
                active.update(frame["player_id"].astype(str))
        if not active:
            return 1.0
        carried = float(
            player_season[
                (player_season["team"] == team)
                & (player_season["season"] == season - 1)
                & (player_season["player_id"].astype(str).isin(active))
            ]["sec"].sum()
        )
        return min(1.0, max(0.0, carried / total_prev))

    out = []
    for game_id, season, home, away, cutoff in zip(
        ordered["game_id"],
        ordered["season"].astype(int),
        ordered["home"],
        ordered["away"],
        cutoffs,
        strict=True,
    ):
        out.append(
            {
                "game_id": str(game_id),
                "c_home": c_for(str(home), int(season), float(cutoff)),
                "c_away": c_for(str(away), int(season), float(cutoff)),
            }
        )
    return validated(pd.DataFrame(out), CONTINUITY_SCHEMA)


def mixed_team_adjustment(
    full: ResidualFit,
    season: ResidualFit,
    c_home: FloatArray,
    c_away: FloatArray,
    home_flag: FloatArray,
) -> FloatArray:
    """``h`` from ``full``; team residuals mixed per the retune addendum."""
    r_home = _mix_side(full.r_home, season.r_home, c_home)
    r_away = _mix_side(full.r_away, season.r_away, c_away)
    mixed: FloatArray = full.home * home_flag + r_home - r_away
    return mixed


def _mix_side(full: FloatArray, season: FloatArray, carry: FloatArray) -> FloatArray:
    fallback = np.where(np.isfinite(season), season, full)
    return carry * full + (1.0 - carry) * fallback
