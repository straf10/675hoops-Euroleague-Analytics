"""EuroLeague season SPM models for M6's injected SPM (``cli.backtest._m6_spm``).

Each EuroLeague season gets a ``rapm_spm`` ``SpmModel`` fitted only on EuroLeague stints and box
rows strictly before that season's first round cutoff (``choose_model`` picks the latest one whose
fit time is at or before a cutoff). The hyperparameters are M3's committed ``chosen`` block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import M3
from eurohoops.eval.m3_backtest import build_rapm_inputs
from eurohoops.models.minutes import round_cutoffs
from eurohoops.models.spm import SpmModel, build_season_spm


@dataclass(frozen=True)
class ElSpm:
    """EuroLeague season SPM models (EL data strictly before each EL season)."""

    models: dict[int, SpmModel]
    fit_time: dict[int, float]  # epoch seconds: first round cutoff of EL season s
    k: float
    half_life_days: float


def el_spm_models(
    el_games: pd.DataFrame,
    el_player_games: pd.DataFrame,
    stints: pd.DataFrame,
    checks: pd.DataFrame,
    chosen: dict[str, Any],
    *,
    last: int = M3.test[-1],
) -> ElSpm:
    """Build EL ``SpmModel`` per season on the M3 EuroLeague frame (same seasons as ``M3``;
    ``last`` extends it, e.g. to the live season for M6's live SPM: each season's model still
    reads only the seasons before it)."""
    first = M3.warmup[0]
    frame = (
        el_games[el_games["season"].between(first, last)]
        .sort_values("tipoff_utc")
        .reset_index(drop=True)
    )
    inputs = build_rapm_inputs(stints, checks, frame, el_player_games)
    season_spm = build_season_spm(
        frame,
        el_player_games,
        inputs,
        rapm_half_life_days=float(chosen["target_half_life_days"]),
        rapm_ridge_o=float(chosen["target_ridge_o"]),
        rapm_ridge_d=float(chosen["target_ridge_d"]),
        k=float(chosen["k"]),
        alpha=float(chosen["alpha"]),
    )
    cutoff = round_cutoffs(frame)
    season_col = frame["season"].astype(int).to_numpy()
    fit_time: dict[int, float] = {}
    for season in sorted(season_spm.models):
        idx = np.flatnonzero(season_col == season)
        fit_time[season] = float(cutoff.iloc[idx].min())
    return ElSpm(
        models=season_spm.models,
        fit_time=fit_time,
        k=float(chosen["k"]),
        half_life_days=float(chosen["target_half_life_days"]),
    )


def choose_model(el: ElSpm, cutoff_time: float) -> SpmModel | None:
    """Latest EL season with ``fit_time[season] <= cutoff_time``; ``None`` if none qualify."""
    eligible = [s for s, t in el.fit_time.items() if t <= cutoff_time]
    if not eligible:
        return None
    season = max(eligible, key=lambda s: (el.fit_time[s], s))
    return el.models[season]
