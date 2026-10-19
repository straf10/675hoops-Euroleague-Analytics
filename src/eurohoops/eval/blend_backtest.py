"""Candidate ``blend``: live Elo margin mixed with a ridge margin; Normal win probability.

Walk-forward rolling origin. For each scored fold season ``s``, every choice is made from seasons
before ``s`` only:

- the live Elo margin scale (``elo.fit_margin_scale``) on seasons ``FIT_FROM`` to ``s - 1``;
- the blend weight ``w`` on the grid ``WEIGHT_GRID``: the one with the lowest log loss over seasons
  ``FIT_FROM`` to ``s - 1``, each weight scored with its own sigma (below);
- the sigma of the Normal link: RMS residual of the blended margin over the previous
  ``SIGMA_WINDOW`` seasons;
- ``blend+roster`` (optional, needs the roster and box inputs): a preseason roster term
  ``beta * (share_home - share_away)`` added to the margin in the regular-season rounds
  ``1..EARLY_ROUNDS``. ``share`` is the minutes-weighted returning share of a club's season-start
  roster (``models/continuity.py``); ``beta`` is the least-squares slope on the earlier seasons'
  early-round residuals. Outside those rounds the term is zero.

The ridge margin (``models/ridge_margin.py``) is refitted per game day on earlier games only.
Live Elo (logistic link, live parameters) is the baseline, scored on the same games.
Docs: docs/models/candidate_elo_blend.md.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import special, stats

from eurohoops.config import ELOR_ELO_PARAMS
from eurohoops.eval.metrics import paired_bootstrap_ci_clustered, per_game_log_loss
from eurohoops.models.continuity import club_share, player_continuity, season_start_roster
from eurohoops.models.elo import FloatArray, prepare, replay
from eurohoops.models.ridge_margin import RidgeParams, ridge_margin_forecast

WEIGHT_GRID = tuple(round(0.1 * i, 1) for i in range(11))  # blend weight on Elo's margin
RIDGE = RidgeParams(half_life_days=480.0, lam=8.0)
FIT_FROM = 2009  # first season used to fit Elo's margin scale, the weight and the baselines
SIGMA_WINDOW = 4  # seasons of residuals behind each fold's sigma
EARLY_ROUNDS = 10  # regular-season rounds that carry the roster term
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
    early: FloatArray  # 1.0 for regular-season rounds 1..EARLY_ROUNDS
    won: FloatArray
    margin: FloatArray
    p_live: FloatArray
    mu_live: FloatArray
    p_elo_normal: FloatArray
    p_blend: FloatArray
    mu_blend: FloatArray
    p_roster: FloatArray
    mu_roster: FloatArray
    p_b0: FloatArray
    mu_b0: FloatArray


def _rated_frame(games: pd.DataFrame) -> pd.DataFrame:
    frame = games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    frame["rated"] = (frame["played"] & ~frame["forfeit"]).astype(bool)
    frame["margin"] = (frame["home_score"] - frame["away_score"]).astype("float64")
    return frame


def _normal_prob(mu: FloatArray, sigma: float) -> FloatArray:
    return np.clip(stats.norm.cdf(mu / sigma), PROB_FLOOR, 1.0 - PROB_FLOOR)


def _shares(
    minutes: pd.DataFrame, roster: pd.DataFrame, games: pd.DataFrame, season: int
) -> dict[str, float]:
    """Each club's returning-minutes share for ``season`` (season-start roster, last season's
    minutes). Clubs with no share (new clubs) get the season's mean share."""
    start = season_start_roster(roster, games, season)
    clubs = club_share(player_continuity(minutes, start, season))
    if clubs.empty:
        return {}
    mean = float(clubs["share"].mean())
    out = dict(zip(clubs["team"].astype(str), clubs["share"].astype(float), strict=True))
    for team in set(games["home"]).union(games["away"]):
        out.setdefault(str(team), mean)
    return out


def roster_term_inputs(
    frame: pd.DataFrame, minutes: pd.DataFrame, roster: pd.DataFrame, seasons: range
) -> FloatArray:
    """Per game of ``frame``: share_home - share_away from the season-start rosters; 0 where the
    season has no roster data."""
    x = np.zeros(len(frame), dtype=np.float64)
    season = frame["season"].to_numpy()
    for s in seasons:
        rows = np.flatnonzero(season == s)
        if not len(rows):
            continue
        shares = _shares(minutes, roster, frame, s)
        if not shares:
            continue
        home = frame["home"].to_numpy()[rows]
        away = frame["away"].to_numpy()[rows]
        x[rows] = [
            shares.get(str(h), 0.5) - shares.get(str(a), 0.5)
            for h, a in zip(home, away, strict=True)
        ]
    return x


def _loss_normal(mu: FloatArray, sigma: float, won: FloatArray) -> float:
    p = _normal_prob(mu, sigma)
    return float(per_game_log_loss(p, won).mean())


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


def run_blend(
    games: pd.DataFrame,
    folds: tuple[int, ...] = FOLDS,
    minutes: pd.DataFrame | None = None,
    roster: pd.DataFrame | None = None,
) -> tuple[Scored, dict[str, Any]]:
    """Walk-forward forecasts for the scored games of ``folds`` (rated games only).

    Without ``minutes`` and ``roster`` the roster term is zero, so ``blend+roster`` equals
    ``blend``.
    """
    frame = _rated_frame(games)
    d = replay(prepare(frame), ELO_LIVE)  # pre-game Elo differences; each uses earlier games only
    rated = frame["rated"].to_numpy(dtype=bool)
    season = frame["season"].to_numpy()
    margin = frame["margin"].to_numpy(dtype=np.float64)
    won = (margin > 0).astype(np.float64)
    neutral = frame["neutral"].to_numpy(dtype=bool)
    is_rs = (frame["phase"] == "RS").to_numpy() & (frame["round"].to_numpy() <= EARLY_ROUNDS)
    early = rated & is_rs
    lo = min(FIT_FROM, min(folds) - SIGMA_WINDOW)
    ridge_mu = ridge_margin_forecast(frame, RIDGE, rated & (season >= lo) & (season <= max(folds)))
    if minutes is not None and roster is not None:
        x_roster = roster_term_inputs(frame, minutes, roster, range(FIT_FROM, max(folds) + 1))
    else:
        x_roster = np.zeros(len(frame), dtype=np.float64)
    parts: dict[str, list[FloatArray]] = {k: [] for k in Scored.__dataclass_fields__}
    chosen: dict[str, dict[str, float]] = {}
    for s in folds:
        fit = rated & (season >= FIT_FROM) & (season < s)
        window = rated & (season >= s - SIGMA_WINDOW) & (season < s)
        scale = float(np.dot(d[fit], d[fit]) / np.dot(d[fit], margin[fit]))
        elo_fit = d / scale
        best_w, best_loss = WEIGHT_GRID[0], np.inf
        for w in WEIGHT_GRID:
            mu_w = w * elo_fit + (1.0 - w) * ridge_mu
            sigma_w = float(np.sqrt(np.mean((margin[window] - mu_w[window]) ** 2)))
            loss = _loss_normal(mu_w[fit], sigma_w, won[fit])
            if loss < best_loss:
                best_w, best_loss = w, loss
        mu_all = best_w * elo_fit + (1.0 - best_w) * ridge_mu
        sigma = float(np.sqrt(np.mean((margin[window] - mu_all[window]) ** 2)))
        # Roster slope: earlier seasons' early-round residuals of the chosen blend, no intercept.
        fit_early = fit & early
        x = x_roster[fit_early]
        resid = margin[fit_early] - mu_all[fit_early]
        beta = float(np.dot(x, resid) / np.dot(x, x)) if np.dot(x, x) > 0 else 0.0
        mu_roster_all = mu_all + beta * x_roster * early
        sigma_roster = float(np.sqrt(np.mean((margin[window] - mu_roster_all[window]) ** 2)))
        rows = rated & (season == s)
        base = fit & ~neutral
        rate = float(np.mean(margin[base] > 0))
        home_margin = float(np.mean(margin[base]))
        chosen[str(s)] = {"weight": best_w, "beta": round(beta, 6), "sigma": round(sigma, 6)}
        values = {
            "season": np.full(int(rows.sum()), float(s)),
            "early": early[rows].astype(np.float64),
            "won": won[rows],
            "margin": margin[rows],
            "p_live": special.expit(d[rows] * np.log(10.0) / 400.0),
            "mu_live": elo_fit[rows],
            "p_elo_normal": _normal_prob(
                elo_fit[rows], float(np.sqrt(np.mean((margin[window] - elo_fit[window]) ** 2)))
            ),
            "p_blend": _normal_prob(mu_all[rows], sigma),
            "mu_blend": mu_all[rows],
            "p_roster": _normal_prob(mu_roster_all[rows], sigma_roster),
            "mu_roster": mu_roster_all[rows],
            "p_b0": np.where(neutral[rows], 0.5, rate).astype(np.float64),
            "mu_b0": np.where(neutral[rows], 0.0, home_margin).astype(np.float64),
        }
        for key, value in values.items():
            parts[key].append(np.asarray(value, dtype=np.float64))
    scored = Scored(**{k: np.concatenate(v) for k, v in parts.items()})
    return scored, _report(scored, folds, chosen)


def _forecasts(scored: Scored) -> dict[str, tuple[FloatArray, FloatArray]]:
    """Model name -> (win probability, expected margin) for every scored game."""
    return {
        "live_elo": (scored.p_live, scored.mu_live),
        "elo_normal": (scored.p_elo_normal, scored.mu_live),
        "blend": (scored.p_blend, scored.mu_blend),
        "blend_roster": (scored.p_roster, scored.mu_roster),
        "b0": (scored.p_b0, scored.mu_b0),
    }


def _paired(diff: FloatArray, clusters: FloatArray) -> dict[str, Any]:
    mean, low, high = paired_bootstrap_ci_clustered(
        diff, clusters.astype(int).tolist(), BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED
    )
    return {"mean": round(mean, 6), "ci95": [round(low, 6), round(high, 6)]}


def _block(scored: Scored, keep: np.ndarray) -> dict[str, Any]:
    """Pooled metrics and paired CIs over the games where ``keep`` is True."""
    forecasts = _forecasts(scored)
    won, margin = scored.won[keep], scored.margin[keep]
    seasons = scored.season[keep]
    pooled = {name: _metrics(p[keep], mu[keep], won, margin) for name, (p, mu) in forecasts.items()}
    loss = {name: per_game_log_loss(p[keep], won) for name, (p, _) in forecasts.items()}
    mae = {name: np.abs(mu[keep] - margin) for name, (_, mu) in forecasts.items()}
    paired = {
        "blend_minus_live": {
            "log_loss": _paired(loss["blend"] - loss["live_elo"], seasons),
            "margin_mae": _paired(mae["blend"] - mae["live_elo"], seasons),
        },
        "blend_roster_minus_live": {
            "log_loss": _paired(loss["blend_roster"] - loss["live_elo"], seasons),
            "margin_mae": _paired(mae["blend_roster"] - mae["live_elo"], seasons),
        },
        "blend_roster_minus_blend": {
            "log_loss": _paired(loss["blend_roster"] - loss["blend"], seasons),
            "margin_mae": _paired(mae["blend_roster"] - mae["blend"], seasons),
        },
    }
    return {"games": int(keep.sum()), "pooled": pooled, "paired": paired}


def _report(
    scored: Scored, folds: tuple[int, ...], chosen: dict[str, dict[str, float]]
) -> dict[str, Any]:
    everything = np.ones(len(scored.won), dtype=bool)
    early = scored.early.astype(bool)
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
    per_season_early = {
        str(s): {
            name: _metrics(
                p[(seasons == s) & early],
                mu[(seasons == s) & early],
                scored.won[(seasons == s) & early],
                scored.margin[(seasons == s) & early],
            )
            for name, (p, mu) in forecasts.items()
        }
        for s in folds
    }
    return {
        "seasons": list(folds),
        "blend_weight_grid": list(WEIGHT_GRID),
        "chosen_by_season": chosen,
        "ridge": {"half_life_days": RIDGE.half_life_days, "lam": RIDGE.lam},
        "early_rounds": EARLY_ROUNDS,
        "all": _block(scored, everything),
        "early": _block(scored, early),
        "per_season": per_season,
        "per_season_early": per_season_early,
    }
