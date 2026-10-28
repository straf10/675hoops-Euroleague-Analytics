"""Projected-share variants for the M5 game predictor (week 14-16, J2).

Same shares as :mod:`eurohoops.models.minutes` (5 x player seconds / team seconds, capped at 1,
no renormalisation after the cap), projected from the team's earlier games under three rules:

- ``proj_hc``: H-c, the team's previous ``n_games`` games (``minutes.projected_shares``).
- ``proj_decay`` (D2): *all* the team's earlier rated games of the season with player rows,
  weighted ``0.5 ** (k / half_life_games)`` (k = 0 for the most recent game, 1 for the one before,
  ...): share = min(1, 5 x sum(w · sec) / sum(w · team_sec)). Before the team's first such game
  the whole previous season with that team counts, equally weighted (as in H-c).
  ``half_life_games=math.inf`` weights every game equally.
- ``proj_avail``: ``proj_decay``, then a player absent (no row, or 0 seconds) from each of the
  team's last ``absent_games`` earlier games of the season is dropped, and the others' shares are
  scaled so the team's share sum is unchanged, then capped at 1. Nobody is dropped before the
  team has ``absent_games`` earlier games this season (the previous-season fallback included),
  nor if that would drop every player.

Walk-forward safe like H-c: a game's projection reads only games that tipped off before its round
cutoff (the first tip-off of its ``(season, phase, round)``), never the game's own rows.
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from eurohoops.models import minutes
from eurohoops.models.elo import FloatArray
from eurohoops.parse.schemas import validated

VARIANTS = ("proj_hc", "proj_decay", "proj_avail")


def _decay_weights(count: int, half_life_games: float) -> FloatArray:
    """Weights of ``count`` games in time order: the most recent has k = 0 and weight 1."""
    ages = np.arange(count - 1, -1, -1, dtype=np.float64)
    weights: FloatArray = 0.5 ** (ages / half_life_games)
    return weights


def _drop_absent(shares: dict[str, float], played: set[str]) -> dict[str, float]:
    """Drop the players who played in none of the recent games; rescale the rest to the old sum."""
    kept = {p: s for p, s in shares.items() if p in played}
    if not kept or len(kept) == len(shares):
        return shares
    scale = sum(shares.values()) / sum(kept.values())
    return {p: min(1.0, s * scale) for p, s in kept.items()}


@dataclass(frozen=True)
class _Played:
    """One team-season's rated games in tip-off order. Each game's player rows (``codes``: the
    player's index in the sorted player list, ``secs``) sit in game order in one array, with
    ``starts[i]`` the offset of game ``i``'s rows (``starts[-1]`` = all rows)."""

    times: FloatArray
    team_secs: FloatArray
    starts: npt.NDArray[np.int64]
    codes: npt.NDArray[np.int64]
    secs: npt.NDArray[Any]


@dataclass(frozen=True)
class _Window:
    """A projected side, before the group sums: its denominator and, for proj_avail, the codes of
    the players who played in its last ``absent_games`` games (None: no absence rule)."""

    game_id: str
    side: str
    team: str
    denominator: float
    absent_codes: npt.NDArray[np.int64] | None


def _played_index(
    team_games: pd.DataFrame, player_games: pd.DataFrame, codes: dict[str, int]
) -> dict[tuple[object, ...], _Played]:
    """Per (team, season), the player rows of its games in tip-off order (``team_games`` is
    sorted by tip-off). Rows of one (game, team) keep their ``player_games`` order."""
    player_codes = np.array([codes[str(p)] for p in player_games["player_id"]], dtype=np.int64)
    secs = player_games["sec"].to_numpy()
    rows_by: dict[Any, tuple[npt.NDArray[np.int64], npt.NDArray[Any]]] = {}
    for key, positions in player_games.groupby(["game_id", "team"]).indices.items():
        rows_by[key] = (player_codes[positions], secs[positions])
    out: dict[tuple[object, ...], _Played] = {}
    for key, frame in team_games.groupby(["team", "season"]):
        parts = [rows_by[(g, key[0])] for g in frame["game_id"]]
        counts = np.array([len(part[0]) for part in parts], dtype=np.int64)
        starts = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
        out[key] = _Played(
            times=frame["time"].to_numpy(dtype=np.float64),
            team_secs=frame["team_sec"].to_numpy(dtype=np.float64),
            starts=starts,
            codes=np.concatenate([part[0] for part in parts]),
            secs=np.concatenate([part[1] for part in parts]),
        )
    return out


def _window_of(
    played: _Played | None,
    cutoff: float,
    season: int,
    team: str,
    by_team: dict[tuple[object, ...], _Played],
) -> tuple[_Played, int, bool] | None:
    """The played games a side projects from: its earlier games of the season (``k`` of them,
    tip-off order), else its whole previous season. None if it has no games at all."""
    k = 0
    if played is not None and not math.isnan(cutoff):
        k = int(np.searchsorted(played.times, cutoff, side="left"))
    if k > 0 and played is not None:
        return played, k, True
    previous = by_team.get((team, season - 1))
    if previous is None or len(previous.times) == 0:
        return None
    return previous, len(previous.times), False


def _side_windows(
    variant: str,
    games: pd.DataFrame,
    by_team: dict[tuple[object, ...], _Played],
    *,
    half_life_games: float,
    absent_games: int,
) -> tuple[
    list[_Window], list[npt.NDArray[np.int64]], list[npt.NDArray[np.int64]], list[npt.NDArray[Any]]
]:
    """Pass 1: every projected side's window, with its rows stacked in the old concatenation
    order (window games in time order, each game's rows in ``player_games`` order)."""
    windows: list[_Window] = []
    group_ids: list[npt.NDArray[np.int64]] = []
    group_codes: list[npt.NDArray[np.int64]] = []
    group_values: list[npt.NDArray[Any]] = []
    for game_id, season, home, away, cutoff in zip(
        games["game_id"],
        games["season"].astype(int),
        games["home"],
        games["away"],
        minutes.round_cutoffs(games),
        strict=True,
    ):
        for side, team in zip(minutes.SIDES, (str(home), str(away)), strict=True):
            found = _window_of(by_team.get((team, season)), float(cutoff), season, team, by_team)
            if found is None:
                continue
            played, k, this_season = found
            weights = (
                _decay_weights(k, half_life_games) if this_season else np.ones(k, dtype=np.float64)
            )
            denominator = float(np.dot(weights, played.team_secs[:k].copy()))
            end = int(played.starts[k])
            row_weights = np.repeat(weights, np.diff(played.starts[: k + 1]))
            absent = None
            if variant == "proj_avail" and this_season and k >= absent_games:
                lo = int(played.starts[k - absent_games])
                on_court = played.secs[lo:end] > 0
                absent = np.unique(played.codes[lo:end][on_court])
            windows.append(_Window(str(game_id), side, team, denominator, absent))
            group_ids.append(np.full(end, len(windows) - 1, dtype=np.int64))
            group_codes.append(played.codes[:end])
            group_values.append(played.secs[:end] * row_weights)
    return windows, group_ids, group_codes, group_values


def _window_shares(
    windows: list[_Window],
    group_ids: list[npt.NDArray[np.int64]],
    group_codes: list[npt.NDArray[np.int64]],
    group_values: list[npt.NDArray[Any]],
    names: list[str],
) -> list[dict[str, object]]:
    """Pass 2: one groupby over every window's rows. pandas sums each (window, player) group's
    values in row order, as the old per-window groupby did, so the sums match bit for bit."""
    out: list[dict[str, object]] = []
    if not windows:
        return out
    sums = (
        pd.DataFrame(
            {
                "window": np.concatenate(group_ids),
                "code": np.concatenate(group_codes),
                "value": np.concatenate(group_values),
            }
        )
        .groupby(["window", "code"], sort=True)["value"]
        .sum()
    )
    window_of = sums.index.get_level_values("window").to_numpy(dtype=np.int64)
    code_of = sums.index.get_level_values("code").to_numpy(dtype=np.int64).tolist()
    seconds = sums.to_numpy(dtype=np.float64).tolist()
    bounds = np.searchsorted(window_of, np.arange(len(windows) + 1)).tolist()
    for w, window in enumerate(windows):
        lo, hi = bounds[w], bounds[w + 1]
        shares = {
            names[c]: min(1.0, minutes.ON_COURT * float(s) / window.denominator)
            for c, s in zip(code_of[lo:hi], seconds[lo:hi], strict=True)
            if s > 0
        }
        if window.absent_codes is not None:
            shares = _drop_absent(shares, {names[c] for c in window.absent_codes.tolist()})
        for player, share in shares.items():
            out.append(
                {
                    "game_id": window.game_id,
                    "side": window.side,
                    "team": window.team,
                    "player_id": player,
                    "share": share,
                }
            )
    return out


def projected_shares_variant(
    variant: str,
    games: pd.DataFrame,
    player_games: pd.DataFrame,
    *,
    n_games: int = 5,
    half_life_games: float = 4.0,
    absent_games: int = 2,
) -> pd.DataFrame:
    """Projected shares of both sides of every game in ``games`` under ``variant``.

    ``variant``: ``proj_hc`` (``n_games`` window), ``proj_decay`` (``half_life_games``) or
    ``proj_avail`` (``proj_decay`` plus the ``absent_games`` rule); see the module docstring.
    ``player_games``: one row per player per game with ``game_id, team, player_id, sec``.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown projection variant {variant!r}; expected one of {VARIANTS}")
    if variant == "proj_hc":
        return minutes.projected_shares(games, player_games, n_games)
    team_games = minutes._team_games(games, player_games)
    # Player codes follow the sorted player ids, so code order is the old sort_index order.
    names = [str(p) for p in sorted(set(player_games["player_id"]))]
    codes = {name: i for i, name in enumerate(names)}
    by_team = _played_index(team_games, player_games, codes)
    windows, group_ids, group_codes, group_values = _side_windows(
        variant, games, by_team, half_life_games=half_life_games, absent_games=absent_games
    )
    out = _window_shares(windows, group_ids, group_codes, group_values, names)
    return validated(
        pd.DataFrame(out, columns=list(minutes.SHARES_SCHEMA.columns)), minutes.SHARES_SCHEMA
    )
