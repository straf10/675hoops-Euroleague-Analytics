"""Candidate ``blend``: live Elo margin averaged with a ridge margin model; Normal win probability.

Walk-forward rolling origin. For each fold season ``s`` (scored), everything is fitted on seasons
before ``s``:

- the live Elo margin scale (``elo.fit_margin_scale``) on seasons ``FIT_FROM`` to ``s - 1``;
- the blend's margin sigma: RMS residual of the blended margin over the previous ``SIGMA_WINDOW``
  seasons (their residuals come from walk-forward forecasts, so they are out of sample too);
- the ridge model (``models/ridge_margin.py``) is fitted per game day on earlier games only.

The candidate is ``mu = w * elo_margin + (1 - w) * ridge_margin`` with ``w = BLEND_WEIGHT`` and
``P(home win) = Phi(mu / sigma)``. Live Elo (logistic link, live parameters) is the baseline, scored
on the same games. Docs: docs/models/candidate_elo_blend.md.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import special, stats

from eurohoops.config import ELOR_ELO_PARAMS
from eurohoops.eval.metrics import paired_bootstrap_ci_clustered, per_game_log_loss
from eurohoops.models.elo import FloatArray, prepare, replay
from eurohoops.models.ridge_margin import RidgeParams, ridge_margin_forecast

BLEND_WEIGHT = 0.5  # weight of Elo's margin; the rest is the ridge margin
RIDGE = RidgeParams(half_life_days=480.0, lam=8.0)
FIT_FROM = 2009  # first season used to fit Elo's margin scale and the baselines
SIGMA_WINDOW = 4  # seasons of residuals behind each fold's sigma
FOLDS = tuple(range(2015, 2026))  # scored seasons (2026 is live; not scored here)
WARMUP_FOLDS = tuple(range(2010, 2015))  # the same protocol on earlier seasons, as a second look
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261019
PROB_FLOOR = 1e-9
ELO_LIVE = ELOR_ELO_PARAMS  # the published flagship's parameters (k 20, hca 90, reversion 0.25)


@dataclass(frozen=True)
class Scored:
    """Per-game arrays of the scored games, in tip-off order."""

    season: FloatArray
    won: FloatArray
    margin: FloatArray
    p_live: FloatArray
    p_elo_normal: FloatArray
    p_blend: FloatArray
    mu_live: FloatArray
    mu_blend: FloatArray
    p_b0: FloatArray
    mu_b0: FloatArray


def _rated_frame(games: pd.DataFrame) -> pd.DataFrame:
    frame = games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    frame["rated"] = (frame["played"] & ~frame["forfeit"]).astype(bool)
    frame["margin"] = (frame["home_score"] - frame["away_score"]).astype("float64")
    return frame


def _normal_prob(mu: FloatArray, sigma: float) -> FloatArray:
    return np.clip(stats.norm.cdf(mu / sigma), PROB_FLOOR, 1.0 - PROB_FLOOR)


def _metrics(p: FloatArray, mu: FloatArray, won: FloatArray, margin: FloatArray) -> dict[str, Any]:
    if not len(won):
        return {"n": 0, "log_loss": None, "brier": None, "accuracy": None, "margin_mae": None}
    return {
        "n": len(won),
        "log_loss": round(float(per_game_log_loss(p, won).mean()), 6),
        "brier": round(float(np.mean((p - won) ** 2)), 6),
        "accuracy": round(float(np.mean((p >= 0.5) == (won == 1.0))), 6),
        "margin_mae": round(float(np.mean(np.abs(mu - margin))), 6),
    }


def run_blend(games: pd.DataFrame, folds: tuple[int, ...] = FOLDS) -> tuple[Scored, dict[str, Any]]:
    """Walk-forward forecasts for the scored games of ``folds`` (rated games only)."""
    frame = _rated_frame(games)
    arrays = prepare(frame)
    d = replay(arrays, ELO_LIVE)  # pre-game Elo differences; each uses games before it only
    rated = frame["rated"].to_numpy(dtype=bool)
    season = frame["season"].to_numpy()
    margin = frame["margin"].to_numpy(dtype=np.float64)
    neutral = frame["neutral"].to_numpy(dtype=bool)
    lo = min(folds) - SIGMA_WINDOW
    needed = rated & (season >= lo) & (season <= max(folds))
    ridge_mu = ridge_margin_forecast(frame, RIDGE, needed)
    scored_rows = rated & np.isin(season, folds)
    parts: dict[str, list[FloatArray]] = {k: [] for k in Scored.__dataclass_fields__}
    for s in folds:
        fit = rated & (season >= FIT_FROM) & (season < s)
        scale = float(np.dot(d[fit], d[fit]) / np.dot(d[fit], margin[fit]))
        rows = scored_rows & (season == s)
        win = (margin[rows] > 0).astype(np.float64)
        prior = rated & (season >= s - SIGMA_WINDOW) & (season < s)
        blend_prior = BLEND_WEIGHT * d[prior] / scale + (1.0 - BLEND_WEIGHT) * ridge_mu[prior]
        sigma = float(np.sqrt(np.mean((margin[prior] - blend_prior) ** 2)))
        elo_prior = d[prior] / scale
        sigma_elo = float(np.sqrt(np.mean((margin[prior] - elo_prior) ** 2)))
        mu_live = d[rows] / scale
        mu_blend = BLEND_WEIGHT * mu_live + (1.0 - BLEND_WEIGHT) * ridge_mu[rows]
        base = fit & ~neutral
        rate = float(np.mean(margin[base] > 0))
        home_margin = float(np.mean(margin[base]))
        p_b0 = np.where(neutral[rows], 0.5, rate)
        mu_b0 = np.where(neutral[rows], 0.0, home_margin)
        values = {
            "season": np.full(len(win), float(s)),
            "won": win,
            "margin": margin[rows],
            "p_live": special.expit(d[rows] * np.log(10.0) / 400.0),
            "p_elo_normal": _normal_prob(mu_live, sigma_elo),
            "p_blend": _normal_prob(mu_blend, sigma),
            "mu_live": mu_live,
            "mu_blend": mu_blend,
            "p_b0": p_b0.astype(np.float64),
            "mu_b0": mu_b0.astype(np.float64),
        }
        for key, value in values.items():
            parts[key].append(np.asarray(value, dtype=np.float64))
    scored = Scored(**{k: np.concatenate(v) for k, v in parts.items()})
    return scored, _report(scored, folds)


def _forecasts(scored: Scored) -> dict[str, tuple[FloatArray, FloatArray]]:
    """Model name -> (win probability, expected margin) for every scored game."""
    return {
        "live_elo": (scored.p_live, scored.mu_live),
        "elo_normal": (scored.p_elo_normal, scored.mu_live),
        "blend": (scored.p_blend, scored.mu_blend),
        "b0": (scored.p_b0, scored.mu_b0),
    }


def _report(scored: Scored, folds: tuple[int, ...]) -> dict[str, Any]:
    seasons = scored.season.astype(int)
    forecasts = _forecasts(scored)
    per_season = {
        str(s): {
            name: _metrics(
                p[seasons == s],
                mu[seasons == s],
                scored.won[seasons == s],
                scored.margin[seasons == s],
            )
            for name, (p, mu) in forecasts.items()
        }
        for s in folds
    }
    pooled = {
        name: _metrics(p, mu, scored.won, scored.margin) for name, (p, mu) in forecasts.items()
    }
    loss = {name: per_game_log_loss(p, scored.won) for name, (p, _) in forecasts.items()}
    mae = {name: np.abs(mu - scored.margin) for name, (_, mu) in forecasts.items()}

    def paired(diff: FloatArray) -> dict[str, Any]:
        mean, low, high = paired_bootstrap_ci_clustered(
            diff, seasons.tolist(), BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED
        )
        return {"mean": round(mean, 6), "ci95": [round(low, 6), round(high, 6)]}

    return {
        "seasons": list(folds),
        "games": len(scored.won),
        "blend_weight": BLEND_WEIGHT,
        "ridge": {"half_life_days": RIDGE.half_life_days, "lam": RIDGE.lam},
        "per_season": per_season,
        "pooled": pooled,
        "paired_blend_minus_live": {
            "log_loss": paired(loss["blend"] - loss["live_elo"]),
            "margin_mae": paired(mae["blend"] - mae["live_elo"]),
        },
        "paired_elo_normal_minus_live": {
            "log_loss": paired(loss["elo_normal"] - loss["live_elo"]),
            "margin_mae": paired(mae["elo_normal"] - mae["live_elo"]),
        },
    }
