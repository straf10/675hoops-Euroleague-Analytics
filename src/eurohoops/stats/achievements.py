"""Accolades data: furthest phase per club and player season, and stat titles, since 2007-08 ->
``achievements.json`` (stats dir). The file keeps its name so the API stays stable.

Codes, lowest to highest: ``RS`` regular season (the pre-2016 Top 16, phase ``TS``, counts here),
``PI`` play-in, ``PO`` playoffs, ``FF`` Final Four (a semifinal, or the third-place game), ``F``
lost the final, ``W`` champion.

Final Four: a season's played ``FF`` games sorted by tip-off. The two earliest are the semifinals;
the final is the remaining game between their two winners; the other remaining game is third
place. A season with no ``FF`` game (2019-20, cancelled) has no final and no champion. A Final
Four that cannot be read this way raises rather than guessing.

Club-season: the furthest stage among the club's played games; the final is ``W`` for the
champion and ``F`` for the runner-up. Teams not in the season's games are left out.

Player-season, one entry per club he played for that season: the club-season stage (above) for
every club he played at least one game for that season (a line is a game he played: a box score
with his minutes, DNP excluded). He does not need to have played in the Final Four or the final:
a player on a title team gets ``W`` even if he missed the Final Four. ``champion`` is 1 when that
club is the season's champion. A player traded mid-season therefore has one entry per club. Only
seasons before ``live_season`` are written: the live season is not finished.

Stat titles: for each finished season and each of PTS, REB, AST, STL, BLK and PIR, the player (or
players, on a tie) with the most per game among the qualified players. The floors are the Players
page's (``web/src/lib/players.ts``): at least a quarter of the season's most games, and 10 minutes
a game. ``stat_titles`` maps a player id to ``[season, stat]`` pairs. It covers the same seasons as
``seasons``, since the box scores are cached from 2007-08.

Team codes are the source codes (``DISPLAY_CODES`` is applied by the site, not here).
"""

from typing import Any

import pandas as pd

FIRST_SEASON = 2007  # 2007-08, the first season the games table covers
ORDER = ("RS", "PI", "PO", "FF", "F", "W")
RANK = {code: rank for rank, code in enumerate(ORDER)}
# The phase code -> the stage code for a game's teams (the final is handled separately)
PHASE_STAGE = {"RS": "RS", "TS": "RS", "PI": "PI", "PO": "PO", "FF": "FF"}
# Stat titles: the Players page's keys (REB is offensive + defensive rebounds)
TITLE_STATS = ("pts", "reb", "ast", "stl", "blk", "pir")
TITLE_SECONDS = 10 * 60  # seconds a game, at least: the Players page's default minimum (10 min)


def _result(game: Any) -> tuple[str, str]:
    """(winner, loser) of a played game row."""
    home, away = str(game.home), str(game.away)
    return (home, away) if int(game.home_score) > int(game.away_score) else (away, home)


def final_game(played: pd.DataFrame) -> tuple[str, str, str] | None:
    """(game_id, champion, runner-up) of a season's played games; None without a Final Four."""
    ff = played[played["phase"] == "FF"].sort_values(["tipoff_utc", "game_id"], kind="stable")
    if ff.empty:
        return None
    if len(ff) < 3:
        raise ValueError(f"Final Four with {len(ff)} played games; expected 2 semis and a final")
    semi_winners = {_result(g)[0] for g in ff.iloc[:2].itertuples(index=False)}
    for game in ff.iloc[2:].itertuples(index=False):
        if {str(game.home), str(game.away)} == semi_winners:
            winner, loser = _result(game)
            return str(game.game_id), winner, loser
    raise ValueError("no Final Four game between the two semifinal winners")


def stage_sides(season_games: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """One row per team in each played game (game_id, team, stage) and the champion code."""
    played = season_games[season_games["played"].astype(bool)]
    final = final_game(played)
    final_id, champion = (None, None) if final is None else (final[0], final[1])
    rows: list[tuple[str, str, str]] = []
    for game in played.itertuples(index=False):
        game_id = str(game.game_id)
        for team in (str(game.home), str(game.away)):
            if game_id == final_id:
                stage = "W" if team == champion else "F"
            else:
                stage = PHASE_STAGE[str(game.phase)]
            rows.append((game_id, team, stage))
    sides = pd.DataFrame(rows, columns=["game_id", "team", "stage"])
    return sides, champion


def stat_titles(box_players: pd.DataFrame, seasons: list[int]) -> dict[str, list[list[Any]]]:
    """Player id -> ``[season, stat]`` for each season's leader on each title stat (see module)."""
    lines = box_players[box_players["season"].isin(seasons)].assign(
        reb=lambda b: b["oreb"] + b["dreb"]
    )
    if lines.empty:
        return {}
    totals = (
        lines.groupby(["season", "player_id"])
        .agg(gp=("game_id", "size"), sec=("sec", "sum"), **{s: (s, "sum") for s in TITLE_STATS})
        .reset_index()
    )
    most = totals.groupby("season")["gp"].transform("max")
    # The Players page's floors: a quarter of the season's most games, 10 minutes a game
    qualified = totals[(totals["gp"] * 4 >= most) & (totals["sec"] >= TITLE_SECONDS * totals["gp"])]
    titles: dict[str, list[list[Any]]] = {}
    for stat in TITLE_STATS:
        per_game = qualified[stat] / qualified["gp"]
        best = per_game.groupby(qualified["season"]).transform("max")
        # A season's best of zero is nobody's title
        lead = qualified.loc[(per_game == best) & (best > 0)]
        for season, pid in zip(
            lead["season"].astype(int), lead["player_id"].astype(str), strict=True
        ):
            titles.setdefault(pid, []).append([season, stat])
    return {pid: sorted(titles[pid]) for pid in sorted(titles)}


def achievements_payload(
    games: pd.DataFrame, box_players: pd.DataFrame, live_season: int
) -> dict[str, Any]:
    """The ``achievements.json`` payload: seasons, club codes and player entries (see module)."""
    seasons = sorted(
        {int(s) for s in games["season"].unique() if FIRST_SEASON <= int(s) < live_season}
    )
    clubs: dict[str, dict[str, str]] = {}
    players: dict[str, list[list[Any]]] = {}
    for season in seasons:
        sides, champion = stage_sides(games[games["season"] == season])
        best = sides.assign(rank=sides["stage"].map(RANK)).groupby("team")["rank"].max()
        clubs[str(season)] = {str(team): ORDER[int(rank)] for team, rank in sorted(best.items())}
        lines = box_players.loc[box_players["season"] == season, ["player_id", "game_id", "team"]]
        # A club he played at least one game for: the club-season stage, not his own games
        played = lines.merge(sides[["game_id", "team"]], on=["game_id", "team"]).drop_duplicates(
            ["player_id", "team"]
        )
        for pid, team in (
            played[["player_id", "team"]].sort_values(["player_id", "team"]).itertuples(index=False)
        ):
            stage = ORDER[int(best[str(team)])]
            entry = [season, str(team), stage, int(str(team) == champion)]
            players.setdefault(str(pid), []).append(entry)
    return {
        "seasons": seasons,
        "clubs": clubs,
        "players": {pid: players[pid] for pid in sorted(players)},
        "stat_titles": stat_titles(box_players, seasons),
    }
