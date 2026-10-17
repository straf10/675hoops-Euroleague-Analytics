"""A synthetic EuroLeague-shaped league for the ELOC tests (``tests/test_eloc_*.py``).

Eight teams, seasons 2007 to 2011, a double round robin (56 games a season in 14 rounds of 4).
Outcomes follow the teams' strengths plus home advantage, so Elo has signal to replay. Every game
is played, unneutral and not a forfeit, so the scored counts are the game counts.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.config import ELOC_CV, ElocCv

TEAMS = tuple("ABCDEFGH")
SEASONS = (2007, 2008, 2009, 2010, 2011)
GAMES_PER_SEASON = len(TEAMS) * (len(TEAMS) - 1)


def games(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    strength = dict(zip(TEAMS, rng.normal(0.0, 150.0, len(TEAMS)), strict=True))
    rows: list[dict[str, object]] = []
    for season in SEASONS:
        start = pd.Timestamp(f"{season}-10-01", tz="UTC")
        pairs = [(h, a) for h in TEAMS for a in TEAMS if h != a]
        for i, (home, away) in enumerate(pairs):
            rnd = i // 4 + 1
            diff = strength[home] - strength[away] + 90.0
            margin = round(diff / 25.0 + rng.normal(0.0, 12.0)) or 1
            home_score = 80 + max(margin, 0)
            rows.append(
                {
                    "game_id": f"S{season}-{i:02d}",
                    "season": season,
                    "round": rnd,
                    "phase": "RS",
                    "tipoff_utc": start + pd.Timedelta(days=7 * (rnd - 1), hours=i % 4),
                    "home": home,
                    "away": away,
                    "home_score": home_score,
                    "away_score": home_score - margin,
                    "played": True,
                    "forfeit": False,
                    "neutral": False,
                    "confirmed_date": True,
                }
            )
    return pd.DataFrame(rows)


def spec(report: Path | None = None) -> ElocCv:
    """Two folds (2010, 2011), fit from 2008, live fit 2008 to 2011, 200 resamples. ``report``
    relocates the outputs (tests write nothing into the repository)."""
    out = report or Path("reports/eloc_cv.json")
    return replace(
        ELOC_CV,
        report=out,
        games_report=out.with_name("eloc_cv_games.csv"),
        elo_warmup=(2007,),
        folds=(2010, 2011),
        fit_from=2008,
        live_fit_seasons=(2008, 2011),
        bootstrap_resamples=200,
    )


def with_scores_swapped(frame: pd.DataFrame, mask: np.ndarray) -> pd.DataFrame:
    """A copy whose scores are swapped (the home side loses) on the ``mask`` rows."""
    out = frame.copy()
    out.loc[mask, ["home_score", "away_score"]] = frame.loc[
        mask, ["away_score", "home_score"]
    ].to_numpy()
    return out
