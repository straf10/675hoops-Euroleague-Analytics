"""Market-referenced diagnostic (mref): each shadow against Elo, with the bookmakers' pre-tip
probability as the reference instead of the result. Research only; it promotes nothing.
Spec: experiments/mref.md. Rule: docs/models/diag_mref.md.

Per game: each side's cross-entropy against MKT (``q`` = the pre-tip ``p_home``) and the paired
gap, model minus Elo. Per model: ``n`` and the SD of the gap. At a complete checkpoint (CLAUDE.md
rule 4), with rounds capped to it, also the mean gap, its paired-bootstrap CI and the verdict.
"""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval.forecasts import REGULAR_SEASON
from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.eval.promotion import LOOK_ROUNDS, bootstrap_ci, checkpoint_status

CLIP = 1e-6  # the probability clip used across the programme (benchmark.py)
MIN_GAMES = 100  # fewer shared games than this: no verdict
COMPETITION = "euroleague"


def _round(x: float) -> float:
    return round(float(x), 6)


def cross_entropy(q: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Per-game cross-entropy of ``p`` against the reference probability ``q``, p clipped."""
    clipped = np.clip(p, CLIP, 1.0 - CLIP)
    return per_game_log_loss(clipped, q)


def paired_table(market: pd.DataFrame, model: pd.DataFrame, elo: pd.DataFrame) -> pd.DataFrame:
    """The games in all three frames, in tip-off order: each side's cross-entropy against MKT and
    the gap (model minus Elo).

    ``market`` is MKT's rows (``p_home``, ``phase``, ``round``, ``tipoff_utc``); ``model`` and
    ``elo`` are scored rows (``p_home``). A game missing from any frame is not in the table.
    """
    shared = (
        market[["game_id", "tipoff_utc", "phase", "round", "p_home"]]
        .rename(columns={"p_home": "q"})
        .merge(model[["game_id", "p_home"]].rename(columns={"p_home": "p_model"}), on="game_id")
        .merge(elo[["game_id", "p_home"]].rename(columns={"p_home": "p_elo"}), on="game_id")
        .sort_values(["tipoff_utc", "game_id"], ignore_index=True)
    )
    q = shared["q"].to_numpy(dtype=np.float64)
    ce_model = cross_entropy(q, shared["p_model"].to_numpy(dtype=np.float64))
    ce_elo = cross_entropy(q, shared["p_elo"].to_numpy(dtype=np.float64))
    return shared.assign(ce_model=ce_model, ce_elo=ce_elo, gap=ce_model - ce_elo)


def _mean_and_ci(gap: np.ndarray) -> tuple[float | None, list[float] | None]:
    """The mean gap and its paired-bootstrap 97.5% CI; None below 2 games."""
    if len(gap) < 2:
        return None, None
    lo, hi = bootstrap_ci(gap)
    return _round(gap.mean()), [_round(lo), _round(hi)]


def verdict(n: int, mean: float | None, ci: list[float] | None) -> str:
    """'closer' when the mean gap and the CI's upper bound are below 0 on at least 100 games."""
    if n < MIN_GAMES or mean is None or ci is None:
        return "not testable"
    return "closer" if mean < 0.0 and ci[1] < 0.0 else "not closer"


def model_block(table: pd.DataFrame, *, due: bool) -> dict[str, Any]:
    """One model's block. ``gap_mean``, ``ci`` and ``verdict`` appear only when ``due``."""
    gap = table["gap"].to_numpy(dtype=np.float64)
    block: dict[str, Any] = {
        "n": len(gap),
        "gap_sd": _round(gap.std(ddof=1)) if len(gap) >= 2 else None,
    }
    if due:
        mean, ci = _mean_and_ci(gap)
        block |= {"gap_mean": mean, "ci": ci, "verdict": verdict(len(gap), mean, ci)}
    return block


def build_report(  # noqa: PLR0917 -- one look's inputs, as in promotion.run_look
    games: pd.DataFrame,
    season: int,
    look: int,
    market: pd.DataFrame,
    models: Mapping[str, pd.DataFrame],
    elo: pd.DataFrame,
) -> dict[str, Any]:
    """The diagnostic for one look: one block per shadow in ``models`` (tag -> scored rows).

    ``games`` feeds ``checkpoint_status``. Look 1 caps the regular season at its round; look 2
    takes the whole season. The statistic is computed only when the checkpoint is complete.
    """
    rnd = LOOK_ROUNDS[COMPETITION]
    due, why = checkpoint_status(games, season, look, rnd)
    last_round = rnd if look == 1 else None
    blocks: dict[str, Any] = {}
    for tag, model in models.items():
        table = paired_table(market, model, elo)
        if last_round is not None:
            table = table[(table["phase"] == REGULAR_SEASON) & (table["round"] <= last_round)]
        blocks[tag] = model_block(table, due=due)
    state = "complete" if due else "not due"
    return {
        "season": season,
        "look": look,
        "last_round": last_round,
        "status": f"look {look} {state}: {why}",
        "models": blocks,
    }
