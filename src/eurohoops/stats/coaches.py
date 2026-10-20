"""EuroLeague coaches -> ``coaches/index.json`` and ``coaches/<slug>.json`` (the coach pages).

One row per team-game from the cached box scores (``Stats[i].Coach``, the coach of that side).
Expectation: the pre-game Elo win probability of each side (the history Elo, ``api.readmodel``
passes ``p_home``), so ``wins_above_expectation`` = actual wins - sum of those probabilities.
Games whose box score names no coach are left out (``coverage`` says how many per season).
Head-to-head: games between two named coaches, listed for pairs with ``H2H_MIN_GAMES`` or more.
Seasons: ``coaches/seasons.json`` has one row per coach and season, with the clubs of that season
merged (in order of first game), the season's figures, playoff flags for that season (0 or 1 each)
and the season's style block (stats/coach_style.py) when styles are given.
Playoffs: a season counts as a playoff season for a coach with a PO or FF game in it, a Final Four
season with an FF game, and a title for the coach of the Final Four champion (``final_winners``).
"""

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from eurohoops.ingest.cache import read_cached
from eurohoops.models.elo import EloParams, prepare, replay, win_probability
from eurohoops.parse.coach_names import resolve
from eurohoops.stats.coach_style import StyleIndex, coach_style

H2H_MIN_GAMES = 1  # every pair is listed: the coach page searches them all
ROWS_COLUMNS = [
    "season",
    "game_id",
    "team",
    "opponent",
    "home",
    "won",
    "p_win",
    "slug",
    "name",
    "tipoff_utc",
    "phase",
    "final",
    "champion",
]
PLAYOFF_PHASES = ("PO", "FF")  # the play-in (PI) and the Top 16 (TS) are not playoffs


def with_elo(games: pd.DataFrame, params: EloParams, first_season: int) -> pd.DataFrame:
    """``games`` with ``p_home``: the pre-game win probability of an Elo replayed with ``params``
    over the games from ``first_season`` on (NaN before it). The replay is the walk-forward
    history Elo, so no game sees its own result or a later one."""
    window = games[games["season"] >= first_season].sort_values("tipoff_utc", kind="stable")
    diffs = replay(prepare(window), params)
    probs = pd.Series(
        [win_probability(float(d)) for d in diffs],
        index=window["game_id"].astype(str).to_numpy(),
    )
    return games.assign(p_home=games["game_id"].astype(str).map(probs))


def final_winners(games: pd.DataFrame) -> dict[str, str]:
    """game_id -> the team code that won the Final Four final, per season where one is found.

    The Final Four is two semifinals in the season's first Final Four round and then the rounds
    after it: the final is the one later game between the two semifinal winners (a third-place
    game, where played, has losing semifinalists). A season without exactly one such game gets no
    entry rather than a guess.
    """
    phase = games[games["phase"] == "FF"]
    played = phase[phase["played"] & ~phase["forfeit"]]
    winners: dict[str, str] = {}
    for _, part in played.groupby("season"):
        first = int(part["round"].min())
        semis = part[part["round"] == first]
        through = {
            str(g["home"] if g["home_score"] > g["away_score"] else g["away"])
            for g in semis.to_dict("records")
        }
        later = part[part["round"] > first]
        finals = [
            g
            for g in later.to_dict("records")
            if str(g["home"]) in through and str(g["away"]) in through
        ]
        if len(finals) == 1:
            final = finals[0]
            winners[str(final["game_id"])] = str(
                final["home"] if final["home_score"] > final["away_score"] else final["away"]
            )
    return winners


def _sides(raw_dir: Path, games: pd.DataFrame, champions: dict[str, str]) -> list[dict[str, Any]]:
    """One dict per team-game of ``games`` (played, not forfeit, with a cached box score)."""
    sides: list[dict[str, Any]] = []
    rated = games[games["played"] & ~games["forfeit"] & games["p_home"].notna()]
    for game in rated.to_dict("records"):
        path = raw_dir / "boxscore" / f"E{int(game['season'])}" / f"{game['game_code']}.json.gz"
        if not path.exists():
            continue
        box = json.loads(read_cached(path))
        home, away = str(game["home"]), str(game["away"])
        found = []
        for side in box.get("Stats", []):
            players = side.get("PlayersStats") or []
            if not players:
                continue
            team = str(players[0]["Team"]).strip()
            found.append((team, str(side.get("Coach") or "").strip()))
        if sorted(t for t, _ in found) != sorted((home, away)):
            continue  # the box score is not this game's (the same check as stats.box)
        home_won = int(game["home_score"]) > int(game["away_score"])
        game_id = str(game["game_id"])
        for team, raw in found:
            is_home = team == home
            p_home = float(game["p_home"])
            sides.append(
                {
                    "season": int(game["season"]),
                    "game_id": game_id,
                    "team": team,
                    "opponent": away if is_home else home,
                    "home": is_home,
                    "won": home_won == is_home,
                    "p_win": p_home if is_home else 1.0 - p_home,
                    "tipoff_utc": game["tipoff_utc"],
                    "phase": str(game["phase"]),
                    "final": game_id in champions,
                    "champion": champions.get(game_id) == team,
                    "raw": raw,
                }
            )
    return sides


def coach_games(raw_dir: Path, games: pd.DataFrame) -> pd.DataFrame:
    """Team-game rows with the coach of that side (``slug``/``name``, missing when unnamed).

    ``games`` is one competition's games table with a ``p_home`` column (the pre-game Elo win
    probability of the home side, NaN where none was computed); games without it are skipped.
    """
    sides = _sides(raw_dir, games, final_winners(games))
    named = resolve(Counter(s["raw"] for s in sides if s["raw"]))
    for side in sides:
        coach = named.get(side["raw"])
        side["slug"] = None if coach is None else coach.slug
        side["name"] = None if coach is None else coach.name
    frame = pd.DataFrame(sides, columns=[*ROWS_COLUMNS, "raw"])
    return frame.drop(columns="raw").astype(
        {"season": "int64", "p_win": "float64", "final": "bool", "champion": "bool"}
    )


def _count(rows: pd.DataFrame) -> dict[str, Any]:
    games = len(rows)
    wins = int(rows["won"].sum())
    expected = float(rows["p_win"].sum())
    return {
        "games": games,
        "wins": wins,
        "losses": games - wins,
        "expected_wins": round(expected, 2),
        "wins_above_expectation": round(wins - expected, 2),
    }


def _playoffs(rows: pd.DataFrame) -> dict[str, int]:
    """Seasons with a playoff game, with a Final Four game and with the Final Four title."""
    by_season = pd.DataFrame(
        {
            "season": rows["season"],
            "playoffs": rows["phase"].isin(PLAYOFF_PHASES),
            "final_four": rows["phase"] == "FF",
            "title": rows["champion"],
        }
    ).groupby("season")
    seasons = by_season[["playoffs", "final_four", "title"]].any()
    return {
        "seasons": int(seasons["playoffs"].sum()),
        "final_four": int(seasons["final_four"].sum()),
        "titles": int(seasons["title"].sum()),
    }


def current_coaches(
    rows: pd.DataFrame, codes: Mapping[str, str]
) -> tuple[int | None, list[dict[str, Any]]]:
    """The latest season and, per club of it, the coach of that club's most recent game there.

    A club whose most recent game names no coach is left out, as is a coach replaced mid-season.
    Clubs carry their display code (``codes``); ordered by it.
    """
    if rows.empty:
        return None, []
    latest = int(rows["season"].max())
    part = rows[rows["season"] == latest].sort_values("tipoff_utc", kind="stable")
    last = part.groupby("team", sort=False).tail(1)
    current = [
        {"team": codes.get(str(row["team"]), str(row["team"])), "slug": row["slug"]}
        for row in last.to_dict("records")
        if isinstance(row["slug"], str)
    ]
    current.sort(key=lambda row: row["team"])
    return latest, current


def coach_payloads(
    rows: pd.DataFrame,
    codes: Mapping[str, str],
    names: Mapping[str, str],
    styles: StyleIndex | None = None,
) -> dict[str, dict[str, Any]]:
    """``coaches/index.json`` and one ``coaches/<slug>.json`` per named coach (see the docstring).

    ``codes`` maps source team codes to display codes and ``names`` to club names. Season and
    club rows carry the display code; the game rows keep source codes upstream. ``styles`` adds
    each coach's ``style`` block (stats/coach_style.py) when given.
    """
    named = rows[rows["slug"].notna()]
    coverage = [
        {
            "season": int(str(season)),
            "games": int(len(part) // 2),
            "with_coach": int(part["slug"].notna().sum() // 2),
        }
        for season, part in rows.groupby("season")
    ]
    pairs = named.merge(named, on="game_id", suffixes=("", "_opp"))
    pairs = pairs[pairs["slug"] != pairs["slug_opp"]]
    files: dict[str, dict[str, Any]] = {}
    index: list[dict[str, Any]] = []
    season_rows: list[dict[str, Any]] = []
    for (slug, name), coach in named.groupby(["slug", "name"]):
        seasons = []
        for (season, team), part in coach.groupby(["season", "team"]):
            seasons.append(
                {
                    "season": int(str(season)),
                    "team": codes.get(str(team), str(team)),
                    "team_name": names.get(str(team), str(team)),
                    **_count(part),
                }
            )
        seasons.sort(key=lambda row: (row["season"], row["team"]))
        clubs: dict[str, dict[str, Any]] = {}
        for row in seasons:
            club = clubs.setdefault(
                row["team"],
                {"team": row["team"], "team_name": row["team_name"], "seasons": []},
            )
            club["seasons"].append(row["season"])
        h2h = []
        for (opp_slug, opp_name), part in pairs[pairs["slug"] == slug].groupby(
            ["slug_opp", "name_opp"]
        ):
            count = _count(part)
            if count["games"] >= H2H_MIN_GAMES:
                h2h.append({"slug": opp_slug, "name": opp_name, **count})
        h2h.sort(key=lambda row: (-row["games"], row["name"]))
        total = _count(coach)
        row = {
            "slug": slug,
            "name": name,
            **total,
            "seasons_played": sorted({r["season"] for r in seasons}),
            "clubs": [c["team"] for c in clubs.values()],
            "playoffs": _playoffs(coach),
        }
        index.append(row)
        for season, part in coach.groupby("season"):
            ordered = part.sort_values("tipoff_utc", kind="stable")
            season_rows.append(
                {
                    "slug": slug,
                    "name": name,
                    "season": int(str(season)),
                    "clubs": [codes.get(str(t), str(t)) for t in dict.fromkeys(ordered["team"])],
                    **_count(part),
                    "playoffs": _playoffs(part),
                    "style": None if styles is None else coach_style(part, styles),
                }
            )
        files[f"coaches/{slug}.json"] = {
            "slug": slug,
            "name": name,
            "career": total,
            "seasons": seasons,
            "clubs": list(clubs.values()),
            "h2h": h2h,
            "style": None if styles is None else coach_style(coach, styles),
        }
    index.sort(key=lambda row: (-row["games"], row["name"]))
    season_rows.sort(key=lambda row: (-row["season"], row["name"]))
    files["coaches/seasons.json"] = {"rows": season_rows}
    current_season, current = current_coaches(rows, codes)
    # The day of the latest box score behind ``current``: games played after it have no coach yet.
    through = None
    if current_season is not None:
        latest_rows = rows[rows["season"] == current_season]
        through = str(latest_rows["tipoff_utc"].max())[:10]
    files["coaches/index.json"] = {
        "h2h_min_games": H2H_MIN_GAMES,
        "coverage": coverage,
        "current_season": current_season,
        "current_through": through,
        "current": current,
        "coaches": index,
    }
    return files
