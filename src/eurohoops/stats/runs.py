"""Scoring runs per game, from the cached play-by-play (``score_events`` in ``stats/onoff.py``).

A run is a stretch of scoring by one team that the other team does not interrupt: consecutive
scoring events on the same side. Each team gets its top ``TOP_RUNS`` runs by points (ties: the
earlier run first). A run carries its start and end clock (period and seconds left in it) and the
running score before its first basket and after its last. Raw facts only; no model.

``runs.json`` (one per season, ``seasons/{season}/runs.json``) holds, per game with a cached
play-by-play, ``{"home": [...], "away": [...]}`` with one row per run in ``RUN_FIELDS`` order.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from eurohoops.parse.stints import period_length, period_start
from eurohoops.stats.onoff import score_events

HOME, AWAY = 0, 1
TOP_RUNS = 3
RUN_FIELDS = (
    "points",
    "start_period",
    "start_left",
    "end_period",
    "end_left",
    "from_home",
    "from_away",
    "to_home",
    "to_away",
)


@dataclass(frozen=True)
class Basket:
    """One scoring event: its period, seconds left in that period (None when the row has no
    clock), the side that scored (``HOME`` or ``AWAY``) and the points."""

    period: int
    left: int | None
    side: int
    points: int


def seconds_left(period: int, elapsed: int | None) -> int | None:
    """Game seconds since tip-off -> seconds left in ``period`` (None stays None)."""
    if elapsed is None:
        return None
    return period_start(period) + period_length(period) - elapsed


@dataclass
class _Run:
    side: int
    points: int
    start: Basket
    end: Basket
    before: tuple[int, int]
    after: tuple[int, int]


def _runs(baskets: Sequence[Basket]) -> list[_Run]:
    """Every maximal stretch of same-side scoring, in game order, with the running score."""
    runs: list[_Run] = []
    score = [0, 0]
    for basket in baskets:
        before = (score[HOME], score[AWAY])
        score[basket.side] += basket.points
        if runs and runs[-1].side == basket.side:
            runs[-1].points += basket.points
            runs[-1].end = basket
            runs[-1].after = (score[HOME], score[AWAY])
        else:
            runs.append(
                _Run(
                    side=basket.side,
                    points=basket.points,
                    start=basket,
                    end=basket,
                    before=before,
                    after=(score[HOME], score[AWAY]),
                )
            )
    return runs


def find_runs(baskets: Sequence[Basket], top: int = TOP_RUNS) -> dict[str, list[list[int | None]]]:
    """The top ``top`` runs of each team by points (ties: the earlier run first), as ``RUN_FIELDS``
    rows under ``"home"`` and ``"away"``."""
    runs = _runs(baskets)
    out: dict[str, list[list[int | None]]] = {"home": [], "away": []}
    for side, key in ((HOME, "home"), (AWAY, "away")):
        mine = [(i, run) for i, run in enumerate(runs) if run.side == side]
        mine.sort(key=lambda item: (-item[1].points, item[0]))
        out[key] = [
            [
                run.points,
                run.start.period,
                run.start.left,
                run.end.period,
                run.end.left,
                run.before[HOME],
                run.before[AWAY],
                run.after[HOME],
                run.after[AWAY],
            ]
            for _, run in mine[:top]
        ]
    return out


def game_runs(raw_dir: Path, games: pd.DataFrame) -> dict[str, dict[str, list[list[int | None]]]]:
    """Game id -> top runs of each team, for every game of ``games`` with a cached play-by-play.

    ``games`` needs the columns ``score_events`` reads (game_id, season, game_code, home). A game
    without a cached file has no entry.
    """
    scores = score_events(raw_dir, games)
    out: dict[str, dict[str, list[list[int | None]]]] = {}
    if scores.empty:
        return out
    for game_id, rows in scores.groupby("game_id", sort=False):
        baskets = [
            Basket(
                period=int(period),
                left=seconds_left(int(period), None if pd.isna(elapsed) else int(elapsed)),
                side=HOME if home else AWAY,
                points=int(points),
            )
            for period, elapsed, points, home in zip(
                rows["period"], rows["elapsed"], rows["points"], rows["home"], strict=True
            )
        ]
        out[str(game_id)] = find_runs(baskets)
    return out


def runs_payload(season: int, game_ids: Sequence[str], runs: Mapping[str, Any]) -> dict[str, Any]:
    """``seasons/{season}/runs.json``: the games of ``game_ids`` that have runs, in id order."""
    return {
        "season": season,
        "run_fields": list(RUN_FIELDS),
        "games": {gid: runs[gid] for gid in sorted(game_ids) if gid in runs},
    }
