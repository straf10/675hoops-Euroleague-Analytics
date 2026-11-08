"""Residual and reliability diagnostics for the EuroLeague forecasts (research only, never live).

Pure functions. The questions they answer: does a pre-game feature that a model does not use
explain its out-of-sample errors (an encompassing test on P(home win), and an OLS test on the
margin residual), and is each model's P(home win) calibrated overall, per season and per team.

No-lookahead: every feature here reads only games with tip-off strictly before the game it
describes (``rest_features``, the Elo replay) or whole earlier seasons (``pregame_features``).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit

from eurohoops.eval.forecasts import _wilson
from eurohoops.models.elo import EloParams, FloatArray, prepare, replay
from eurohoops.models.rest import rest_features

CLIP = 1e-6  # the offset logit is taken on p clipped to [CLIP, 1 - CLIP]
MAX_ITER = 100
TOL = 1e-10
EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)  # reliability bins: half-open, the last one closed
REGULAR_SEASON = "RS"
PRIOR_SEASON_GAP = 1  # the home-team prior is the previous season only
FEATURES = (
    "home_rest",
    "away_rest",
    "rest_diff",
    "home_short",
    "away_short",
    "home_last7",
    "away_last7",
    "round",
    "is_playoff",
    "month_of_season",
    "confidence",
    "prior_home_edge",
)


@dataclass(frozen=True)
class Fit:
    coef: float  # on the standardized feature
    se: float
    z: float
    p: float
    n: int


def _standardize(feature: FloatArray) -> FloatArray:
    """Zero mean, unit sample sd. A constant feature cannot be tested and raises."""
    sd = float(feature.std(ddof=1))
    if not sd > 0.0:
        raise ValueError("constant feature: nothing to test")
    standardized: FloatArray = (feature - feature.mean()) / sd
    return standardized


def encompassing(p_model: FloatArray, home_won: FloatArray, feature: FloatArray) -> Fit:
    """Logistic regression of ``home_won`` on offset ``logit(p_model)`` and a standardized feature.

    The model's own log-odds enter with coefficient 1 (the offset). The feature's coefficient is
    zero when the feature adds nothing to the model. Newton-Raphson; the Wald test uses the
    inverse Hessian at the solution.
    """
    p = np.clip(np.asarray(p_model, dtype=np.float64), CLIP, 1.0 - CLIP)
    y = np.asarray(home_won, dtype=np.float64)
    offset: FloatArray = np.log(p) - np.log1p(-p)
    x = _standardize(np.asarray(feature, dtype=np.float64))
    design: FloatArray = np.column_stack([np.ones_like(x), x])
    beta: FloatArray = np.zeros(2)
    hess: FloatArray = np.eye(2)
    for _ in range(MAX_ITER):
        mu: FloatArray = expit(offset + design @ beta)
        hess = (design * (mu * (1.0 - mu))[:, None]).T @ design
        step: FloatArray = np.linalg.solve(hess, design.T @ (y - mu))
        beta = beta + step
        if float(np.max(np.abs(step))) < TOL:
            break
    else:
        raise RuntimeError("encompassing logit did not converge")
    se = float(np.sqrt(np.linalg.inv(hess)[1, 1]))
    z = float(beta[1]) / se
    return Fit(
        coef=float(beta[1]),
        se=se,
        z=z,
        p=float(2.0 * stats.norm.sf(abs(z))),
        n=len(y),
    )


def margin_residual_test(residual: FloatArray, feature: FloatArray) -> Fit:
    """OLS of a margin residual (actual minus expected margin) on a standardized feature."""
    r = np.asarray(residual, dtype=np.float64)
    x = _standardize(np.asarray(feature, dtype=np.float64))
    design: FloatArray = np.column_stack([np.ones_like(x), x])
    gram_inv: FloatArray = np.linalg.inv(design.T @ design)
    beta: FloatArray = gram_inv @ (design.T @ r)
    resid = r - design @ beta
    dof = len(r) - 2
    s2 = float(resid @ resid) / dof
    se = float(np.sqrt(s2 * gram_inv[1, 1]))
    t = float(beta[1]) / se
    return Fit(
        coef=float(beta[1]),
        se=se,
        z=t,
        p=float(2.0 * stats.t.sf(abs(t), dof)),
        n=len(r),
    )


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the input order (each capped at 1)."""
    p = np.asarray(pvalues, dtype=np.float64)
    m = len(p)
    adjusted: FloatArray = np.empty(m, dtype=np.float64)
    running = 0.0
    for rank, idx in enumerate(np.argsort(p, kind="stable")):
        running = max(running, (m - rank) * float(p[idx]))
        adjusted[idx] = min(1.0, running)
    return [float(v) for v in adjusted]


def reliability(
    p: FloatArray, y: FloatArray, edges: Sequence[float] = EDGES
) -> list[dict[str, Any]]:
    """Per bin of predicted P(home win): games, mean predicted, observed home-win rate and its
    Wilson 95% interval. Empty bins are dropped."""
    prob = np.asarray(p, dtype=np.float64)
    wins = np.asarray(y, dtype=np.float64)
    which = np.searchsorted(np.asarray(edges[1:-1]), prob, side="right")
    rows: list[dict[str, Any]] = []
    for k in range(len(edges) - 1):
        here = which == k
        n = int(here.sum())
        if n == 0:
            continue
        low, high = _wilson(int(wins[here].sum()), n)
        rows.append(
            {
                "lo": edges[k],
                "hi": edges[k + 1],
                "n": n,
                "predicted": float(prob[here].mean()),
                "observed": float(wins[here].mean()),
                "low": low,
                "high": high,
            }
        )
    return rows


def binned_residuals(
    feature: FloatArray, residual: FloatArray, n_bins: int = 10
) -> list[dict[str, Any]]:
    """Residual means per feature bin with a normal 95% interval. A feature with at most
    ``n_bins`` distinct values gets one bin per value; otherwise quantile bins."""
    x = np.asarray(feature, dtype=np.float64)
    r = np.asarray(residual, dtype=np.float64)
    values = np.unique(x)
    if len(values) <= n_bins:
        groups = [np.flatnonzero(x == v) for v in values]
    else:
        edges = np.quantile(x, np.linspace(0.0, 1.0, n_bins + 1))
        which = np.clip(np.searchsorted(edges[1:-1], x, side="right"), 0, n_bins - 1)
        groups = [np.flatnonzero(which == k) for k in range(n_bins)]
    rows: list[dict[str, Any]] = []
    for g in groups:
        if len(g) == 0:
            continue
        mean = float(r[g].mean())
        half = None
        if len(g) > 1:
            half = 1.959963984540054 * float(r[g].std(ddof=1)) / float(np.sqrt(len(g)))
        rows.append(
            {
                "feature_mean": float(x[g].mean()),
                "residual_mean": mean,
                "ci_low": None if half is None else mean - half,
                "ci_high": None if half is None else mean + half,
                "n": len(g),
            }
        )
    return rows


def elo_pregame(games: pd.DataFrame, params: EloParams) -> pd.DataFrame:
    """Pre-game Elo rating difference (home-court advantage included) and P(home win) for every
    game, indexed by ``game_id``. ``games`` must be sorted by tip-off (``prepare`` checks it)."""
    diff: FloatArray = replay(prepare(games), params)
    p: FloatArray = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
    return pd.DataFrame(
        {"elo_diff": diff, "elo_p_home": p}, index=games["game_id"].astype(str).to_numpy()
    )


def pregame_features(games: pd.DataFrame) -> pd.DataFrame:
    """Pre-game features of every game, indexed by ``game_id``.

    ``games`` is the whole games table (every season, tip-off sorted) with columns game_id,
    season, round, phase, tipoff_utc, home, away, played, forfeit, neutral, home_score, away_score.

    - home/away rest (days, capped at 7), short-rest flags, games in the last 7 days, and rest_diff
      = home rest minus away rest: from ``rest_features``.
    - round: the game's round number; is_playoff: 1 unless phase is the regular season.
    - month_of_season: calendar months since October (October 0 ... June 8).
    - confidence: |p_model - 0.5| is NOT computed here (it needs the model); see the script.
    - prior_home_edge: the home team's home-win rate in the previous season minus the league's
      home-win rate that season, over played non-neutral non-forfeit games. NaN when the team had
      no such home games. Only whole earlier seasons are read.
    """
    rest = rest_features(games)
    home = rest[rest["side"] == "home"].set_index("game_id")
    away = rest[rest["side"] == "away"].set_index("game_id")
    index = games["game_id"].astype(str).to_numpy()
    out = pd.DataFrame(index=index)
    out["home_rest"] = home.reindex(index)["days_rest"].to_numpy(dtype=np.float64)
    out["away_rest"] = away.reindex(index)["days_rest"].to_numpy(dtype=np.float64)
    out["rest_diff"] = out["home_rest"] - out["away_rest"]
    out["home_short"] = home.reindex(index)["short_rest"].to_numpy(dtype=np.float64)
    out["away_short"] = away.reindex(index)["short_rest"].to_numpy(dtype=np.float64)
    out["home_last7"] = home.reindex(index)["games_last_7d"].to_numpy(dtype=np.float64)
    out["away_last7"] = away.reindex(index)["games_last_7d"].to_numpy(dtype=np.float64)
    out["round"] = games["round"].to_numpy(dtype=np.float64)
    out["is_playoff"] = (games["phase"].to_numpy() != REGULAR_SEASON).astype(np.float64)
    out["month_of_season"] = ((games["tipoff_utc"].dt.month.to_numpy() - 10) % 12).astype(
        np.float64
    )
    out["prior_home_edge"] = _prior_home_edge(games)
    return out


def _prior_home_edge(games: pd.DataFrame) -> FloatArray:
    done = games[games["played"] & ~games["forfeit"] & ~games["neutral"]]
    home_won = (done["home_score"] > done["away_score"]).astype(np.float64)
    league = home_won.groupby(done["season"]).mean()
    team = home_won.groupby([done["season"], done["home"]]).mean()
    edges: list[float] = []
    for season, team_code in zip(games["season"], games["home"], strict=True):
        prior = int(season) - PRIOR_SEASON_GAP
        key = (prior, str(team_code))
        if key in team.index and prior in league.index:
            edges.append(float(team.loc[key]) - float(league.loc[prior]))
        else:
            edges.append(float("nan"))
    return np.asarray(edges, dtype=np.float64)
