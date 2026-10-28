"""A small synthetic EuroLeague league for the M5 harness (week 14-16 J4).

Reused by ``test_m5_backtest.py`` and the leakage suite: ``build_inputs`` returns an ``M5Inputs``
and ``small_spec`` the matching ``M5Backtest`` (tiny grid, a short warmup/tuning/validation/test
split), so a full run takes a few seconds.

The league has 8 teams (``GRE`` among them). Seasons 2015-2022: 2015 only warms M1 and Elo up
(the frame starts at 2016). A
game's margin is a fixed per-player rating table (``PLAYER_RATING``) applied to the game's actual
minutes shares, plus a hidden team effect, a home edge and noise; ``fake_player_part`` applies the
same table to any shares frame, so it is deterministic and reads nothing but its arguments.
Rounds alternate 2 and 5 days apart (short and normal rest); ``other_comp_prev`` is always False.
One 2019 game is a forfeit and one 2021 game is unplayed.
"""

from __future__ import annotations

import copy
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import M5Backtest, M5Grid
from eurohoops.eval.m5_backtest import M5Inputs, run_m5_backtest
from eurohoops.models.elo import FloatArray
from eurohoops.parse.games import conform
from tests.conftest import make_team_games

TARGET_TEAMS = ("GRE", "T01", "T02", "T03", "T04", "T05", "T06", "T07")
SEASONS = tuple(range(2015, 2023))
PLAYERS_PER_TEAM = 9
POINTS_PER_RATING = 1.5  # one rating unit of share-weighted player value is 1.5 points
HOME_EDGE = 3.0
FORFEIT_GAME = (2019, 20)  # (season, game_code)
UNPLAYED_GAME = (2021, 30)
TUNED_M1: dict[str, Any] = {
    "rating": {"half_life_days": 365.0, "carry": 1.0, "ridge": 250.0},
    "pace": {"half_life_days": 365.0, "carry": 1.0, "ridge": 2.0},
    "margin": {"variant": "student_t_const", "scale": 10.0, "df": 7.0, "ref_pace": None},
    "totals_sigma": 16.0,
}
ELO: dict[str, Any] = {
    "k": 20.0,
    "hca": 90.0,
    "reversion": 0.25,
    "margin_scale": 23.358237,
    "margin_sigma": 11.882097,
}


def _player_ratings() -> dict[str, float]:
    rng = np.random.default_rng(20261020)
    return {
        f"{team}_{k}": float(rng.normal(0.0, 1.0))
        for team in TARGET_TEAMS
        for k in range(PLAYERS_PER_TEAM)
    }


PLAYER_RATING = _player_ratings()


def fake_player_part(frame: pd.DataFrame, shares: pd.DataFrame) -> FloatArray:
    """Home minus away of sum(share x rating) in points, NaN for a game with no shares row."""
    sign = np.where(shares["side"] == "home", 1.0, -1.0)
    rating = shares["player_id"].map(PLAYER_RATING).fillna(0.0).to_numpy(dtype=np.float64)
    value = pd.Series(
        POINTS_PER_RATING * sign * shares["share"].to_numpy(dtype=np.float64) * rating,
        index=shares["game_id"].astype(str).to_numpy(),
    )
    per_game = value.groupby(level=0).sum()
    out: FloatArray = np.asarray(per_game.reindex(frame["game_id"].astype(str)), dtype=np.float64)
    return out


def small_spec() -> M5Backtest:
    return M5Backtest(
        report=Path("unused.json"),
        games_report=Path("unused.csv"),
        warmup=(2016, 2017),
        tuning=(2018, 2019),
        validation=(2020,),
        test=(2021, 2022),
        grid=M5Grid(
            half_life_games=(3.0,),
            residual_half_life_days=(180.0,),
            residual_ridge=(10.0, 40.0),
            rest_ridge=(25.0,),
        ),
        bootstrap_resamples=200,
    )


def _legs(teams: tuple[str, ...]) -> list[list[tuple[str, str]]]:
    """A double round robin by the circle method: every team plays once per round."""
    rotation = list(teams)
    half = len(teams) // 2
    first = []
    for r in range(len(teams) - 1):
        pairs = [(rotation[i], rotation[-1 - i]) for i in range(half)]
        first.append(pairs if r % 2 == 0 else [(b, a) for a, b in pairs])
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    return first + [[(b, a) for a, b in pairs] for pairs in first]


def _tipoff(season: int, day: int, hour: int, slot: int) -> pd.Timestamp:
    start = pd.Timestamp(f"{season}-10-01T{hour:02d}:00:00Z")
    return start + pd.Timedelta(days=day, minutes=15 * slot)


def _minutes(rng: np.random.Generator) -> np.ndarray[Any, np.dtype[np.int64]]:
    """One team-game's seconds per roster slot: starters play more, some players sit out."""
    weights = np.linspace(1.0, 0.25, PLAYERS_PER_TEAM) * rng.lognormal(0.0, 0.25, PLAYERS_PER_TEAM)
    weights = weights * (rng.random(PLAYERS_PER_TEAM) > 0.08)
    seconds: np.ndarray[Any, np.dtype[np.int64]] = np.round(12000 * weights / weights.sum()).astype(
        np.int64
    )
    return seconds


def _target_season(
    rng: np.random.Generator, season: int, effect: dict[str, float]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    games: list[dict[str, Any]] = []
    players: list[dict[str, Any]] = []
    code = 0
    for r, pairs in enumerate(_legs(TARGET_TEAMS), start=1):
        day = 7 * ((r - 1) // 2) + 2 * ((r - 1) % 2)
        for slot, (home, away) in enumerate(pairs):
            code += 1
            game_id = f"E{season}_{code}"
            seconds = {team: _minutes(rng) for team in (home, away)}
            share = {t: 5.0 * s / s.sum() for t, s in seconds.items()}
            rating = {
                t: float(
                    sum(share[t][k] * PLAYER_RATING[f"{t}_{k}"] for k in range(PLAYERS_PER_TEAM))
                )
                for t in (home, away)
            }
            margin = (
                HOME_EDGE
                + effect[home]
                - effect[away]
                + POINTS_PER_RATING * (rating[home] - rating[away])
                + rng.normal(0.0, 9.0)
            )
            diff = round(margin) or 1
            base = 72 + int(rng.integers(0, 10))
            home_score, away_score = base + max(diff, 0), base + max(-diff, 0)
            forfeit = (season, code) == FORFEIT_GAME
            played = (season, code) != UNPLAYED_GAME
            if forfeit:
                home_score, away_score = 20, 0
            games.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "game_code": code,
                    "phase": "RS",
                    "round": r,
                    "round_label": f"Round {r}",
                    "tipoff_utc": _tipoff(season, day, 18, slot),
                    "home": home,
                    "away": away,
                    "home_score": home_score if played else None,
                    "away_score": away_score if played else None,
                    "played": played,
                    "forfeit": forfeit,
                    "neutral": False,
                    "confirmed_date": True,
                }
            )
            if played and not forfeit:
                players += [
                    {"game_id": game_id, "team": team, "player_id": f"{team}_{k}", "sec": int(s)}
                    for team in (home, away)
                    for k, s in enumerate(seconds[team])
                    if s > 0
                ]
    return games, players


@cache
def _default_run(tuning_only: bool, score_test: bool) -> tuple[dict[str, Any], pd.DataFrame]:
    return run_m5_backtest(
        build_inputs(0),
        spec=small_spec(),
        player_part=fake_player_part,
        tuning_only=tuning_only,
        score_test=score_test,
    )


def default_run(
    *, tuning_only: bool = False, score_test: bool = False
) -> tuple[dict[str, Any], pd.DataFrame]:
    """``run_m5_backtest`` on ``build_inputs()`` with ``small_spec()`` and ``fake_player_part``.

    Deterministic, so computed once per worker process and shared by every module that asks for
    it. Each caller gets its own copy, so a test that mutates the report or frame cannot leak
    into another test.
    """
    report, frame = _default_run(tuning_only, score_test)
    return copy.deepcopy(report), frame.copy(deep=True)


def build_inputs(seed: int = 0) -> M5Inputs:
    """The synthetic league of the module docstring, deterministic in ``seed``."""
    rng = np.random.default_rng(seed)
    effect = {team: float(rng.normal(0.0, 2.0)) for team in TARGET_TEAMS}
    games: list[dict[str, Any]] = []
    players: list[dict[str, Any]] = []
    for season in SEASONS:
        season_games, season_players = _target_season(rng, season, effect)
        games += season_games
        players += season_players
    target = conform(pd.DataFrame(games))
    return M5Inputs(
        games=target,
        team_games=make_team_games(target),
        player_games=pd.DataFrame(players).astype({"sec": "int64"}),
        tuned_m1=copy.deepcopy(TUNED_M1),
        elo=dict(ELO),
    )
