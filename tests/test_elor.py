"""Margin scale of live Elo (``models/elor.py``, read by ELOC): fitted on earlier seasons only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from eurohoops.models import elo
from eurohoops.models.elor import margin_scales


def test_margin_scales_use_earlier_seasons_only() -> None:
    rng = np.random.default_rng(7)
    seasons = np.repeat([2023, 2024, 2025], 40)
    games = pd.DataFrame(
        {
            "season": seasons,
            "played": True,
            "forfeit": False,
            "home_score": rng.integers(60, 100, seasons.size),
            "away_score": rng.integers(60, 100, seasons.size),
        }
    )
    diff = rng.normal(0.0, 50.0, seasons.size)
    scales = margin_scales(games, diff)
    assert np.isnan(scales[2023])
    early = (games["season"] < 2025).to_numpy()
    margin = (games["home_score"] - games["away_score"]).to_numpy(dtype=float)
    assert scales[2025] == elo.fit_margin_scale(diff[early], margin[early])
