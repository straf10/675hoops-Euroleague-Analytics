"""POOL-c (docs/models/pool_c.md): the equal-weight pool with its logit scaled by one c.

    P_c = sigmoid( c * z_pool ),   z_pool = logit(P_pool)  (the logit POOL already computes)

``c`` is fitted by log loss on POOL's scored rows for regular-season rounds 1-19 and then frozen
in ``reports/pool_c_fit.json``. The gate's paired bootstrap scores the rounds after them (20 to
season end). The rows are the scorecard's pre-registered row per game (``provable_rows``) joined
with the game's result in the marts. ``run_fit`` and ``run_eval`` are the two stages of
``scripts/diag_pool_c.py``; they take the frames the script reads and write only their report.

Probabilities are clipped to the pool's clip level before any log loss, so a logged 0.0000 or
1.0000 cannot make the loss infinite.
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit

from eurohoops.eval.forecasts import REGULAR_SEASON, _finished
from eurohoops.eval.metrics import paired_bootstrap_ci, per_game_log_loss
from eurohoops.eval.scorecard import provable_rows
from eurohoops.logs import write_json
from eurohoops.models.elo import FloatArray
from eurohoops.models.pool import PROB_CLIP, logit

C_BOUNDS = (0.0, 5.0)  # the search interval for c; a bounded, deterministic 1-D minimisation
GATE_RESAMPLES = 10_000
GATE_SEED = 20261022  # the date the gate was drafted
FIT_LAST_ROUND = 19  # the fit set: regular-season rounds 1 to this; the evaluation is the rest
RULE = "pass when the 95% CI upper bound of the mean (POOL-c minus POOL) log loss is below 0"


class StageRefused(RuntimeError):
    """A stage was asked for before its inputs are complete, or would overwrite a frozen fit."""


def _clip(p: FloatArray) -> FloatArray:
    return np.clip(p, PROB_CLIP, 1.0 - PROB_CLIP)


def _checked(pool_p: FloatArray, home_won: FloatArray) -> tuple[FloatArray, FloatArray]:
    p = np.asarray(pool_p, dtype=np.float64)
    y = np.asarray(home_won, dtype=np.float64)
    if p.ndim != 1 or p.shape != y.shape or not len(p):
        raise ValueError("pool_p and home_won must be non-empty 1-D arrays of one length")
    if not np.all((p > 0.0) & (p < 1.0)):
        raise ValueError("POOL probabilities must lie strictly inside (0, 1)")
    if not np.all((y == 0.0) | (y == 1.0)):
        raise ValueError("home_won must be 0 or 1")
    return p, y


def apply_c(pool_p: FloatArray, c: float) -> FloatArray:
    """POOL-c home-win probabilities: sigmoid(c * logit(P_pool)), clipped to the pool's level."""
    z = c * logit(np.asarray(pool_p, dtype=np.float64))
    return _clip(expit(z))


def mean_log_loss(pool_p: FloatArray, home_won: FloatArray, c: float) -> float:
    """Mean per-game log loss of POOL-c on the given rows."""
    p, y = _checked(pool_p, home_won)
    return float(per_game_log_loss(apply_c(p, c), y).mean())


def fit_c(pool_p: FloatArray, home_won: FloatArray) -> float:
    """The c in ``C_BOUNDS`` that minimises the mean log loss of POOL-c on the given rows.

    Bounded Brent search: deterministic, and the same rows always give the same c. The loss is
    convex in c until the clip binds, so the search finds the minimum.
    """
    p, y = _checked(pool_p, home_won)
    result = minimize_scalar(
        lambda c: mean_log_loss(p, y, float(c)),
        bounds=C_BOUNDS,
        method="bounded",
        options={"xatol": 1e-8},
    )
    if not result.success:
        raise RuntimeError(f"c fit did not converge: {result.message}")
    return float(result.x)


def paired_gap(
    pool_p: FloatArray,
    home_won: FloatArray,
    c: float,
    *,
    resamples: int = GATE_RESAMPLES,
    seed: int = GATE_SEED,
) -> dict[str, float | int | bool]:
    """Paired bootstrap of (POOL-c minus POOL) per-game log loss on the given rows.

    The 95% CI is the percentile interval of the mean over ``resamples`` paired resamples drawn
    with ``seed`` (``eval.metrics.paired_bootstrap_ci``). ``pass`` is the draft gate's rule: the
    CI upper bound is below zero.
    """
    p, y = _checked(pool_p, home_won)
    base = per_game_log_loss(_clip(p), y)
    scaled = per_game_log_loss(apply_c(p, c), y)
    mean, low, high = paired_bootstrap_ci(scaled - base, resamples, seed)
    return {
        "n": len(p),
        "c": float(c),
        "mean_diff": round(mean, 6),
        "ci_lo": round(low, 6),
        "ci_hi": round(high, 6),
        "resamples": resamples,
        "seed": seed,
        "pass": bool(high < 0.0),
    }


# ---- stages: the POOL log and the games mart in, one report out ---------------------------------


def scored_games(
    pool_log: pd.DataFrame, games: pd.DataFrame, season: int, manual_pushes: Sequence[datetime]
) -> pd.DataFrame:
    """POOL's scorecard row per finished game of ``season``, with the home win (1.0 or 0.0).

    Columns: game_id, p_home, model_version, round, phase, tipoff_utc, home_won. Tip-off order.
    """
    rows = provable_rows(pool_log[pool_log["season"] == season], manual_pushes)
    frame = rows[["game_id", "p_home", "model_version"]].merge(
        _finished(games, season)[
            ["game_id", "round", "phase", "tipoff_utc", "home_score", "away_score"]
        ],
        on="game_id",
    )
    frame["home_won"] = (frame["home_score"] > frame["away_score"]).astype(np.float64)
    frame = frame.drop(columns=["home_score", "away_score"])
    return frame.sort_values(["tipoff_utc", "game_id"], ignore_index=True)


def split_fit_eval(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The fit set (regular-season rounds 1 to ``FIT_LAST_ROUND``) and the evaluation set.

    The evaluation set is every other scored game: regular-season rounds from 20 on, and any
    playoff game. No game is in both.
    """
    in_fit = (scored["phase"] == REGULAR_SEASON) & (scored["round"] <= FIT_LAST_ROUND)
    return scored[in_fit].reset_index(drop=True), scored[~in_fit].reset_index(drop=True)


def unplayed_fit_games(games: pd.DataFrame, season: int) -> tuple[int, int]:
    """(unplayed, scheduled) regular-season games of rounds 1 to ``FIT_LAST_ROUND``."""
    fit_games = games[
        (games["season"] == season)
        & (games["phase"] == REGULAR_SEASON)
        & (games["round"] <= FIT_LAST_ROUND)
    ]
    return int((~fit_games["played"]).sum()), len(fit_games)


def rows_sha256(fit: pd.DataFrame) -> str:
    """Digest of the fit rows (game, POOL's probability, outcome): the data the fit saw."""
    text = fit[["game_id", "p_home", "home_won"]].to_csv(index=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_fit(
    pool_log: pd.DataFrame,
    games: pd.DataFrame,
    season: int,
    manual_pushes: Sequence[datetime],
    out: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Fit c on rounds 1-19 and freeze it in ``out``. Writes nothing when it refuses."""
    if out.exists() and not force:
        raise StageRefused(f"{out} exists: the fit is frozen (--force overwrites it)")
    unplayed, scheduled = unplayed_fit_games(games, season)
    if scheduled == 0:
        raise StageRefused(f"no regular-season games of rounds 1-{FIT_LAST_ROUND} in the schedule")
    if unplayed:
        raise StageRefused(
            f"{unplayed} of {scheduled} regular-season games of rounds 1-{FIT_LAST_ROUND} "
            "are not played yet; the fit waits for all of them"
        )
    fit, _ = split_fit_eval(scored_games(pool_log, games, season, manual_pushes))
    if fit.empty:
        raise StageRefused(f"POOL has no scored rows for rounds 1-{FIT_LAST_ROUND}")
    payload: dict[str, Any] = {
        "stage": "fit",
        "season": season,
        "c": fit_c(fit["p_home"].to_numpy(), fit["home_won"].to_numpy()),
        "c_bounds": list(C_BOUNDS),
        "n_games": len(fit),
        "scheduled_games": scheduled,
        "first_round": int(fit["round"].min()),
        "last_round": int(fit["round"].max()),
        "fit_rows_sha256": rows_sha256(fit),
        "pool_model_versions": sorted(set(fit["model_version"].astype(str))),
        "eurohoops_version": version("eurohoops"),
    }
    write_json(out, payload)
    return payload


def run_eval(  # noqa: PLR0917 -- one stage's inputs and output
    pool_log: pd.DataFrame,
    games: pd.DataFrame,
    season: int,
    manual_pushes: Sequence[datetime],
    fit_path: Path,
    out: Path,
) -> dict[str, Any]:
    """Score POOL-c with the frozen c on every game after the fit set, and write ``out``."""
    if not fit_path.exists():
        raise StageRefused(f"{fit_path} not found: run the fit stage first")
    frozen = json.loads(fit_path.read_text(encoding="utf-8"))
    fit, evaluation = split_fit_eval(scored_games(pool_log, games, season, manual_pushes))
    if rows_sha256(fit) != frozen["fit_rows_sha256"]:
        raise StageRefused("the fit rows differ from those the frozen fit saw; not evaluating")
    c = float(frozen["c"])
    season_rounds = evaluation.loc[evaluation["phase"] == REGULAR_SEASON, "round"]
    gap: dict[str, Any]
    if evaluation.empty:
        gap = {
            "n": 0,
            "mean_diff": None,
            "ci_lo": None,
            "ci_hi": None,
            "resamples": GATE_RESAMPLES,
            "seed": GATE_SEED,
            "pass": False,
        }
    else:
        gap = paired_gap(evaluation["p_home"].to_numpy(), evaluation["home_won"].to_numpy(), c)
    payload: dict[str, Any] = {
        "stage": "eval",
        "season": season,
        "rule": RULE,
        "c": c,
        "fit_rows_sha256": frozen["fit_rows_sha256"],
        "first_round": int(season_rounds.min()) if len(season_rounds) else None,
        "last_round": int(season_rounds.max()) if len(season_rounds) else None,
        **gap,
    }
    write_json(out, payload)
    return payload
