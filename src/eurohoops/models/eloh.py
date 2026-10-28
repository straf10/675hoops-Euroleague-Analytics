"""ELOH (experiments/eloh.md): Elo with a per-team home advantage, shrunk toward 0.

``fit_home_effects`` runs frozen live Elo over the fit seasons. For each home team it takes the
mean residual of its home results against Elo's pre-game home win probability, shrinks that mean
with an empirical Bayes factor (method of moments on the between-team variance) and converts it to
Elo points. The fit is written once to ``reports/eloh_fit.json`` by ``scripts/fit_eloh.py``; the
live forecaster reads that file and never refits.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.models.elo import EloParams, prepare, replay, win_probability

# d p / d diff = p (1 - p) * ln(10) / 400, so a residual on p maps to Elo points by this slope.
LOGIT_SLOPE = np.log(10.0) / 400.0


@dataclass(frozen=True)
class TeamEffect:
    n: int  # rated home games in the fit seasons (played, not forfeit, not neutral)
    mean_residual: float  # ē: mean of (home win - p_home)
    mean_p: float  # p̄: mean pre-game p_home
    sampling_var: float  # s²: mean(p (1 - p)) / n
    shrink: float  # B = τ² / (τ² + s²)
    delta: float  # δ in Elo points: B · ē / (LOGIT_SLOPE · p̄ (1 - p̄))


@dataclass(frozen=True)
class HomeFit:
    params: EloParams  # the frozen live Elo parameters the residuals come from
    tau2: float  # between-team variance of the home residuals, net of sampling noise
    var_residual: float  # sample variance (ddof 1) of ē across teams
    mean_sampling_var: float  # mean of s² across teams
    teams: dict[str, TeamEffect]  # home teams with at least one rated home game


def fit_home_effects(games: pd.DataFrame, params: EloParams) -> HomeFit:
    """Fit δ per home team on ``games``: tipoff-sorted, fit seasons only, played and not forfeit.

    Neutral games are left out: Elo gives them no home advantage, so their residuals say nothing
    about a home team. Each game's p_home uses only earlier games (``replay``), as in live Elo.
    """
    diffs = replay(prepare(games), params)
    p_all = np.array([win_probability(d) for d in diffs], dtype=np.float64)
    rated = (games["played"] & ~games["forfeit"] & ~games["neutral"]).to_numpy(dtype=bool)
    sub = games[rated]
    frame = pd.DataFrame(
        {
            "team": sub["home"].astype(str).to_numpy(),
            "p": p_all[rated],
            "win": (sub["home_score"] > sub["away_score"]).to_numpy(dtype=np.float64),
        }
    )
    frame["residual"] = frame["win"] - frame["p"]
    frame["var_p"] = frame["p"] * (1.0 - frame["p"])
    grouped = frame.groupby("team")
    n = grouped.size()
    stats = pd.DataFrame(
        {
            "n": n,
            "ebar": grouped["residual"].mean(),
            "pbar": grouped["p"].mean(),
            "s2": grouped["var_p"].mean() / n,
        }
    )
    return fit_from_stats(stats, params)


def fit_from_stats(stats: pd.DataFrame, params: EloParams) -> HomeFit:
    """Shrink each team's home residual. ``stats`` is indexed by team with columns ``n`` (home
    games), ``ebar`` (mean residual), ``pbar`` (mean p_home) and ``s2`` (sampling variance of
    ``ebar``, mean(p (1 - p)) / n)."""
    if len(stats) < 2:
        raise ValueError("ELOH needs home residuals from at least two teams")
    var_residual = float(stats["ebar"].var(ddof=1))
    mean_s2 = float(stats["s2"].mean())
    tau2 = max(0.0, var_residual - mean_s2)
    teams: dict[str, TeamEffect] = {}
    for team, row in stats.sort_index().iterrows():
        s2 = float(row["s2"])
        shrink = tau2 / (tau2 + s2)
        p_bar = float(row["pbar"])
        shrunk = shrink * float(row["ebar"])
        teams[str(team)] = TeamEffect(
            n=int(row["n"]),
            mean_residual=float(row["ebar"]),
            mean_p=p_bar,
            sampling_var=s2,
            shrink=shrink,
            delta=shrunk / (LOGIT_SLOPE * p_bar * (1.0 - p_bar)),
        )
    return HomeFit(params, tau2, var_residual, mean_s2, teams)


def fit_to_json(fit: HomeFit, seasons: tuple[int, int]) -> dict[str, Any]:
    """The frozen file's content: the fit's parameters, its variance terms and each team's δ."""
    return {
        "method": (
            "per-team mean home residual of frozen live Elo, shrunk by method-of-moments "
            "empirical Bayes toward 0, converted to Elo points (experiments/eloh.md)"
        ),
        "fit_seasons": list(seasons),
        "elo_params": asdict(fit.params),
        "tau2": fit.tau2,
        "var_residual_ddof1": fit.var_residual,
        "mean_sampling_var": fit.mean_sampling_var,
        "teams_fitted": len(fit.teams),
        "teams": {team: asdict(effect) for team, effect in fit.teams.items()},
    }


def load_deltas(path: Path) -> dict[str, float]:
    """The frozen δ per source team code. A team not listed has δ = 0."""
    report = json.loads(path.read_text(encoding="utf-8"))
    return {team: float(effect["delta"]) for team, effect in report["teams"].items()}
