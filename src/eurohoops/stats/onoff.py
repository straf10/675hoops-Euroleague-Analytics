"""On/off and clutch totals per player and season, from the stints mart and the cached play-by-play.

The stats site shows a player's team points for/against, possessions and seconds with him on and
off the court, and in clutch time (the last 5 minutes of the 4th quarter or an overtime, score
within 5 points). Raw totals only; the site derives the rates.

Only passing games (``stint_game_checks.passed``) count, and a season is listed only when at
least 90% of its played games pass. Stints carry their points and possessions as one number, so
the clutch part of a stint is an approximation: a stint counts when the margin at its start is
within the limit, and its seconds, points and possessions are prorated to the part that lies in
the last 5 minutes (a stint that starts before the window uses the margin at its start). Clutch
points of a player are exact: his scoring events from the play-by-play, with the margin before
the event, in the same window.
"""

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from eurohoops.ingest.cache import read_cached
from eurohoops.parallel import map_ordered
from eurohoops.parse.stints import OVERTIME_S, POINTS, QUARTER_S, QUARTERS, events

log = logging.getLogger(__name__)

CLUTCH_SECONDS = 300
CLUTCH_MARGIN = 5
MIN_PASS_SHARE = 0.9
FILE_NAME = "onoff.json"
SCORE_COLUMNS = ("game_id", "season", "period", "elapsed", "team", "player", "points", "home")
_TOTALS = ["sec", "poss", "pf", "pa"]


def empty_payload() -> dict[str, Any]:
    return {
        "seasons": [],
        "clutch": {"last_seconds": CLUTCH_SECONDS, "margin": CLUTCH_MARGIN},
        "players": {},
    }


def _window_start(period: pd.Series) -> pd.Series:
    """Game second where the last ``CLUTCH_SECONDS`` of the period begin."""
    quarters = len(QUARTERS)
    end = np.where(
        period <= quarters,
        period * QUARTER_S,
        quarters * QUARTER_S + (period - quarters) * OVERTIME_S,
    )
    return pd.Series(end - CLUTCH_SECONDS, index=period.index)


def qualifying_seasons(
    checks: pd.DataFrame, played: Mapping[int, int], window: list[int]
) -> list[int]:
    """Seasons of ``window`` where at least 90% of the played games pass the stint checks."""
    passed = checks[checks["passed"]].groupby("season")["game_id"].nunique()
    return [
        s for s in window if played.get(s, 0) > 0 and passed.get(s, 0) / played[s] >= MIN_PASS_SHARE
    ]


def rated_games(games: pd.DataFrame, window: list[int]) -> pd.DataFrame:
    """The played, non-forfeited games of ``window`` (the games the stint checks cover)."""
    return games[games["played"] & ~games["forfeit"] & games["season"].isin(window)]


def played_games(rated: pd.DataFrame) -> dict[int, int]:
    """Season -> number of rated games."""
    counts = rated.groupby("season")["game_id"].nunique()
    return {int(s): int(n) for s, n in zip(counts.index.tolist(), counts.tolist(), strict=True)}


def _clutch_stints(stints: pd.DataFrame) -> pd.DataFrame:
    """Adds ``csec`` (seconds of the stint in clutch time) and ``cfrac`` (that share of it)."""
    out = stints.sort_values(["game_id", "start_s"], kind="stable").copy()
    home = out.groupby("game_id")["home_points"].cumsum() - out["home_points"]
    away = out.groupby("game_id")["away_points"].cumsum() - out["away_points"]
    overlap = (out["end_s"] - np.maximum(out["start_s"], _window_start(out["period"]))).clip(
        lower=0
    )
    close = (out["period"] >= len(QUARTERS)) & ((home - away).abs() <= CLUTCH_MARGIN)
    length = (out["end_s"] - out["start_s"]).clip(lower=1)
    out["csec"] = np.where(close, overlap, 0)
    out["cfrac"] = out["csec"] / length
    return out


def _side_rows(stints: pd.DataFrame) -> pd.DataFrame:
    """One row per team per stint with that team's totals and the clutch share of them."""
    base = stints[["game_id", "season", "csec", "cfrac"]].assign(
        sec=stints["end_s"] - stints["start_s"]
    )
    sides = []
    for mine, other in (("home", "away"), ("away", "home")):
        sides.append(
            base.assign(
                team=stints[mine],
                players=stints[f"{mine}_players"],
                poss=stints[f"{mine}_poss"],
                pf=stints[f"{mine}_points"],
                pa=stints[f"{other}_points"],
            )
        )
    rows = pd.concat(sides, ignore_index=True)
    for name in ("poss", "pf", "pa"):
        rows[f"c{name}"] = rows[name] * rows["cfrac"]
    return rows


def clutch_points(scores: pd.DataFrame) -> pd.DataFrame:
    """Points per (player, season) scored in clutch time, from scoring events in log order.

    ``scores`` has ``SCORE_COLUMNS``; ``home`` marks the home team's events. The margin is the
    running score before the event; events without a clock never count.
    """
    if scores.empty:
        return pd.DataFrame({"player": [], "season": [], "pts": []})
    frame = scores.copy()
    frame["h"] = np.where(frame["home"], frame["points"], 0)
    frame["a"] = np.where(frame["home"], 0, frame["points"])
    before_h = frame.groupby("game_id")["h"].cumsum() - frame["h"]
    before_a = frame.groupby("game_id")["a"].cumsum() - frame["a"]
    keep = (
        (frame["period"] >= len(QUARTERS))
        & frame["elapsed"].notna()
        & (frame["elapsed"] >= _window_start(frame["period"]))
        & ((before_h - before_a).abs() <= CLUTCH_MARGIN)
        & (frame["player"] != "")
    )
    return frame[keep].groupby(["player", "season"], as_index=False).agg(pts=("points", "sum"))


def onoff_payload(
    stints: pd.DataFrame,
    checks: pd.DataFrame,
    played: Mapping[int, int],
    window: list[int],
    scores: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """The ``onoff.json`` payload. ``played``: season -> played games; ``scores``: the scoring
    events (``SCORE_COLUMNS``) of the passing games."""
    seasons = qualifying_seasons(checks, played, window)
    good = set(checks.loc[checks["passed"] & checks["season"].isin(seasons), "game_id"])
    use = stints[stints["game_id"].isin(good)]
    payload = empty_payload()
    payload["seasons"] = seasons
    if use.empty:
        return payload
    rows = _side_rows(_clutch_stints(use))
    on_rows = rows.explode("players").rename(columns={"players": "player"})
    team_games = rows.groupby(["game_id", "team"], as_index=False)[_TOTALS].sum()
    appeared = on_rows[["player", "season", "game_id", "team"]].drop_duplicates()
    off = (
        appeared.merge(team_games, on=["game_id", "team"])
        .groupby(["player", "season"])[_TOTALS]
        .sum()
    )
    on = on_rows.groupby(["player", "season"])[[*_TOTALS, "csec", "cposs", "cpf", "cpa"]].sum()
    off = off - on[_TOTALS]
    pts = clutch_points(scores if scores is not None else pd.DataFrame())
    pts_by = {
        (p, s): int(v) for p, s, v in pts[["player", "season", "pts"]].itertuples(index=False)
    }
    off_by = {(r["player"], r["season"]): r for r in off.reset_index().to_dict("records")}
    players: dict[str, dict[str, Any]] = {}
    for row in on.reset_index().to_dict("records"):
        player, season = str(row["player"]), int(row["season"])
        o = off_by[(row["player"], row["season"])]
        players.setdefault(player, {})[str(season)] = {
            "on": {k: round(float(row[k])) for k in _TOTALS},
            "off": {k: round(float(o[k])) for k in _TOTALS},
            "clutch": {
                "sec": round(float(row["csec"])),
                "poss": round(float(row["cposs"])),
                "pf": round(float(row["cpf"])),
                "pa": round(float(row["cpa"])),
                "pts": pts_by.get((player, season), 0),
            },
        }
    payload["players"] = dict(sorted(players.items()))
    return payload


def _game_score_rows(item: tuple[Path, str, int, int, str]) -> list[tuple[Any, ...]] | None:
    """One game's scoring rows (``SCORE_COLUMNS``) for a worker process; None without a file."""
    raw_dir, game_id, season, code, home = item
    path = raw_dir / "playbyplay" / f"E{season}" / f"{code}.json.gz"
    if not path.exists():
        return None
    return [
        (
            game_id,
            season,
            event.period,
            event.elapsed,
            event.team,
            event.player,
            POINTS[event.kind],
            event.team == home,
        )
        for event in events(json.loads(read_cached(path)))
        if event.kind in POINTS
    ]


def score_events(raw_dir: Path, games: pd.DataFrame) -> pd.DataFrame:
    """Scoring events of ``games`` (game_id, season, game_code, home) from the cached
    play-by-play, in log order. Games without a cached file are skipped."""
    items = [
        (raw_dir, str(game_id), int(season), int(code), home)
        for game_id, season, code, home in zip(
            games["game_id"], games["season"], games["game_code"], games["home"], strict=True
        )
    ]
    rows: list[tuple[Any, ...]] = []
    for found in map_ordered(_game_score_rows, items):
        rows.extend(found or [])
    return pd.DataFrame(rows, columns=list(SCORE_COLUMNS))


def load_onoff(
    mart_path: Path, raw_dir: Path, games: pd.DataFrame, window: list[int]
) -> dict[str, Any]:
    """The payload from the stints mart; the empty payload (and a warning) if it is unusable."""
    if not mart_path.exists():
        log.warning("on/off: %s is missing; writing an empty %s", mart_path, FILE_NAME)
        return empty_payload()
    try:
        with duckdb.connect(str(mart_path), read_only=True) as con:
            stints = con.execute(
                "SELECT * FROM stints WHERE season IN (SELECT UNNEST(?))", [window]
            ).df()
            checks = con.execute("SELECT game_id, season, passed FROM stint_game_checks").df()
    except duckdb.Error as error:
        log.warning("on/off: no stints in %s (%s); writing an empty file", mart_path, error)
        return empty_payload()
    rated = rated_games(games, window)
    played = played_games(rated)
    seasons = qualifying_seasons(checks, played, window)
    good = set(checks.loc[checks["passed"] & checks["season"].isin(seasons), "game_id"])
    scores = score_events(raw_dir, rated[rated["game_id"].isin(good)])
    return onoff_payload(stints, checks, played, window, scores)


def write_onoff(out_dir: Path, payload: Mapping[str, Any]) -> None:
    """Write ``onoff.json`` (compact JSON, LF endings) next to the other stats files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (out_dir / FILE_NAME).write_bytes(f"{text}\n".encode())
