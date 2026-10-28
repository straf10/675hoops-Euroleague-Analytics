"""Win Shares per EuroLeague player-season: Dean Oliver's method (*Basketball on Paper*, 2004),
as Basketball-Reference publishes it. Reference: datafield.dev, *Professional Basketball
Analytics*, part 3 chapter 13.

The chapter's formulas disagree in places (two versions each of the forced-miss weight, the
individual stops and the marginal defense). This module follows its section 13.12 derivation,
which is the version with the full defensive stop model. Where the chapter gives no value, the
constant is documented next to it below.

Offense, season totals per player (``OWS``):
  PProd = PProd_FG + PProd_AST + PProd_ORB, where
    PProd_FG  = 2 x unassisted 2FGM + 3 x unassisted 3FGM
                + AST_CREDIT x points of the assisted makes (an assisted make's points split
                between scorer and passer, AST_CREDIT each);
    PProd_AST = AST x league points per assisted FG x AST_CREDIT;
    PProd_ORB = ORB x team points per possession x ORB_WEIGHT.
  Possessions used = FGA + 0.44 x FTA + TOV - ORB.
  Marginal offense = PProd - 0.92 x league PPP x possessions used;
  OWS = marginal offense / points per win.

Defense, season totals per player (``DWS``), with the team's opponent totals:
  DFG% = opp FGM / opp FGA; DOR% = opp ORB / (opp ORB + team DRB);
  FMwt = DFG% (1 - DOR%) / (DFG% (1 - DOR%) + (1 - DFG%) DOR%);
  Stops1 = STL + BLK x FMwt x (1 - 1.07 DOR%) + DRB x (1 - FMwt)          (individual);
  Stops2 = MIN / team MIN x [(opp FGA - opp FGM - team BLK) x FMwt x (1 - 1.07 DOR%)
           + (opp TOV - team STL)] + PF / team PF x 0.4 x opp FTA x (1 - opp FT%)^2   (team share);
  Stop% = (Stops1 + Stops2) x team MIN / (team possessions x MIN);
  D points per scoring possession = opp PTS / (opp FGM + (1 - (1 - opp FT%)^2) x opp FTA x 0.4);
  DRtg = team DRtg + 0.2 x (100 x D points per scoring possession x (1 - Stop%) - team DRtg),
  team DRtg = 100 x opp PTS / team possessions;
  Marginal defense = MIN / team MIN x team possessions x (1.08 x league PPP - DRtg / 100);
  DWS = marginal defense / points per win.

Win Shares = OWS + DWS; WS/40 = WS / MIN x 40 (EuroLeague games are 40 minutes).

Season totals are summed over every box score of the season (the games the Players page uses);
rates (Stop%, DRtg, PPP) are computed once per team-season from those totals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandera.pandas as pa

from eurohoops.parse.schemas import validated
from eurohoops.stats.assists import AssistRow

# Points per win on EuroLeague regular seasons 2007-08..2025-26 (392 team-seasons): the inverse of
# the slope of win % on point differential per game, fitted by ``fit_points_per_win``
# (re-derived by scripts/fit_points_per_win.py). 35.50, 95% CI 33.92 to 37.11. Replaces the
# NBA's 0.32 x league PPG.
POINTS_PER_WIN = 35.50
# Offensive-rebound weight in PProd_ORB. The chapter gives no value; its worked example uses 1.2.
ORB_WEIGHT = 1.2
# Share of an assisted basket's points credited to the passer (PProd_AST) and the scorer (PProd_FG)
AST_CREDIT = 0.5
FTA_POSSESSION = 0.44  # FTA weight in possessions used
FTA_SCORING = 0.4  # FTA weight in scoring possessions
OFFENSE_REPLACEMENT = 0.92  # x league PPP x possessions used
DEFENSE_REPLACEMENT = 1.08  # x league PPP x team possessions
DRTG_SHARE = 0.2  # weight of the stop-based term in an individual DRtg
DOR_STOP_WEIGHT = 1.07  # (1 - 1.07 DOR%) in the blocked-shot and missed-shot stops
MINUTES_PER_GAME = 40  # EuroLeague regulation game, for WS/40

TEAM_COLS = [
    "pts",
    "fg2m",
    "fg2a",
    "fg3m",
    "fg3a",
    "ftm",
    "fta",
    "oreb",
    "dreb",
    "tov",
    "stl",
    "blk",
    "poss",
    "won",
]
PLAYER_COLS = [
    "sec",
    "pf",
    "fg2m",
    "fg2a",
    "fg3m",
    "fg3a",
    "fta",
    "oreb",
    "dreb",
    "ast",
    "stl",
    "blk",
    "tov",
]


@dataclass(frozen=True)
class PointsPerWin:
    """Points per win with a 95% bootstrap interval, and the regression behind it."""

    value: float
    low: float
    high: float
    slope: float  # win % per point of differential per game
    intercept: float
    teams: int


def fit_points_per_win(
    team_seasons: pd.DataFrame, resamples: int = 10_000, seed: int = 0
) -> PointsPerWin:
    """Points per win from regular-season team-seasons (``games``, ``wins``, ``pf``, ``pa``).

    Regresses win % on point differential per game (OLS with intercept). A win is worth 1 / slope
    points of differential over a season: wins - games / 2 = games x slope x diff per game, and
    total differential = games x diff per game. The interval resamples team-seasons
    (``resamples``, with a seeded generator).
    """
    games = team_seasons["games"].to_numpy(dtype=float)
    diff = (team_seasons["pf"] - team_seasons["pa"]).to_numpy(dtype=float) / games
    win_pct = team_seasons["wins"].to_numpy(dtype=float) / games
    slope, intercept = np.polyfit(diff, win_pct, 1)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(diff), size=(resamples, len(diff)))
    x, y = diff[picks], win_pct[picks]
    var_x = (x * x).mean(axis=1) - x.mean(axis=1) ** 2
    cov_xy = (x * y).mean(axis=1) - x.mean(axis=1) * y.mean(axis=1)
    boot = 1.0 / (cov_xy / var_x)
    boot = boot[np.isfinite(boot) & (boot > 0)]
    low, high = np.percentile(boot, [2.5, 97.5])
    return PointsPerWin(
        value=float(1.0 / slope),
        low=float(low),
        high=float(high),
        slope=float(slope),
        intercept=float(intercept),
        teams=len(diff),
    )


def team_seasons_regular(games: pd.DataFrame) -> pd.DataFrame:
    """Regular-season team-seasons from a games table: season, team, games, wins, pf, pa.

    Only played, non-forfeit regular-season games (phase ``RS``) count.
    """
    rs = games[games["played"] & ~games["forfeit"] & (games["phase"] == "RS")]
    home = rs.assign(
        team=rs["home"],
        pf=rs["home_score"],
        pa=rs["away_score"],
        won=rs["home_score"] > rs["away_score"],
    )
    away = rs.assign(
        team=rs["away"],
        pf=rs["away_score"],
        pa=rs["home_score"],
        won=rs["away_score"] > rs["home_score"],
    )
    both = pd.concat([home, away])
    return (
        both.groupby(["season", "team"])
        .agg(games=("game_id", "count"), wins=("won", "sum"), pf=("pf", "sum"), pa=("pa", "sum"))
        .reset_index()
    )


def assisted_fg(
    assists: Mapping[str, Sequence[AssistRow]], seasons: Mapping[str, int]
) -> pd.DataFrame:
    """Assisted made field goals per scorer: season, team, player_id, a2 (2-pointers), a3 (3s).

    Uses the field-goal links of ``stats/assists.py`` (``tier`` ``fg``, or None for a field goal);
    free-throw links are not field goals and are left out.
    """
    rows = [
        (seasons[gid], r.team, r.scorer, r.points)
        for gid, linked in assists.items()
        for r in linked
        if r.scorer is not None and (r.tier or "fg") == "fg" and r.points in (2, 3)
    ]
    frame = pd.DataFrame(rows, columns=["season", "team", "player_id", "points"])
    frame["a2"] = (frame["points"] == 2).astype(int)
    frame["a3"] = (frame["points"] == 3).astype(int)
    return frame.groupby(["season", "team", "player_id"], as_index=False)[["a2", "a3"]].sum()


def forced_miss_weight(dfg: pd.Series | float, dor: pd.Series | float) -> pd.Series | float:
    """FMwt: the share of the opponents' missed shots that the defence turns into stops."""
    return dfg * (1 - dor) / (dfg * (1 - dor) + (1 - dfg) * dor)


def offense_possessions(
    fga: pd.Series | float, fta: pd.Series | float, tov: pd.Series | float, orb: pd.Series | float
) -> pd.Series | float:
    """Possessions used: FGA + 0.44 FTA + TOV - ORB."""
    return fga + FTA_POSSESSION * fta + tov - orb


def points_produced(
    unassisted: pd.Series | float,
    assisted_points: pd.Series | float,
    *,
    ast: pd.Series | float,
    league_points_per_assist: pd.Series | float,
    orb: pd.Series | float,
    team_ppp: pd.Series | float,
) -> pd.Series | float:
    """PProd = PProd_FG + PProd_AST + PProd_ORB (see the module docstring).

    ``unassisted`` is the unassisted made-shot points (2 and 3 each); ``assisted_points`` the
    points of his assisted makes.
    """
    prod_fg = unassisted + AST_CREDIT * assisted_points
    prod_ast = ast * league_points_per_assist * AST_CREDIT
    prod_orb = orb * team_ppp * ORB_WEIGHT
    return prod_fg + prod_ast + prod_orb


def marginal_offense(
    pprod: pd.Series | float, league_ppp: pd.Series | float, poss_used: pd.Series | float
) -> pd.Series | float:
    """Points produced above a replacement player's (0.92 x league PPP per possession used)."""
    return pprod - OFFENSE_REPLACEMENT * league_ppp * poss_used


def stop_percentage(
    stops: pd.Series | float,
    team_minutes: pd.Series | float,
    team_poss: pd.Series | float,
    minutes: pd.Series | float,
) -> pd.Series | float:
    """Stop% = stops x team minutes / (team possessions x minutes)."""
    return stops * team_minutes / (team_poss * minutes)


def individual_drtg(
    team_drtg: pd.Series | float,
    d_points_per_scoring_poss: pd.Series | float,
    stop_pct: pd.Series | float,
) -> pd.Series | float:
    """DRtg = team DRtg + 0.2 (100 x D points per scoring possession x (1 - Stop%) - team DRtg)."""
    return team_drtg + DRTG_SHARE * (100 * d_points_per_scoring_poss * (1 - stop_pct) - team_drtg)


def marginal_defense(
    minutes: pd.Series | float,
    team_minutes: pd.Series | float,
    team_poss: pd.Series | float,
    league_ppp: pd.Series | float,
    drtg: pd.Series | float,
) -> pd.Series | float:
    """MIN / team MIN x team possessions x (1.08 x league PPP - DRtg / 100)."""
    return (minutes / team_minutes) * team_poss * (DEFENSE_REPLACEMENT * league_ppp - drtg / 100)


def _team_seasons(teams: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """One row per team-season: own totals (``TEAM_COLS``), opponent totals (``opp_`` prefix),
    team minutes in seconds (``mp``) and team fouls (``pf``)."""
    other = teams[["game_id", "team", *TEAM_COLS]].rename(
        columns={"team": "opponent", **{c: f"opp_{c}" for c in TEAM_COLS}}
    )
    games = teams.merge(other, on=["game_id", "opponent"], validate="one_to_one")
    opp_cols = [f"opp_{c}" for c in TEAM_COLS]
    totals = games.groupby(["season", "team"])[[*TEAM_COLS, *opp_cols]].sum()
    totals["mp"] = players.groupby(["season", "team"])["sec"].sum()
    totals["pf"] = players.groupby(["season", "team"])["pf"].sum()
    return totals.reset_index()


def win_shares(
    players: pd.DataFrame,
    teams: pd.DataFrame,
    assisted: pd.DataFrame,
    points_per_win: float = POINTS_PER_WIN,
) -> pd.DataFrame:
    """Win Shares per player, season and team: OWS, DWS, WS, WS/40 (``stats.box.BoxGames`` tables
    ``players`` and ``teams``; ``assisted`` from :func:`assisted_fg`).

    Every row of ``players`` must have ``sec`` > 0 (a player who was on the court). Team sums come
    from the same box scores, so a team's WS sums to its wins only up to the stats model.
    """
    ts = _team_seasons(teams, players)
    ts["fgm"] = ts["fg2m"] + ts["fg3m"]
    ts["fga"] = ts["fg2a"] + ts["fg3a"]
    ts["opp_fgm"] = ts["opp_fg2m"] + ts["opp_fg3m"]
    ts["opp_fga"] = ts["opp_fg2a"] + ts["opp_fg3a"]
    ts["team_ppp"] = ts["pts"] / ts["poss"]
    league = ts.groupby("season")[["pts", "poss"]].sum()
    lg_ppp = (league["pts"] / league["poss"]).rename("lg_ppp")
    ts = ts.merge(lg_ppp, left_on="season", right_index=True)
    ts["dfg"] = ts["opp_fgm"] / ts["opp_fga"]
    ts["dor"] = ts["opp_oreb"] / (ts["opp_oreb"] + ts["dreb"])
    ts["fmwt"] = forced_miss_weight(ts["dfg"], ts["dor"])
    ts["stops2_team"] = (ts["opp_fga"] - ts["opp_fgm"] - ts["blk"]) * ts["fmwt"] * (
        1 - DOR_STOP_WEIGHT * ts["dor"]
    ) + (ts["opp_tov"] - ts["stl"])
    opp_ft = ts["opp_ftm"] / ts["opp_fta"]
    ts["foul_stops_team"] = FTA_SCORING * ts["opp_fta"] * (1 - opp_ft) ** 2
    ts["d_pps"] = ts["opp_pts"] / (
        ts["opp_fgm"] + (1 - (1 - opp_ft) ** 2) * ts["opp_fta"] * FTA_SCORING
    )
    ts["team_drtg"] = 100 * ts["opp_pts"] / ts["poss"]

    assists = assisted.groupby("season")[["a2", "a3"]].sum()
    assists["points"] = 2 * assists["a2"] + 3 * assists["a3"]
    assists["count"] = assists["a2"] + assists["a3"]
    per_assist = (assists["points"] / assists["count"]).rename("pts_per_assist")

    pl = players.groupby(["season", "team", "player_id"], as_index=False).agg(
        player=("player", "last"),
        **{c: (c, "sum") for c in PLAYER_COLS},
    )
    pl = pl.merge(assisted, on=["season", "team", "player_id"], how="left").fillna(
        {"a2": 0, "a3": 0}
    )
    pl = pl.merge(ts, on=["season", "team"], validate="many_to_one", suffixes=("", "_tm"))
    pl = pl.merge(per_assist, left_on="season", right_index=True)
    pl["fga"] = pl["fg2a"] + pl["fg3a"]  # the player's, not the team column merged above

    unassisted = 2 * (pl["fg2m"] - pl["a2"]) + 3 * (pl["fg3m"] - pl["a3"])
    assisted_points = 2 * pl["a2"] + 3 * pl["a3"]
    pprod = points_produced(
        unassisted,
        assisted_points,
        ast=pl["ast"],
        league_points_per_assist=pl["pts_per_assist"],
        orb=pl["oreb"],
        team_ppp=pl["team_ppp"],
    )
    pl["points_produced"] = pprod
    used = offense_possessions(pl["fga"], pl["fta"], pl["tov"], pl["oreb"])
    pl["ows"] = marginal_offense(pprod, pl["lg_ppp"], used) / points_per_win

    stops1 = (
        pl["stl"]
        + pl["blk"] * pl["fmwt"] * (1 - DOR_STOP_WEIGHT * pl["dor"])
        + pl["dreb"] * (1 - pl["fmwt"])
    )
    stops2 = (pl["sec"] / pl["mp"]) * pl["stops2_team"] + (pl["pf"] / pl["pf_tm"]) * pl[
        "foul_stops_team"
    ]
    stop = stop_percentage(stops1 + stops2, pl["mp"], pl["poss"], pl["sec"])
    drtg = individual_drtg(pl["team_drtg"], pl["d_pps"], stop)
    pl["dws"] = (
        marginal_defense(pl["sec"], pl["mp"], pl["poss"], pl["lg_ppp"], drtg) / points_per_win
    )

    pl["ws"] = pl["ows"] + pl["dws"]
    pl["minutes"] = pl["sec"] / 60
    pl["ws40"] = pl["ws"] / pl["minutes"] * MINUTES_PER_GAME
    return pl[
        [
            "season",
            "team",
            "player_id",
            "player",
            "minutes",
            "points_produced",
            "ows",
            "dws",
            "ws",
            "ws40",
        ]
    ].reset_index(drop=True)


def team_check(ws: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Per season: the correlation of each team's summed player WS with its wins, and the mean
    absolute error of that sum (wins over the same games, from the team box rows)."""
    summed = ws.groupby(["season", "team"], as_index=False)["ws"].sum()
    wins = teams.groupby(["season", "team"], as_index=False)["won"].sum()
    both = summed.merge(wins, on=["season", "team"], validate="one_to_one")
    rows = []
    for season, group in both.groupby("season"):
        rows.append(
            {
                "season": int(season),
                "teams": len(group),
                "correlation": float(np.corrcoef(group["ws"], group["won"])[0, 1]),
                "mae": float((group["ws"] - group["won"]).abs().mean()),
                "ws_total": float(group["ws"].sum()),
                "wins_total": int(group["won"].sum()),
            }
        )
    return pd.DataFrame(rows)


WS_FIELDS = ("ows", "dws", "ws", "ws40")
WIN_SHARES_SCHEMA = pa.DataFrameSchema(
    {
        "season": pa.Column("int64"),
        "team": pa.Column(str),
        "player_id": pa.Column(str),
        "player": pa.Column(str),
        "minutes": pa.Column("float64", pa.Check.gt(0)),
        "points_produced": pa.Column("float64"),
        "ows": pa.Column("float64"),
        "dws": pa.Column("float64"),
        "ws": pa.Column("float64"),
        "ws40": pa.Column("float64"),
    },
    unique=["season", "team", "player_id"],
    strict=True,
)


def box_win_shares(
    players: pd.DataFrame,
    teams: pd.DataFrame,
    assists: Mapping[str, Sequence[AssistRow]],
    seasons: Mapping[str, int],
) -> pd.DataFrame:
    """Win Shares of every player who was on court in the box scores (``WIN_SHARES_SCHEMA``).

    ``assists`` is the play-by-play assist rows per game id and ``seasons`` the season per game id
    (both from the games table); the assisted field goals come from them.
    """
    on_court = players[players["sec"] > 0]
    return validated(win_shares(on_court, teams, assisted_fg(assists, seasons)), WIN_SHARES_SCHEMA)
