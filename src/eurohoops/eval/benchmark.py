"""MKT benchmark: the bookmakers' pre-tip home-win probability against each model (B1).

MKT is read at report time from the odds log (``forecasts._market_calls``): each game's latest
snapshot fetched strictly before tip-off, de-vigged by ``odds.py``. It is never written to
``predictions/`` and no model may import this module: MKT feeds no model without its own gate
(``docs/models/mkt.md``). Nothing here writes to ``predictions/`` or ``odds/``.

Per model, on the games where both the model and MKT have a pre-tip row:
- mean per-game log loss and Brier of each, their gap (model minus MKT) and a paired bootstrap
  95% CI of that gap;
- the encompassing test: a logistic regression of home win on an intercept, logit(MKT) and
  logit(model), with 95% CIs from the inverse Fisher information (normal approximation);
- the same scores by snapshot lead time (tip-off minus the snapshot's fetch time).
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import expit

from eurohoops.eval.forecasts import MKT_KEY, _calls, _market_calls
from eurohoops.eval.metrics import per_game_log_loss

CLIP = 1e-6  # the logit clip used across the programme (docs/models/pool.md)
Z95 = 1.959963984540054
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 2026
MIN_ENCOMPASSING_GAMES = 10  # below this the three-coefficient fit and its CIs are not reported
MAX_ITER = 100
# Snapshot lead time in hours before tip-off; a bucket includes its lower bound, excludes its upper.
LEAD_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("<3 h", 0.0, 3.0),
    ("3-24 h", 3.0, 24.0),
    (">=24 h", 24.0, float("inf")),
)


def logit(p: np.ndarray) -> np.ndarray:
    q = np.clip(p, CLIP, 1.0 - CLIP)
    return np.asarray(np.log(q / (1.0 - q)), dtype=np.float64)


def lead_bucket(hours: float) -> str:
    for label, lo, hi in LEAD_BUCKETS:
        if lo <= hours < hi:
            return label
    raise ValueError(f"lead time {hours} h is outside every bucket")


def logit_fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Maximum-likelihood logistic coefficients (Newton) and their standard errors."""
    beta = np.zeros(X.shape[1])
    for _ in range(MAX_ITER):
        mu = expit(X @ beta)
        info = (X * (mu * (1.0 - mu))[:, None]).T @ X
        step = np.linalg.solve(info, X.T @ (y - mu))
        beta = beta + step
        if float(np.max(np.abs(step))) < 1e-10:
            break
    else:
        raise RuntimeError("logistic fit did not converge")
    mu = expit(X @ beta)
    info = (X * (mu * (1.0 - mu))[:, None]).T @ X
    return beta, np.sqrt(np.diag(np.linalg.inv(info)))


def encompassing(home_won: np.ndarray, p_market: np.ndarray, p_model: np.ndarray) -> dict[str, Any]:
    """Home win on logit(MKT) and logit(model). ``model_adds_information`` is declared when the
    logit(model) coefficient's 95% CI excludes 0."""
    X = np.column_stack([np.ones(len(home_won)), logit(p_market), logit(p_model)])
    beta, se = logit_fit(X, home_won)
    coef = {
        name: {
            "coef": round(float(b), 6),
            "lo": round(float(b - Z95 * s), 6),
            "hi": round(float(b + Z95 * s), 6),
        }
        for name, b, s in zip(("intercept", "mkt", "model"), beta, se, strict=True)
    }
    model = coef["model"]
    return {
        "n": len(home_won),
        **coef,
        "model_adds_information": bool(model["lo"] > 0 or model["hi"] < 0),
    }


def paired_gap_ci(model_loss: np.ndarray, mkt_loss: np.ndarray) -> list[float]:
    """Paired bootstrap 95% CI of the mean of (model - MKT) per game, seeded."""
    gap = model_loss - mkt_loss
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(gap), size=(BOOTSTRAP_RESAMPLES, len(gap)))
    lo, hi = np.percentile(gap[idx].mean(axis=1), [2.5, 97.5])
    return [round(float(lo), 6), round(float(hi), 6)]


def _scores(pairs: pd.DataFrame) -> dict[str, Any]:
    """Log loss and Brier of the model and MKT on ``pairs`` (``p_home``, ``p_market``)."""
    if pairs.empty:
        return {"n": 0, "log_loss": None, "brier": None}
    home_won = (pairs["margin"].to_numpy(dtype=np.float64) > 0).astype(np.float64)
    p_model = pairs["p_home"].to_numpy(dtype=np.float64)
    p_mkt = pairs["p_market"].to_numpy(dtype=np.float64)
    loss_model = per_game_log_loss(p_model, home_won)
    loss_mkt = per_game_log_loss(p_mkt, home_won)
    brier_model = (p_model - home_won) ** 2
    brier_mkt = (p_mkt - home_won) ** 2
    return {
        "n": len(pairs),
        "log_loss": {
            "model": round(float(loss_model.mean()), 6),
            "mkt": round(float(loss_mkt.mean()), 6),
        },
        "brier": {
            "model": round(float(brier_model.mean()), 6),
            "mkt": round(float(brier_mkt.mean()), 6),
        },
    }


def _model_block(calls: pd.DataFrame, market: pd.DataFrame) -> dict[str, Any]:
    """One model's benchmark: its pre-tip rows joined with MKT's pre-tip row of the same game."""
    pairs = calls[["game_id", "p_home", "margin"]].merge(
        market[["game_id", "p_home", "lead_hours"]].rename(columns={"p_home": "p_market"}),
        on="game_id",
    )
    pairs = pairs.assign(bucket=[lead_bucket(h) for h in pairs["lead_hours"]])
    overall = _scores(pairs)
    if len(pairs):
        home_won = (pairs["margin"].to_numpy(dtype=np.float64) > 0).astype(np.float64)
        loss = per_game_log_loss(pairs["p_home"].to_numpy(dtype=np.float64), home_won)
        loss_mkt = per_game_log_loss(pairs["p_market"].to_numpy(dtype=np.float64), home_won)
        overall["gap_ci95"] = {
            "log_loss": paired_gap_ci(loss, loss_mkt),
            "brier": paired_gap_ci(
                (pairs["p_home"].to_numpy(dtype=np.float64) - home_won) ** 2,
                (pairs["p_market"].to_numpy(dtype=np.float64) - home_won) ** 2,
            ),
        }
        if len(pairs) >= MIN_ENCOMPASSING_GAMES:  # three coefficients need more games than that
            overall["encompassing"] = encompassing(
                home_won,
                pairs["p_market"].to_numpy(dtype=np.float64),
                pairs["p_home"].to_numpy(dtype=np.float64),
            )
    by_lead = []
    for label, _, _ in LEAD_BUCKETS:
        scores = _scores(pairs[pairs["bucket"] == label])
        by_lead.append({"bucket": label, **scores})
    return {**overall, "by_lead": by_lead}


def benchmark(
    logs: Mapping[str, Path | None],
    games: pd.DataFrame,
    odds_log: Path,
    season: int,
    manual_pushes: Sequence[datetime] = (),
) -> dict[str, Any]:
    """MKT against each model in ``logs`` (key -> prediction log; ``None`` skips a model).

    Games are the finished games of ``season`` that have a pre-tip snapshot; a model's pairs are
    the games it also logged before tip-off. Keys are the source's model keys (``MKT_KEY`` is
    the benchmark's own name, never a log key).
    """
    market = _market_calls(odds_log, games, season)
    lead = (
        pd.to_datetime(market["tipoff_utc"], utc=True)
        - pd.to_datetime(market["fetched_at_utc"], utc=True)
    ).dt.total_seconds() / 3600
    market = market.assign(lead_hours=lead.to_numpy(dtype=np.float64))
    models = {}
    for key, path in logs.items():
        if path is None or key == MKT_KEY:
            continue
        calls, _ = _calls(path, games, season, manual_pushes)
        models[key] = _model_block(calls, market)
    return {
        "buckets": [{"label": label, "lo": lo, "hi": hi} for label, lo, hi in LEAD_BUCKETS],
        "market_games": len(market),
        "models": models,
    }
