"""Live Elo's margin scale, fitted on earlier seasons only (docs/models/elo_calibrated.md).

ELOC (``live_eloc``, ``eval/eloc_cv``) reads ``margin_scales``. The roster-prior code that shared
this module was retired with ELOR on 2026-11-03 and is no longer here.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from eurohoops.models import elo
from eurohoops.models.elo import FloatArray


def margin_scales(games: pd.DataFrame, elo_diff: FloatArray) -> dict[int, float]:
    """Per season s, ``elo.fit_margin_scale`` on rated games of seasons before s (NaN for the
    first season)."""
    rated = (games["played"] & ~games["forfeit"]).to_numpy(dtype=bool)
    season = games["season"].astype(int).to_numpy()
    margin = (games["home_score"] - games["away_score"]).to_numpy(dtype=np.float64)
    out: dict[int, float] = {}
    for s in np.unique(season):
        train = rated & (season < s)
        out[int(s)] = (
            elo.fit_margin_scale(elo_diff[train], margin[train]) if train.any() else math.nan
        )
    return out
