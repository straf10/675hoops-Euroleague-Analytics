"""EuroLeague coaches -> ``coaches/index.json`` and ``coaches/<slug>.json`` (the coach pages).

One row per team-game from the cached box scores (``Stats[i].Coach``, the coach of that side).
Expectation: the pre-game Elo win probability of each side (the history Elo, ``api.readmodel``
passes ``p_home``), so ``wins_above_expectation`` = actual wins - sum of those probabilities.
Games whose box score names no coach are left out (``coverage`` says how many per season).
Head-to-head: games between two named coaches, listed for pairs with ``H2H_MIN_GAMES`` or more.
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

H2H_MIN_GAMES = 4
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
]


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


def _sides(raw_dir: Path, games: pd.DataFrame) -> list[dict[str, Any]]:
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
        for team, raw in found:
            is_home = team == home
            p_home = float(game["p_home"])
            sides.append(
                {
                    "season": int(game["season"]),
                    "game_id": str(game["game_id"]),
                    "team": team,
                    "opponent": away if is_home else home,
                    "home": is_home,
                    "won": home_won == is_home,
                    "p_win": p_home if is_home else 1.0 - p_home,
                    "raw": raw,
                }
            )
    return sides


def coach_games(raw_dir: Path, games: pd.DataFrame) -> pd.DataFrame:
    """Team-game rows with the coach of that side (``slug``/``name``, missing when unnamed).

    ``games`` is one competition's games table with a ``p_home`` column (the pre-game Elo win
    probability of the home side, NaN where none was computed); games without it are skipped.
    """
    sides = _sides(raw_dir, games)
    named = resolve(Counter(s["raw"] for s in sides if s["raw"]))
    for side in sides:
        coach = named.get(side["raw"])
        side["slug"] = None if coach is None else coach.slug
        side["name"] = None if coach is None else coach.name
    frame = pd.DataFrame(sides, columns=[*ROWS_COLUMNS, "raw"])
    return frame.drop(columns="raw").astype({"season": "int64", "p_win": "float64"})


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


def coach_payloads(
    rows: pd.DataFrame, codes: Mapping[str, str], names: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    """``coaches/index.json`` and one ``coaches/<slug>.json`` per named coach (see the docstring).

    ``codes`` maps source team codes to display codes and ``names`` to club names. Season and
    club rows carry the display code; the game rows keep source codes upstream.
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
        }
        index.append(row)
        files[f"coaches/{slug}.json"] = {
            "slug": slug,
            "name": name,
            "career": total,
            "seasons": seasons,
            "clubs": list(clubs.values()),
            "h2h": h2h,
        }
    index.sort(key=lambda row: (-row["games"], row["name"]))
    files["coaches/index.json"] = {
        "h2h_min_games": H2H_MIN_GAMES,
        "coverage": coverage,
        "coaches": index,
    }
    return files
