"""EuroCup diagnostic (experiments/eurocup.md): Elo against B0, walk-forward, research only.

Elo and B0 are fitted on the tuning seasons by ``run_backtest``; the test seasons are only scored.
This module replays the same fitted Elo, computes each game's log loss under Elo and under B0,
and applies the pass bar: the paired bootstrap of the per-game gap (Elo minus B0) decides the
ranking. Nothing here reads a test season for a setting.
"""

from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import Backtest, M1Backtest
from eurohoops.eval.backtest import TunedModel, run_backtest, win_probabilities
from eurohoops.eval.m1_backtest import baselines, m1_predictions, prepare_data, tune
from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.eval.promotion import bootstrap_ci
from eurohoops.models.elo import EloParams, FloatArray, prepare, replay

MEAN_GAP_BAR = 0.01  # the mean log-loss gap must reach this size to rank a model above another
NO_RANKING = "no ranking"


def ranking_verdict(mean_gap: float, lower: float, upper: float, first: str, second: str) -> str:
    """Pass bar (experiments/eurocup.md): ``gap = log loss(first) - log loss(second)`` per game."""
    if mean_gap <= -MEAN_GAP_BAR and upper < 0.0:
        return f"{first} ranks above {second}"
    if mean_gap >= MEAN_GAP_BAR and lower > 0.0:
        return f"{second} ranks above {first}"
    return NO_RANKING


def _gap_block(gap: np.ndarray, first: str = "elo", second: str = "b0") -> dict[str, Any]:
    lower, upper = bootstrap_ci(gap)
    return {
        "n": int(gap.size),
        "mean": round(float(gap.mean()), 6),
        "ci97_5": [round(lower, 6), round(upper, 6)],
        "verdict": ranking_verdict(float(gap.mean()), lower, upper, first, second),
    }


def elo_vs_b0(games: pd.DataFrame, spec: Backtest) -> dict[str, Any]:
    """Fit Elo and B0 on the tuning seasons, then compare per-game log losses on each split.

    ``games`` is the competition's rows from the marts. Unplayed and forfeited games are left out
    by the same rule as ``run_backtest``.
    """
    report = run_backtest(games, spec)
    tuned = report["tuned"]
    model = TunedModel(
        params=EloParams(k=tuned["k"], hca=tuned["hca"], reversion=tuned["reversion"]),
        margin_scale=tuned["margin_scale"],
        b0_home_win_rate=report["b0"]["home_win_rate"],
        b0_home_margin=report["b0"]["home_margin"],
    )
    rated = games["played"] & ~games["forfeit"]
    history = games[rated & games["season"].between(spec.warmup[0], spec.test[-1])]
    season = history["season"].to_numpy()
    margin = (history["home_score"] - history["away_score"]).to_numpy(dtype=np.float64)
    home_won: FloatArray = (margin > 0).astype(np.float64)
    neutral: FloatArray = history["neutral"].to_numpy(dtype=np.float64)
    p_elo = win_probabilities(replay(prepare(history), model.params))
    p_b0, _ = model.b0(neutral)
    gap = per_game_log_loss(p_elo, home_won) - per_game_log_loss(p_b0, home_won)
    splits = {"tuning": np.isin(season, spec.tuning), "test": np.isin(season, spec.test)}
    test_seasons = {int(s): int((season == s).sum()) for s in spec.test}
    return {
        "model_version": report["model_version"],
        "seasons": report["seasons"],
        "tuned_elo": tuned,
        "b0": report["b0"],
        "games": {
            "tuning": int(splits["tuning"].sum()),
            "test": int(splits["test"].sum()),
            "test_by_season": {str(s): n for s, n in test_seasons.items()},
        },
        "log_loss": {
            name: {
                "elo": round(float(per_game_log_loss(p_elo[mask], home_won[mask]).mean()), 6),
                "b0": round(float(per_game_log_loss(p_b0[mask], home_won[mask]).mean()), 6),
            }
            for name, mask in splits.items()
        },
        "gap_elo_minus_b0": {name: _gap_block(gap[mask]) for name, mask in splits.items()},
        "pass_bar": (
            f"Elo above B0 if the test mean gap <= -{MEAN_GAP_BAR} and the 97.5% paired "
            f"bootstrap upper bound < 0; B0 above Elo if the mean gap >= {MEAN_GAP_BAR} and the "
            "lower bound > 0; else no ranking. Tuning block is descriptive only."
        ),
        "verdict": _gap_block(gap[splits["test"]])["verdict"],
    }


def m1_vs_elo_b0(games: pd.DataFrame, team_games: pd.DataFrame, spec: M1Backtest) -> dict[str, Any]:
    """M1, the comparison Elo and B0 on the EuroCup test seasons (spec addendum).

    Tuning uses the tuning seasons only (``tune``). The gaps use the test games M1 can score
    (team box lines present), the same games for all three models.
    """
    data = prepare_data(games, team_games, spec)
    tuned = tune(data, spec)
    base = baselines(games, data, spec)
    m1 = m1_predictions(tuned, tuned.variant, data)
    shared = data.split["test"] & data.has_rows & data.rated
    home_won: FloatArray = (data.margin > 0).astype(np.float64)
    loss = {
        "m1": per_game_log_loss(m1.p_home[shared], home_won[shared]),
        "elo": per_game_log_loss(base.elo.p_home[shared], home_won[shared]),
        "b0": per_game_log_loss(base.b0.p_home[shared], home_won[shared]),
    }
    pairs = {
        "m1_minus_elo": (loss["m1"] - loss["elo"], "m1", "elo"),
        "m1_minus_b0": (loss["m1"] - loss["b0"], "m1", "b0"),
    }
    return {
        "n_shared_test_games": int(shared.sum()),
        "log_loss_shared_test": {name: round(float(v.mean()), 6) for name, v in loss.items()},
        "tuned_variant": tuned.variant,
        "pairwise": {
            name: _gap_block(gap, first, second) for name, (gap, first, second) in pairs.items()
        },
    }
