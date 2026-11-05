"""Team factors (``team_factors``)
-------------------------------
Per season, from the team's box-score sums: eFG% = (fg2m + 1.5 fg3m) / fga, TOV% = tov / poss,
ORB% = oreb / (oreb + opponent dreb), FT rate = fta / fga. The sums are the cached box scores'
team totals rows. Schedule strength is the mean opponent rating over the team's
scheduled games of the season (played and remaining), the rating being Elo as published (the
live backtest's frozen parameters, replayed from its first warm-up season) at the end of the
replay through that season. An input that is missing gives ``value: null`` and a ``reason``.
"""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import pandera.pandas as pa

from eurohoops.api.read.store import NotFound, Store, cached
from eurohoops.config import (
    LIVE_SEASON,
    Competition,
)
from eurohoops.models.elo import win_probability
from eurohoops.models.rest import rest_features
from eurohoops.parse.schemas import validated

TEAM_LINES_SCHEMA = pa.DataFrameSchema(
    {
        "season": pa.Column("int64"),
        "game_id": pa.Column(str),
        "team": pa.Column(str),
        "opponent": pa.Column(str),
        **{
            c: pa.Column("int64", pa.Check.ge(0))
            for c in ("fg2m", "fg3m", "fga", "fta", "oreb", "dreb", "tov")
        },
        "poss": pa.Column("float64", pa.Check.gt(0.0)),
    },
    strict=True,
)


def _known_team(store: Store, comp: Competition, code: str) -> dict[str, str]:
    games = store.games(comp)
    if code not in {*games["home"], *games["away"]}:
        raise NotFound(f"unknown team '{code}' in {comp.name}")
    return store.team(comp, code)


def team_ratings(store: Store, competition: str, team: str) -> dict[str, Any]:
    """The team's published Elo (as ``site.json`` lists it): rating, change since the season's
    start and rank among the live season's teams. M1's strengths are not published."""
    comp = store.competition(competition)
    info = _known_team(store, comp, team)
    table = store.elo(comp, LIVE_SEASON)
    if team not in table:
        raise NotFound(f"'{team}' has no game in the {comp.name} {LIVE_SEASON} season")
    order = sorted(table, key=lambda t: (-round(table[t][0], 1), t))
    rating, start = table[team]
    return {
        "competition": comp.name,
        "team": info,
        "season": LIVE_SEASON,
        "elo": {
            "rating": round(rating, 1),
            "change": round(rating - start, 1),
            "rank": order.index(team) + 1,
            "teams": len(order),
        },
        "m1": {
            "available": False,
            "reason": "M1's team strengths are not published; its forecasts are under "
            "/predictions/{game_id}",
        },
    }


@cached
def _team_lines(store: Store, comp: Competition) -> tuple[pd.DataFrame | None, str]:
    """Team box lines (``TEAM_LINES_SCHEMA``) of the EuroLeague, or None and why not."""
    teams = store.euroleague_box().teams
    lines = teams.assign(fga=teams["fg2a"] + teams["fg3a"])
    return validated(lines[list(TEAM_LINES_SCHEMA.columns)], TEAM_LINES_SCHEMA), ""


def _factor(numerator: float, denominator: float, what: str) -> dict[str, Any]:
    if denominator <= 0:
        return {"value": None, "reason": f"no {what} in the season"}
    return {"value": float(numerator) / float(denominator), "reason": None}


def _unavailable(reason: str) -> dict[str, Any]:
    return {"value": None, "reason": reason}


def _four_factors(lines: pd.DataFrame, team: str, season: int) -> dict[str, Any]:
    season_lines = lines[lines["season"] == season]
    mine = season_lines[season_lines["team"] == team]
    opponents = season_lines[["game_id", "team", "dreb"]].rename(
        columns={"team": "opponent", "dreb": "opp_dreb"}
    )
    paired = mine.merge(opponents, on=["game_id", "opponent"], how="left")
    sums = paired[["fg2m", "fg3m", "fga", "fta", "oreb", "tov", "poss", "opp_dreb"]].sum()
    orb = (
        _unavailable("an opponent's box line is missing for one of the games")
        if paired["opp_dreb"].isna().any()
        else _factor(sums["oreb"], sums["oreb"] + sums["opp_dreb"], "rebounds available")
    )
    return {
        "games": len(paired),
        "factors": {
            "efg_pct": _factor(
                sums["fg2m"] + 1.5 * sums["fg3m"], sums["fga"], "field-goal attempt"
            ),
            "tov_pct": _factor(sums["tov"], sums["poss"], "possession"),
            "orb_pct": orb,
            "ft_rate": _factor(sums["fta"], sums["fga"], "field-goal attempt"),
        },
    }


SCHEDULE_NEXT = 5


SCHEDULE_RATING = (
    "Elo as published, end of the replay through the season. Each opponent is venue-adjusted: "
    "its rating minus the home-court advantage when the team is at home, plus it when away. "
    "The average team is the mean rating of the season's clubs, at the same venue as the team."
)


@cached
def schedule_rest(store: Store, comp: Competition) -> dict[tuple[str, str], float]:
    """Days of rest (``rest.py``) of each side of every game in the competition's mart, keyed by
    (game id, source code).

    The schedule counts as history here (every row is treated as played), so a fixture's rest is
    the days since the previous fixture, whether or not that game has been played yet."""
    long = rest_features(store.games(comp).assign(played=True))
    return {
        (str(g), str(t)): float(d)
        for g, t, d in zip(long["game_id"], long["team"], long["days_rest"], strict=True)
    }


def strength_block(
    games: pd.DataFrame,
    team: str,
    ratings: Mapping[str, tuple[float, float]],
    hca: float,
    rest: Mapping[tuple[str, str], float],
) -> dict[str, Any]:
    """Opponent strength of ``team`` over ``games`` (its rows, in tip-off order, not empty)."""
    at_home = games["home"].eq(team).to_numpy()
    opponents = [str(o) for o in np.where(at_home, games["away"], games["home"])]
    rating = np.array([ratings[o][0] for o in opponents], dtype=float)
    adjusted = rating - np.where(at_home, 1.0, -1.0) * hca
    average = float(np.mean([r for r, _ in ratings.values()]))
    game_ids = [str(g) for g in games["game_id"]]
    return {
        "games": len(games),
        "home": int(at_home.sum()),
        "away": int((~at_home).sum()),
        "mean_opponent_elo": float(rating.mean()),
        "mean_opponent_elo_adjusted": float(adjusted.mean()),
        "average_team_win_pct": float(np.mean([win_probability(average - a) for a in adjusted])),
        "rest_days": float(np.mean([rest[(g, team)] for g in game_ids])),
        "opponent_rest_days": float(
            np.mean([rest[(g, o)] for g, o in zip(game_ids, opponents, strict=True)])
        ),
        "reason": None,
    }


def _schedule_strength(store: Store, comp: Competition, team: str, season: int) -> dict[str, Any]:
    """The team's opponents in ``season``: the games played so far, the games left, and the next
    few (``SCHEDULE_NEXT``). Each block is empty, with a reason, when it has no games."""
    out: dict[str, Any] = {"rating": SCHEDULE_RATING, "next": SCHEDULE_NEXT}
    try:
        ratings = store.elo(comp, season)
        hca = store.live_model(comp).params.hca
        games = store.games(comp)
        rest = schedule_rest(store, comp)
    except NotFound as missing:
        empty = {"games": 0, "reason": missing.reason}
        return {**out, "played": empty, "remaining": empty, "next5": empty}
    mine = games[(games["season"] == season) & ((games["home"] == team) | (games["away"] == team))]
    mine = mine.sort_values("tipoff_utc", kind="stable")
    done = mine[mine["played"].astype(bool)]
    left = mine[~mine["played"].astype(bool)]

    def block(frame: pd.DataFrame, reason: str) -> dict[str, Any]:
        if mine.empty:
            return {"games": 0, "reason": f"no scheduled games in {season}"}
        if frame.empty:
            return {"games": 0, "reason": reason}
        return strength_block(frame, team, ratings, hca, rest)

    return {
        **out,
        "played": block(done, "no games played yet"),
        "remaining": block(left, "no games left to play"),
        "next5": block(left.head(SCHEDULE_NEXT), "no games left to play"),
    }


def team_factors(store: Store, competition: str, team: str, season: int | None) -> dict[str, Any]:
    """The four factors and schedule strength of a team's season (latest with box scores when
    ``season`` is None); a missing input gives ``value: null`` and a ``reason``."""
    comp = store.competition(competition)
    info = _known_team(store, comp, team)
    lines, why = _team_lines(store, comp)
    own = None if lines is None else lines[lines["team"] == team]
    seasons = [] if own is None else sorted(int(s) for s in own["season"].unique())
    chosen = season if season is not None else (seasons[-1] if seasons else LIVE_SEASON)
    if own is None or chosen not in seasons:
        reason = why or f"no box-score games for '{team}' in {chosen}"
        factors = {
            name: _unavailable(reason) for name in ("efg_pct", "tov_pct", "orb_pct", "ft_rate")
        }
        box: dict[str, Any] = {"games": 0, "factors": factors}
    else:
        assert lines is not None
        box = _four_factors(lines, team, chosen)
    return {
        "competition": comp.name,
        "team": info,
        "season": chosen,
        "available_seasons": seasons,
        **box,
        "schedule_strength": _schedule_strength(store, comp, team, chosen),
    }
