"""The whole WP protocol on a tiny synthetic league: every season 2007-2025, two games each,
one with overtime. Checks the shape of the report and the per-game rows, not the numbers."""

import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval import wp_backtest as wb
from eurohoops.models import wp


def _game_file(
    tmp: Path, season: int, fnum: int, rng: np.random.Generator
) -> tuple[int, int, bool]:
    """Writes one synthetic game and returns its final home and away score and whether it has OT."""
    names = ("FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter")
    obj: dict[str, Any] = {"CodeTeamA": "H", "CodeTeamB": "A", "ExtraTime": []}
    total = {"H": 0, "A": 0}
    overtime = fnum == 2
    for block, name in enumerate(names):
        events = []
        for i in range(12):
            team = "H" if rng.uniform() < 0.5 else "A"
            total[team] += 2
            clock = f"09:{59 - 4 * i:02d}"
            events.append(
                {
                    "PLAYTYPE": "2FGM",
                    "MARKERTIME": clock,
                    "MINUTE": block * 10 + 1 + i % 9,
                    "POINTS_A": str(total["H"]) if team == "H" else "",
                    "POINTS_B": str(total["A"]) if team == "A" else "",
                }
            )
        obj[name] = events
    if overtime:
        obj["ExtraTime"] = [
            {
                "PLAYTYPE": "2FGM",
                "MARKERTIME": "03:00",
                "MINUTE": 41,
                "POINTS_A": str(total["H"] + 2),
                "POINTS_B": "",
            }
        ]
        total["H"] += 2
    folder = tmp / "playbyplay" / f"E{season}"
    folder.mkdir(parents=True, exist_ok=True)
    with gzip.open(folder / f"{fnum}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return total["H"], total["A"], overtime


def _league(tmp: Path) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    rows = []
    for season in range(wb.FIRST_SEASON, wb.LAST_SEASON + 1):
        for fnum in (1, 2):
            home, away, _ = _game_file(tmp, season, fnum, rng)
            rows.append(
                {
                    "game_id": f"E{season}_{fnum}",
                    "season": season,
                    "phase": "RS",
                    "tipoff_utc": pd.Timestamp(f"{season}-10-{fnum:02d}", tz="UTC"),
                    "home": "H",
                    "away": "A",
                    "home_score": home,
                    "away_score": away,
                    "played": True,
                    "forfeit": False,
                    "neutral": False,
                }
            )
    return pd.DataFrame(rows)


@pytest.mark.slow
def test_full_protocol_runs_on_a_synthetic_league(tmp_path: Path) -> None:
    games = _league(tmp_path)
    report, rows = wb.run(games, tmp_path)
    assert report["version"] == wp.VERSION
    assert report["counts"]["included_games"] == len(games)
    assert report["chosen"]["family"] in ("logit", "gbm")
    assert {"model", "baseline", "delta_logloss"} <= report["test"].keys()
    assert len(report["gbm_grid"]) == 4
    assert report["gate"]["game_pages_use"] in ("model", "baseline")
    # One row per test game and group; the "all" group is the per-game average.
    test_ids = set(games.loc[games["season"].isin(wb.TEST), "game_id"])
    assert set(rows["game_id"]) == test_ids
    assert set(rows["group"]) <= set(wb.GROUPS)
    assert (rows["group"] == "all").sum() == len(test_ids)
    assert np.isfinite(rows["logloss_model"]).all()
    assert wb.format_table(report).startswith("version ")
