"""Win Shares per EuroLeague player-season, following Basketball-Reference's implementation of
Dean Oliver's method (*Basketball on Paper*, 2004):

- Win Shares: https://www.basketball-reference.com/about/ws.html
- Individual ratings (Points Produced, scoring possessions, Stop%, DRtg):
  https://www.basketball-reference.com/about/ratings.html

Offense, season totals per player (OWS). Team terms are per team-season:
  Team_Scoring_Poss = Team_FGM + (1 - (1 - Team_FT%)^2) x Team_FTA x 0.4
  Team_Play%        = Team_Scoring_Poss / (Team_FGA + 0.4 x Team_FTA + Team_TOV)
  Team_ORB%         = Team_ORB / (Team_ORB + Opp_DRB)
  Team_ORB_Weight   = ((1 - Team_ORB%) x Team_Play%)
                      / ((1 - Team_ORB%) x Team_Play% + Team_ORB% x (1 - Team_Play%))
  qAST = (MP / (Team_MP / 5)) x 1.14 x ((Team_AST - AST) / Team_FGM)
         + [((Team_AST / Team_MP) x MP x 5 - AST) / ((Team_FGM / Team_MP) x MP x 5 - FGM)]
           x (1 - MP / (Team_MP / 5))
  FG_Part  = FGM x (1 - 0.5 x ((PTS - FTM) / (2 x FGA)) x qAST)
  AST_Part = 0.5 x (((Team_PTS - Team_FTM) - (PTS - FTM)) / (2 x (Team_FGA - FGA))) x AST
  FT_Part  = (1 - (1 - FT%)^2) x 0.4 x FTA
  ORB_Part = ORB x Team_ORB_Weight x Team_Play%
  ScPoss   = (FG_Part + AST_Part + FT_Part) x (1 - (Team_ORB / Team_Scoring_Poss) x Team_ORB_Weight
             x Team_Play%) + ORB_Part
  PProd_FG_Part  = 2 x (FGM + 0.5 x 3PM) x (1 - 0.5 x ((PTS - FTM) / (2 x FGA)) x qAST)
  PProd_AST_Part = 2 x ((Team_FGM - FGM + 0.5 x (Team_3PM - 3PM)) / (Team_FGM - FGM)) x 0.5
                   x (((Team_PTS - Team_FTM) - (PTS - FTM)) / (2 x (Team_FGA - FGA))) x AST
  PProd_ORB_Part = ORB x Team_ORB_Weight x Team_Play% x (Team_PTS / Team_Scoring_Poss)
  PProd    = (PProd_FG_Part + PProd_AST_Part + FTM)
             x (1 - (Team_ORB / Team_Scoring_Poss) x Team_ORB_Weight x Team_Play%)
             + PProd_ORB_Part
  FGxPoss  = (FGA - FGM) x (1 - 1.07 x Team_ORB%)
  FTxPoss  = (1 - FT%)^2 x 0.4 x FTA
  Possessions used = ScPoss + FGxPoss + FTxPoss + TOV
  Marginal offense = PProd - 0.92 x league PPP x possessions used
  OWS = marginal offense / points per win

Defense, season totals per player (DWS), with the team's opponent totals:
  DFG% = Opp_FGM / Opp_FGA; DOR% = Opp_ORB / (Opp_ORB + Team_DRB);
  FMwt = DFG% (1 - DOR%) / (DFG% (1 - DOR%) + (1 - DFG%) DOR%);
  Stops1 = STL + BLK x FMwt x (1 - 1.07 DOR%) + DRB x (1 - FMwt)           (player);
  Stops2 = (((Opp_FGA - Opp_FGM - Team_BLK) / Team_MP) x FMwt x (1 - 1.07 DOR%)
            + (Opp_TOV - Team_STL) / Team_MP) x MP
           + (PF / Team_PF) x 0.4 x Opp_FTA x (1 - Opp_FT%)^2;
  Stops = Stops1 + Stops2;  Stop% = Stops x Team_MP / (Team_Poss x MP);
  D_Pts_per_ScPoss = Opp_PTS / (Opp_FGM + (1 - (1 - Opp_FT%)^2) x Opp_FTA x 0.4);
  Team DRtg = 100 x Opp_PTS / Team_Poss;
  DRtg = Team DRtg + 0.2 x (100 x D_Pts_per_ScPoss x (1 - Stop%) - Team DRtg);
  Marginal defense = MP / Team_MP x Team_Poss x (1.08 x league PPP - DRtg / 100);
  DWS = marginal defense / points per win.

Points per win (ws.html): 0.32 x league PPG x (team pace / league pace), per team-season, where
PPG and pace are per team-game. With this constant the league's WS sums to its wins, because
the replacement levels 0.92 and 1.08 leave 0.16 x points scored in marginal points per season.

Win Shares = OWS + DWS; WS/40 = WS / MIN x 40 (EuroLeague games are 40 minutes).

Season totals are summed over every box score of the season (the games the Players page uses).
Rates (Stop%, DRtg, PPP, pace) are computed once per team-season from those totals.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandera.pandas as pa

from eurohoops.parse.schemas import validated

PPW_FACTOR = 0.32  # points per win = PPW_FACTOR x league PPG x (team pace / league pace)
OFFENSE_REPLACEMENT = 0.92  # x league PPP x possessions used
DEFENSE_REPLACEMENT = 1.08  # x league PPP x team possessions
FT_SCORING = 0.4  # FTA weight in scoring possessions and in FT_Part
FTA_POSSESSION = 0.4  # FTA weight in the team play rate and FTxPoss
DOR_STOP_WEIGHT = 1.07  # (1 - 1.07 DOR%) in FGxPoss, Stops1 and Stops2
QAST_WEIGHT = 1.14  # qAST's first term
DRTG_SHARE = 0.2  # weight of the stop-based term in an individual DRtg
MINUTES_PER_GAME = 40  # EuroLeague regulation game, for WS/40

# Team-season sums needed from the box scores (own totals, then the opponent's: opp_ prefix).
COUNT_COLS = [
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
    "ast",
    "poss",
]
# Player season sums (player box lines).
PLAYER_COLS = [
    "sec",
    "pf",
    "pts",
    "fg2m",
    "fg2a",
    "fg3m",
    "fg3a",
    "ftm",
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

    A comparison only: the module uses the Basketball-Reference definition. Regresses win % on
    point differential per game (OLS with intercept). A win is worth 1 / slope points of
    differential over a season: wins - games / 2 = games x slope x diff per game, and total
    differential = games x diff per game. The interval resamples team-seasons (``resamples``, with a
    seeded generator).
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


def scoring_possessions(
    fgm: pd.Series | float, ft_pct: pd.Series | float, fta: pd.Series | float
) -> pd.Series | float:
    """Scoring possessions: FGM + (1 - (1 - FT%)^2) x FTA x 0.4 (team or player)."""
    return fgm + (1 - (1 - ft_pct) ** 2) * fta * FT_SCORING


def team_play_pct(
    scoring: pd.Series | float,
    fga: pd.Series | float,
    fta: pd.Series | float,
    tov: pd.Series | float,
) -> pd.Series | float:
    """Team_Play% = Team_Scoring_Poss / (Team_FGA + 0.4 x Team_FTA + Team_TOV)."""
    return scoring / (fga + FTA_POSSESSION * fta + tov)


def team_orb_pct(orb: pd.Series | float, opp_drb: pd.Series | float) -> pd.Series | float:
    """Team_ORB% = Team_ORB / (Team_ORB + Opp_DRB)."""
    return orb / (orb + opp_drb)


def team_orb_weight(orb_pct: pd.Series | float, play_pct: pd.Series | float) -> pd.Series | float:
    """Team_ORB_Weight: the share of an offensive rebound's possession worth a full possession."""
    return ((1 - orb_pct) * play_pct) / ((1 - orb_pct) * play_pct + orb_pct * (1 - play_pct))


def points_per_win(
    league_ppg: pd.Series | float, pace: pd.Series | float, league_pace: pd.Series | float
) -> pd.Series | float:
    """Points per win: 0.32 x league PPG x (team pace / league pace), per team-game."""
    return PPW_FACTOR * league_ppg * (pace / league_pace)


def qast(
    *,
    sec: pd.Series | float,
    team_sec: pd.Series | float,
    ast: pd.Series | float,
    fgm: pd.Series | float,
    team_ast: pd.Series | float,
    team_fgm: pd.Series | float,
) -> pd.Series | float:
    """qAST: the share of the player's made field goals that were assisted, from his minutes and
    his team's assists and made field goals (Basketball-Reference). Times are seconds."""
    per_five = team_sec / 5
    first = (sec / per_five) * (QAST_WEIGHT * ((team_ast - ast) / team_fgm))
    second = (((team_ast / team_sec) * sec * 5 - ast) / ((team_fgm / team_sec) * sec * 5 - fgm)) * (
        1 - sec / per_five
    )
    return first + second


def points_produced(
    *,
    fgm: pd.Series | float,
    fg3m: pd.Series | float,
    pts: pd.Series | float,
    ftm: pd.Series | float,
    fga: pd.Series | float,
    qast_value: pd.Series | float,
    fg_share: pd.Series | float,
    ast: pd.Series | float,
    team_fgm: pd.Series | float,
    team_fg3m: pd.Series | float,
    team_pts: pd.Series | float,
    team_ftm: pd.Series | float,
    team_fga: pd.Series | float,
    oreb: pd.Series | float,
    team_orb_factor: pd.Series | float,
    orb_weight_play: pd.Series | float,
    team_ppp_scoring: pd.Series | float,
) -> pd.Series | float:
    """PProd (Basketball-Reference, see the module docstring).

    ``team_orb_factor`` = Team_ORB / Team_Scoring_Poss x Team_ORB_Weight x Team_Play%;
    ``orb_weight_play`` = Team_ORB_Weight x Team_Play%; ``team_ppp_scoring`` = Team_PTS /
    Team_Scoring_Poss."""
    fg_part = 2 * (fgm + 0.5 * fg3m) * (1 - 0.5 * fg_share * qast_value)
    ast_part = (
        2
        * ((team_fgm - fgm + 0.5 * (team_fg3m - fg3m)) / (team_fgm - fgm))
        * 0.5
        * (((team_pts - team_ftm) - (pts - ftm)) / (2 * (team_fga - fga)))
        * ast
    )
    orb_part = oreb * orb_weight_play * team_ppp_scoring
    return (fg_part + ast_part + ftm) * (1 - team_orb_factor) + orb_part


def scoring_possessions_player(
    *,
    fgm: pd.Series | float,
    fga: pd.Series | float,
    pts: pd.Series | float,
    ftm: pd.Series | float,
    fta: pd.Series | float,
    ft_pct: pd.Series | float,
    qast_value: pd.Series | float,
    fg_share: pd.Series | float,
    ast: pd.Series | float,
    team_pts: pd.Series | float,
    team_ftm: pd.Series | float,
    team_fga: pd.Series | float,
    oreb: pd.Series | float,
    team_orb_factor: pd.Series | float,
    orb_weight_play: pd.Series | float,
) -> pd.Series | float:
    """ScPoss (Basketball-Reference): the player's scoring possessions (module docstring)."""
    fg_part = fgm * (1 - 0.5 * fg_share * qast_value)
    ast_part = 0.5 * (((team_pts - team_ftm) - (pts - ftm)) / (2 * (team_fga - fga))) * ast
    ft_part = (1 - (1 - ft_pct) ** 2) * FT_SCORING * fta
    orb_part = oreb * orb_weight_play
    return (fg_part + ast_part + ft_part) * (1 - team_orb_factor) + orb_part


def possessions_used(
    *,
    scoring: pd.Series | float,
    fga: pd.Series | float,
    fgm: pd.Series | float,
    team_orb_pct_value: pd.Series | float,
    ft_pct: pd.Series | float,
    fta: pd.Series | float,
    tov: pd.Series | float,
) -> pd.Series | float:
    """TotPoss = ScPoss + FGxPoss + FTxPoss + TOV, FGxPoss = (FGA - FGM)(1 - 1.07 Team_ORB%),
    FTxPoss = (1 - FT%)^2 x 0.4 x FTA."""
    fgx = (fga - fgm) * (1 - DOR_STOP_WEIGHT * team_orb_pct_value)
    ftx = (1 - ft_pct) ** 2 * FTA_POSSESSION * fta
    return scoring + fgx + ftx + tov


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


def _div(num: pd.Series, den: pd.Series) -> pd.Series:
    """num / den, with 0 where the denominator is 0 (a player with no attempts of that kind)."""
    out = num / den
    return out.where(np.isfinite(out), 0.0)


def _team_seasons(teams: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """One row per team-season: own sums (``tm_`` prefix), the opponents' sums (``opp_``), games
    (``tm_games``), team minutes in seconds (``tm_mp``) and team fouls (``tm_pf``)."""
    other = teams[["game_id", "team", *COUNT_COLS]].rename(
        columns={"team": "opponent", **{c: f"opp_{c}" for c in COUNT_COLS}}
    )
    games = teams.merge(other, on=["game_id", "opponent"], validate="one_to_one")
    sums = games.groupby(["season", "team"])[[*COUNT_COLS, *[f"opp_{c}" for c in COUNT_COLS]]].sum()
    sums = sums.rename(columns={c: f"tm_{c}" for c in COUNT_COLS})
    sums["tm_games"] = games.groupby(["season", "team"]).size()
    sums["tm_mp"] = players.groupby(["season", "team"])["sec"].sum()
    sums["tm_pf"] = players.groupby(["season", "team"])["pf"].sum()
    return sums.reset_index()


def win_shares(players: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Win Shares per player, season and team: OWS, DWS, WS, WS/40 and the possessions used.

    ``players`` and ``teams`` are the box-score tables of ``stats.box.BoxGames``. Every row of
    ``players`` must have ``sec`` > 0 (he was on the court).
    """
    tm = _team_seasons(teams, players)
    tm["tm_fgm"] = tm["tm_fg2m"] + tm["tm_fg3m"]
    tm["tm_fga"] = tm["tm_fg2a"] + tm["tm_fg3a"]
    tm["opp_fgm"] = tm["opp_fg2m"] + tm["opp_fg3m"]
    tm["opp_fga"] = tm["opp_fg2a"] + tm["opp_fg3a"]
    tm_ft = tm["tm_ftm"] / tm["tm_fta"]
    opp_ft = tm["opp_ftm"] / tm["opp_fta"]
    tm["scoring"] = scoring_possessions(tm["tm_fgm"], tm_ft, tm["tm_fta"])
    tm["play"] = team_play_pct(tm["scoring"], tm["tm_fga"], tm["tm_fta"], tm["tm_tov"])
    tm["orb_pct"] = team_orb_pct(tm["tm_oreb"], tm["opp_dreb"])
    tm["orb_weight"] = team_orb_weight(tm["orb_pct"], tm["play"])
    tm["orb_factor"] = (tm["tm_oreb"] / tm["scoring"]) * tm["orb_weight"] * tm["play"]
    tm["orb_weight_play"] = tm["orb_weight"] * tm["play"]
    tm["ppp_scoring"] = tm["tm_pts"] / tm["scoring"]
    tm["team_ppp"] = tm["tm_pts"] / tm["tm_poss"]
    tm["pace"] = tm["tm_poss"] / tm["tm_games"]
    league = tm.groupby("season")[["tm_pts", "tm_poss", "tm_games"]].sum()
    lg = pd.DataFrame(
        {
            "lg_ppp": league["tm_pts"] / league["tm_poss"],
            "lg_ppg": league["tm_pts"] / league["tm_games"],
            "lg_pace": league["tm_poss"] / league["tm_games"],
        }
    )
    tm = tm.merge(lg, left_on="season", right_index=True)
    tm["ppw"] = points_per_win(tm["lg_ppg"], tm["pace"], tm["lg_pace"])
    # defence: the opponents' totals against this team
    tm["dfg"] = tm["opp_fgm"] / tm["opp_fga"]
    tm["dor"] = tm["opp_oreb"] / (tm["opp_oreb"] + tm["tm_dreb"])
    tm["fmwt"] = (tm["dfg"] * (1 - tm["dor"])) / (
        tm["dfg"] * (1 - tm["dor"]) + (1 - tm["dfg"]) * tm["dor"]
    )
    tm["stops2_team"] = (tm["opp_fga"] - tm["opp_fgm"] - tm["tm_blk"]) * tm["fmwt"] * (
        1 - DOR_STOP_WEIGHT * tm["dor"]
    ) + (tm["opp_tov"] - tm["tm_stl"])
    tm["foul_stops_team"] = FT_SCORING * tm["opp_fta"] * (1 - opp_ft) ** 2
    tm["d_pps"] = tm["opp_pts"] / (
        tm["opp_fgm"] + (1 - (1 - opp_ft) ** 2) * tm["opp_fta"] * FT_SCORING
    )
    tm["team_drtg"] = 100 * tm["opp_pts"] / tm["tm_poss"]

    pl = players.groupby(["season", "team", "player_id"], as_index=False).agg(
        player=("player", "last"), **{c: (c, "sum") for c in PLAYER_COLS}
    )
    pl["fgm"] = pl["fg2m"] + pl["fg3m"]
    pl["fga"] = pl["fg2a"] + pl["fg3a"]
    pl["ft_pct"] = _div(pl["ftm"], pl["fta"])
    pl = pl.merge(tm, on=["season", "team"], validate="many_to_one")
    pl["qast"] = qast(
        sec=pl["sec"],
        team_sec=pl["tm_mp"],
        ast=pl["ast"],
        fgm=pl["fgm"],
        team_ast=pl["tm_ast"],
        team_fgm=pl["tm_fgm"],
    )
    qa = pl["qast"]
    fg_share = _div(pl["pts"] - pl["ftm"], 2 * pl["fga"])  # (PTS - FTM) / (2 FGA); 0 without FGA

    # Offense. The team terms are per team-season (the merged columns).
    pl["pprod"] = points_produced(
        fgm=pl["fgm"],
        fg3m=pl["fg3m"],
        pts=pl["pts"],
        ftm=pl["ftm"],
        fga=pl["fga"],
        qast_value=qa,
        fg_share=fg_share,
        ast=pl["ast"],
        team_fgm=pl["tm_fgm"],
        team_fg3m=pl["tm_fg3m"],
        team_pts=pl["tm_pts"],
        team_ftm=pl["tm_ftm"],
        team_fga=pl["tm_fga"],
        oreb=pl["oreb"],
        team_orb_factor=pl["orb_factor"],
        orb_weight_play=pl["orb_weight_play"],
        team_ppp_scoring=pl["ppp_scoring"],
    )
    pl["scoring_poss"] = scoring_possessions_player(
        fgm=pl["fgm"],
        fga=pl["fga"],
        pts=pl["pts"],
        ftm=pl["ftm"],
        fta=pl["fta"],
        ft_pct=pl["ft_pct"],
        qast_value=qa,
        fg_share=fg_share,
        ast=pl["ast"],
        team_pts=pl["tm_pts"],
        team_ftm=pl["tm_ftm"],
        team_fga=pl["tm_fga"],
        oreb=pl["oreb"],
        team_orb_factor=pl["orb_factor"],
        orb_weight_play=pl["orb_weight_play"],
    )
    pl["poss_used"] = possessions_used(
        scoring=pl["scoring_poss"],
        fga=pl["fga"],
        fgm=pl["fgm"],
        team_orb_pct_value=pl["orb_pct"],
        ft_pct=pl["ft_pct"],
        fta=pl["fta"],
        tov=pl["tov"],
    )
    pl["ows"] = marginal_offense(pl["pprod"], pl["lg_ppp"], pl["poss_used"]) / pl["ppw"]

    # Defense
    stops1 = (
        pl["stl"]
        + pl["blk"] * pl["fmwt"] * (1 - DOR_STOP_WEIGHT * pl["dor"])
        + pl["dreb"] * (1 - pl["fmwt"])
    )
    stops2 = (pl["sec"] / pl["tm_mp"]) * pl["stops2_team"] + (pl["pf"] / pl["tm_pf"]) * pl[
        "foul_stops_team"
    ]
    stop = stop_percentage(stops1 + stops2, pl["tm_mp"], pl["tm_poss"], pl["sec"])
    drtg = individual_drtg(pl["team_drtg"], pl["d_pps"], stop)
    pl["dws"] = (
        marginal_defense(pl["sec"], pl["tm_mp"], pl["tm_poss"], pl["lg_ppp"], drtg) / pl["ppw"]
    )

    pl["ws"] = pl["ows"] + pl["dws"]
    pl["minutes"] = pl["sec"] / 60
    pl["ws40"] = pl["ws"] / pl["minutes"] * MINUTES_PER_GAME
    out = pl[
        [
            "season",
            "team",
            "player_id",
            "player",
            "minutes",
            "pprod",
            "poss_used",
            "ows",
            "dws",
            "ws",
            "ws40",
        ]
    ].rename(columns={"pprod": "points_produced", "poss_used": "possessions_used"})
    return out.reset_index(drop=True)


WS_FIELDS = ("ows", "dws", "ws", "ws40")
WIN_SHARES_SCHEMA = pa.DataFrameSchema(
    {
        "season": pa.Column("int64"),
        "team": pa.Column(str),
        "player_id": pa.Column(str),
        "player": pa.Column(str),
        "minutes": pa.Column("float64", pa.Check.gt(0)),
        "points_produced": pa.Column("float64"),
        "possessions_used": pa.Column("float64"),
        "ows": pa.Column("float64"),
        "dws": pa.Column("float64"),
        "ws": pa.Column("float64"),
        "ws40": pa.Column("float64"),
    },
    unique=["season", "team", "player_id"],
    strict=True,
)


def box_win_shares(players: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Win Shares of every player who was on court in the box scores (``WIN_SHARES_SCHEMA``)."""
    on_court = players[players["sec"] > 0]
    return validated(win_shares(on_court, teams), WIN_SHARES_SCHEMA)


def team_check(ws: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Per season: the correlation of each team's summed player WS with its wins, the mean absolute
    error of that sum, and the league sum of WS against the league's wins (the same games)."""
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
