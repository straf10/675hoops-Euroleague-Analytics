"""The EuroLeague player part M5 uses (moved from ``cli.py`` unchanged, for ELOR's roster prior).

M3's committed ``rapm_spm`` (``reports/backtest_m3.json`` ``chosen``, never re-tuned) is fitted
walk-forward once over the frame; the player part is H-c's ``rapm_margins`` with a shares frame.
``el_player_ratings`` exposes the walk-forward fit and expected possessions themselves, so the
ELOR roster prior (``models/elor.py``) rates its own rosters with the very same fit.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from eurohoops.eval.m3_backtest import TunedRapm, build_rapm_inputs, rapm_margins
from eurohoops.marts import read_table
from eurohoops.models.elo import FloatArray
from eurohoops.models.minutes import expected_possessions
from eurohoops.models.rapm import WalkForward
from eurohoops.models.spm import fit_spm

PlayerPart = Callable[[pd.DataFrame, pd.DataFrame], FloatArray]


class PlayerPartError(RuntimeError):
    """A missing or wrong input (the CLI logs the message and exits 1)."""


@dataclass(frozen=True)
class ElPlayerRatings:
    frame: pd.DataFrame  # the games the walk-forward fit is aligned with (tip-off order)
    wf: WalkForward
    possessions: pd.Series  # expected possessions per game_id


def same_frame(expected: pd.DataFrame, frame: pd.DataFrame) -> None:
    if not frame["game_id"].astype(str).equals(expected["game_id"].astype(str)):
        raise ValueError("the player part was fitted on a different frame than the harness's")


def el_player_ratings(
    frame: pd.DataFrame,
    player_games: pd.DataFrame,
    team_games: pd.DataFrame,
    *,
    m3_report: Path,
    mart_path: Path,
) -> ElPlayerRatings:
    """M3's committed ``rapm_spm`` fitted walk-forward over ``frame``."""
    chosen = json.loads(m3_report.read_text(encoding="utf-8"))["chosen"]
    if chosen["variant"] != "rapm_spm":
        raise PlayerPartError("M3 chosen variant must be rapm_spm (see reports/backtest_m3.json)")
    stints = read_table(mart_path, "stints")
    checks = read_table(mart_path, "stint_game_checks")
    if stints is None or checks is None:
        raise PlayerPartError("stints/stint_game_checks missing; run: eurohoops stints --mart")
    extra = {k: chosen[k] for k in ("target_half_life_days", "target_ridge_o", "target_ridge_d")}
    tuned = TunedRapm(
        chosen["half_life_days"],
        chosen["ridge_o"],
        chosen["ridge_d"],
        chosen["tuning_rmse"],
        grid={},
        extra={**extra, "k": chosen["k"], "alpha": chosen["alpha"]},
    )
    rapm_inputs = build_rapm_inputs(stints, checks, frame, player_games)
    wf = fit_spm(frame, rapm_inputs, tuned)
    possessions = expected_possessions(frame, team_games)
    return ElPlayerRatings(frame, wf, possessions)


def el_player_part(ratings: ElPlayerRatings) -> PlayerPart:
    """M5's EuroLeague player part: ``rapm_margins`` on the fit, for any shares frame."""

    def player_part(games: pd.DataFrame, shares: pd.DataFrame) -> FloatArray:
        same_frame(ratings.frame, games)
        return rapm_margins(games, ratings.wf, shares, ratings.possessions)

    return player_part
