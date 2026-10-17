"""ELOC protocol v1 (docs/models/elo_calibrated.md): nine rolling-origin folds, a two-parameter
logistic recalibration of live Elo, no grid, run once.

Fold s is scored with ``(a, b)`` fitted on the scored EuroLeague games of seasons ``fit_from`` to
s-1 only. Elo is replayed from the first warm-up season with the fixed live parameters, and a
game's Elo difference uses only games tipped off before it. Scored games: the fold seasons,
played, not forfeit, not neutral. The paired comparison is game-weighted over whole-season
resamples (``m7_backtest.cluster_bootstrap_ci``), as ELOR's is.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import expit

from eurohoops.config import ElocCv
from eurohoops.eval.common import round6
from eurohoops.eval.m7_backtest import cluster_bootstrap_ci
from eurohoops.eval.metrics import ece, per_game_log_loss
from eurohoops.models import elo
from eurohoops.models.elo import FloatArray
from eurohoops.models.elo_cal import Calibration, apply, elo_logit, fit


@dataclass(frozen=True)
class ElocContext:
    games: pd.DataFrame  # tip-off order, warm-up start to the last season the run needs
    season: np.ndarray
    elo_diff: FloatArray  # Elo's pre-game difference, home-court advantage included
    x: FloatArray  # logit(p_elo)
    scored: np.ndarray  # played, not forfeit, not neutral (any season in the replay)
    home_won: FloatArray


def _scored(games: pd.DataFrame) -> np.ndarray:
    played = games["played"].to_numpy(dtype=bool)
    forfeit = games["forfeit"].to_numpy(dtype=bool)
    neutral = games["neutral"].to_numpy(dtype=bool)
    mask: np.ndarray = played & ~forfeit & ~neutral
    return mask


def build_context(games: pd.DataFrame, spec: ElocCv) -> ElocContext:
    """Elo replayed from ``spec.elo_warmup[0]`` to the last season any fit or fold needs."""
    last = max(spec.folds[-1], spec.live_fit_seasons[1])
    part = games[games["season"].between(spec.elo_warmup[0], last)]
    part = part.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    diff = elo.replay(elo.prepare(part), spec.elo_params)
    margin = (part["home_score"] - part["away_score"]).fillna(0).to_numpy(dtype=np.float64)
    return ElocContext(
        games=part,
        season=part["season"].astype(int).to_numpy(),
        elo_diff=diff,
        x=elo_logit(diff),
        scored=_scored(part),
        home_won=(margin > 0).astype(np.float64),
    )


def fold_train(ctx: ElocContext, spec: ElocCv, fold: int) -> np.ndarray:
    """Fold ``fold``'s fit window: scored games of ``fit_from`` up to, not including, ``fold``."""
    return ctx.scored & (ctx.season >= spec.fit_from) & (ctx.season < fold)


def fold_calibration(ctx: ElocContext, spec: ElocCv, fold: int) -> Calibration:
    train = fold_train(ctx, spec, fold)
    return fit(ctx.x[train], ctx.home_won[train])


def _metrics(
    p: FloatArray, ctx: ElocContext, mask: np.ndarray, folds: tuple[int, ...]
) -> dict[str, Any]:
    y = ctx.home_won[mask]
    pm = p[mask]
    season = ctx.season[mask]
    loss = per_game_log_loss(pm, y)
    brier = (pm - y) ** 2
    per_season = {
        str(s): {
            "games": int((season == s).sum()),
            "log_loss": round6(loss[season == s].mean()),
            "brier": round6(brier[season == s].mean()),
        }
        for s in folds
        if (season == s).any()
    }
    return {
        "n": int(mask.sum()),
        "log_loss": round6(loss.mean()),
        "brier": round6(brier.mean()),
        "ece": round6(ece(pm, y)),
        "per_season": per_season,
    }


def run_cv(
    games: pd.DataFrame,
    *,
    spec: ElocCv,
    git_head: str,
    baseline_log_loss: float | None = None,
    baseline_games: int | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Runs the folds. Raises before anything is returned (so before anything is written) when
    the scored games or Elo's pooled log loss differ from ELOR's report; ``None`` skips a check."""
    ctx = build_context(games, spec)
    p_elo = expit(ctx.x)  # == elo.win_probability(d): the same logistic in the rating difference
    p_cal = np.full(len(ctx.x), np.nan)
    fits: dict[int, Calibration] = {}
    for fold in spec.folds:
        cal = fold_calibration(ctx, spec, fold)
        fits[fold] = cal
        in_fold = ctx.scored & (ctx.season == fold)
        p_cal[in_fold] = apply(cal, ctx.elo_diff[in_fold])

    mask = ctx.scored & np.isin(ctx.season, spec.folds)
    y = ctx.home_won[mask]
    cluster = pd.factorize(ctx.season[mask], sort=True)[0].astype(np.int64)
    loss_elo = per_game_log_loss(p_elo[mask], y)
    loss_cal = per_game_log_loss(p_cal[mask], y)
    if baseline_games is not None and int(mask.sum()) != baseline_games:
        raise ValueError(f"ELOC scores {int(mask.sum())} games; ELOR's report has {baseline_games}")
    if baseline_log_loss is not None and round6(loss_elo.mean()) != baseline_log_loss:
        raise ValueError(
            f"Elo's log loss on the scored games is {round6(loss_elo.mean())}; "
            f"ELOR's report has {baseline_log_loss}"
        )
    mean, low, high = cluster_bootstrap_ci(
        loss_cal - loss_elo, cluster, spec.bootstrap_resamples, spec.bootstrap_seed
    )
    margin = spec.shadow_log_loss_margin
    criteria = {
        "below_elo": bool(loss_cal.mean() < loss_elo.mean()),
        "non_inferior": bool(high < margin),
        "worth_a_version": bool(mean <= -margin),
    }

    live_lo, live_hi = spec.live_fit_seasons
    live_train = ctx.scored & (ctx.season >= live_lo) & (ctx.season <= live_hi)
    live = fit(ctx.x[live_train], ctx.home_won[live_train])

    report: dict[str, Any] = {
        "model": "eloc",
        "protocol": spec.protocol,
        "git_head": git_head,
        "elo_params": asdict(spec.elo_params),
        "elo_warmup": list(spec.elo_warmup),
        "folds": list(spec.folds),
        "fit_from": spec.fit_from,
        "calibration": "p = sigmoid(a + b * logit(p_elo)); unpenalised maximum likelihood",
        "bootstrap": {"resamples": spec.bootstrap_resamples, "seed": spec.bootstrap_seed},
        "scored_games": int(mask.sum()),
        "per_fold": {
            str(f): {
                "fit_seasons": [spec.fit_from, f - 1],
                "fit_games": int(fold_train(ctx, spec, f).sum()),
                "scored_games": int((ctx.scored & (ctx.season == f)).sum()),
                "a": round6(fits[f].a),
                "b": round6(fits[f].b),
                "iterations": fits[f].iterations,
            }
            for f in spec.folds
        },
        "elo": _metrics(p_elo, ctx, mask, spec.folds),
        "eloc": _metrics(p_cal, ctx, mask, spec.folds),
        "eloc_minus_elo": {
            "mean": round6(mean),
            "ci95": [round6(low), round6(high)],
        },
        "shadow_criteria": {**criteria, "all": all(criteria.values())},
        "live_fit": {
            "a": round6(live.a),
            "b": round6(live.b),
            "seasons": [live_lo, live_hi],
            "games": live.n,
            "iterations": live.iterations,
        },
    }
    detail = ctx.games.loc[mask, ["game_id", "season", "home", "away"]].copy()
    detail["home_won"] = y.astype(int)
    detail["p_elo"] = np.round(p_elo[mask], 6)
    detail["p_eloc"] = np.round(p_cal[mask], 6)
    return report, detail.reset_index(drop=True)


def cv_check(games: pd.DataFrame, spec: ElocCv) -> dict[str, Any]:
    """Read-only: game counts per fold (fit and scored) and the live fit's game count. It fits
    nothing and scores nothing."""
    ctx = build_context(games, spec)
    per_fold = {
        str(f): {
            "fit_seasons": [spec.fit_from, f - 1],
            "fit_games": int(fold_train(ctx, spec, f).sum()),
            "scored_games": int((ctx.scored & (ctx.season == f)).sum()),
        }
        for f in spec.folds
    }
    live_lo, live_hi = spec.live_fit_seasons
    live = ctx.scored & (ctx.season >= live_lo) & (ctx.season <= live_hi)
    return {
        "elo_replay_games": len(ctx.games),
        "per_fold": per_fold,
        "live_fit": {"seasons": [live_lo, live_hi], "games": int(live.sum())},
    }
