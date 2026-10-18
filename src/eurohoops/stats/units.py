"""Best duos and five-man units per club and season, from the stints (``parse/stints_mart.py``).

A pair is two players on the court together, a unit is five. Every stint counts for each pair
and each unit of the side on the court: its seconds, that side's possessions and its points for
and against. ``net`` is the net points per 100 possessions. ``ci`` is a rough 95% half-width for
that net rating: lineup ratings are noisy, so the page shows it beside the possession count.

Only seasons that pass the same stint quality check as the on/off export count
(``onoff.qualifying_seasons``). Pairs need ``MIN_PAIR_SECONDS`` on the court, units
``MIN_UNIT_SECONDS``. A club keeps its ``TOP_N`` pairs and units by minutes.

``seasons/{season}/units.json``: ``{"season", "minimums": {"pair", "unit"} (minutes), "sd"
(points per possession, the noise behind ``ci``), "clubs": {code: {"pairs": [...], "units":
[...]}}}``. A pair row is ``[a, b, minutes, poss, pf, pa, net, ci]`` (ids sorted); a unit row is
``[a, b, c, d, e, minutes, poss, pf, pa, net, ci]``. Minutes and ``net`` have one decimal.
"""

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from eurohoops.parse.stints_mart import build_stints_mart
from eurohoops.stats.onoff import played_games, qualifying_seasons, rated_games

MIN_PAIR_SECONDS = 100 * 60
MIN_UNIT_SECONDS = 50 * 60
UNIT_SIZE = 5
TOP_N = 15
Z_95 = 1.96
# index of each total in the per-group accumulator
_SEC, _POSS, _PF, _PA = range(4)


def net_rating(pf: float, pa: float, poss: float) -> float:
    """Net points per 100 possessions (0 with no possessions)."""
    return 100 * (pf - pa) / poss if poss else 0.0


def half_width(sd: float, poss: float) -> float:
    """Rough 95% half-width of a net rating over ``poss`` possessions, in points per 100.

    The margin per possession has standard deviation ``sd``; the rating is 100 times its mean,
    so its standard error is ``100 * sd / sqrt(poss)``. Possessions are treated as independent.
    """
    return Z_95 * 100 * sd / math.sqrt(poss) if poss else 0.0


def possession_sd(margins: Sequence[float], poss: Sequence[float]) -> float:
    """Points per possession of the margin, from stints: sqrt(sum of squared margins / possessions).

    A stint's margin is a sum of its possessions' margins, so its variance grows with its
    possessions; this pools that over the season. Zero when there are no possessions.
    """
    total = sum(poss)
    return math.sqrt(sum(m * m for m in margins) / total) if total else 0.0


def _season_clubs(stints: pd.DataFrame, codes: Mapping[str, str]) -> tuple[dict[str, Any], float]:
    """The per-club pair and unit rows of one season's stints, and the season's ``sd``."""
    pairs: dict[str, dict[tuple[str, ...], list[float]]] = defaultdict(
        lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    )
    units: dict[str, dict[tuple[str, ...], list[float]]] = defaultdict(
        lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    )
    margins: list[float] = []
    stint_poss: list[float] = []
    for row in stints.to_dict("records"):
        sec = float(row["end_s"]) - float(row["start_s"])
        home_pts, away_pts = float(row["home_points"]), float(row["away_points"])
        home_poss, away_poss = float(row["home_poss"]), float(row["away_poss"])
        margins.append(home_pts - away_pts)
        stint_poss.append(home_poss)
        sides = (
            (str(row["home"]), list(row["home_players"]), home_poss, home_pts, away_pts),
            (str(row["away"]), list(row["away_players"]), away_poss, away_pts, home_pts),
        )
        for team, players, poss, pf, pa in sides:
            club = codes.get(team, team)
            ids = sorted(str(p) for p in players)
            for i, a in enumerate(ids):
                for b in ids[i + 1 :]:
                    acc = pairs[club][(a, b)]
                    acc[_SEC] += sec
                    acc[_POSS] += poss
                    acc[_PF] += pf
                    acc[_PA] += pa
            if len(ids) == UNIT_SIZE:
                acc = units[club][tuple(ids)]
                acc[_SEC] += sec
                acc[_POSS] += poss
                acc[_PF] += pf
                acc[_PA] += pa
    sd = round(possession_sd(margins, stint_poss), 3)
    clubs: dict[str, Any] = {}
    for club in sorted(set(pairs) | set(units)):
        kept_pairs = [
            (key, acc) for key, acc in pairs.get(club, {}).items() if acc[_SEC] >= MIN_PAIR_SECONDS
        ]
        kept_units = [
            (key, acc) for key, acc in units.get(club, {}).items() if acc[_SEC] >= MIN_UNIT_SECONDS
        ]
        clubs[club] = {
            "pairs": [[*key, *_flat(acc, sd)] for key, acc in _top(kept_pairs)],
            "units": [[*key, *_flat(acc, sd)] for key, acc in _top(kept_units)],
        }
    return clubs, sd


def _top(
    items: list[tuple[tuple[str, ...], list[float]]],
) -> list[tuple[tuple[str, ...], list[float]]]:
    """The ``TOP_N`` by minutes; ties by player ids."""
    return sorted(items, key=lambda kv: (-kv[1][_SEC], kv[0]))[:TOP_N]


def _flat(acc: list[float], sd: float) -> list[float]:
    """Minutes, possessions, points for, points against, net and ci of one group."""
    poss, pf, pa = acc[_POSS], acc[_PF], acc[_PA]
    return [
        round(acc[_SEC] / 60, 1),
        round(poss),
        round(pf),
        round(pa),
        round(net_rating(pf, pa, poss), 1),
        round(half_width(sd, poss), 1),
    ]


def units_by_season(
    stints: pd.DataFrame,
    checks: pd.DataFrame,
    played: Mapping[int, int],
    window: list[int],
    codes: Mapping[str, str],
) -> dict[int, dict[str, Any]]:
    """Season -> the ``units.json`` payload, for the qualifying seasons of ``window`` only.

    ``stints`` and ``checks`` are the stints mart tables (``stint_game_checks``); ``played``
    counts each season's rated games; ``codes`` renames source team codes for display.
    """
    seasons = qualifying_seasons(checks, played, window)
    good = set(checks.loc[checks["passed"] & checks["season"].isin(seasons), "game_id"])
    use = stints[stints["game_id"].isin(good)]
    out: dict[int, dict[str, Any]] = {}
    for season in seasons:
        clubs, sd = _season_clubs(use[use["season"] == season], codes)
        out[season] = {
            "season": season,
            "minimums": {"pair": MIN_PAIR_SECONDS // 60, "unit": MIN_UNIT_SECONDS // 60},
            "sd": sd,
            "clubs": clubs,
        }
    return out


def load_units(
    raw_dir: Path, games: pd.DataFrame, window: list[int], codes: Mapping[str, str]
) -> dict[int, dict[str, Any]]:
    """The units payloads, with the stints built from the cached raw files (as the marts do)."""
    rated = rated_games(games, window)
    mart = build_stints_mart(raw_dir, rated)
    return units_by_season(mart.stints, mart.checks, played_games(rated), window, codes)
