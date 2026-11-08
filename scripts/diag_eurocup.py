"""EuroCup diagnostic: Elo against B0, walk-forward (research only, read-only on the marts).

Pre-registered in experiments/eurocup.md. Elo and B0 are fitted on the tuning seasons 2015-16..
2022-23 and scored on the test seasons 2023-24..2025-26 (finished games). Ratings are replayed from
the 2007-08 warm-up.

Run: ``uv run python scripts/diag_eurocup.py``. Writes ``reports/diag_eurocup.json`` (the path in
``EUROCUP.live_backtest``) and prints the summary. Reads the DuckDB marts; writes nothing else.
"""

import gzip
import json
from typing import Any

from eurohoops.config import EUROCUP, MART_PATH
from eurohoops.eval.eurocup import elo_vs_b0
from eurohoops.logs import write_json
from eurohoops.marts import read_games

RAW = EUROCUP.raw_dir


def _coverage(games_seasons: list[int]) -> dict[str, Any]:
    """Per season: scheduled and played games (marts), cached box-score and play-by-play files."""
    cov: dict[str, Any] = {}
    for season in games_seasons:
        box = RAW / "boxscore" / f"{EUROCUP.code}{season}"
        pbp = RAW / "playbyplay" / f"{EUROCUP.code}{season}"
        cov[str(season)] = {
            "boxscore_files": len(list(box.glob("*.json.gz"))) if box.exists() else 0,
            "playbyplay_files": len(list(pbp.glob("*.json.gz"))) if pbp.exists() else 0,
        }
    return cov


def _excluded_ties() -> dict[str, list[str]]:
    """Played games the ingest left out for equal final scores (cached schedules)."""
    out: dict[str, list[str]] = {}
    for path in sorted((RAW / "schedule").glob(f"{EUROCUP.code}*.json.gz")):
        season = path.stem.split(".")[0].removeprefix(EUROCUP.code)
        games = json.loads(gzip.decompress(path.read_bytes()))["data"]
        ties = [
            g["identifier"]
            for g in games
            if g["played"] and g["local"]["score"] == g["road"]["score"]
        ]
        if ties:
            out[season] = ties
    return out


def main() -> None:
    games = read_games(MART_PATH, EUROCUP.name)
    result = elo_vs_b0(games, EUROCUP.live_backtest)
    seasons = sorted(int(s) for s in games["season"].unique())
    report = {
        "experiment": "eurocup",
        "competition": EUROCUP.name,
        "games_in_marts": {
            "rows": len(games),
            "played": int(games["played"].sum()),
            "forfeits": int(games["forfeit"].sum()),
            "phases": {k: int(v) for k, v in games["phase"].value_counts().sort_index().items()},
        },
        "excluded_equal_scores": _excluded_ties(),
        "coverage": _coverage(seasons),
        **result,
    }
    write_json(EUROCUP.live_backtest.report, report)
    gap = report["gap_elo_minus_b0"]
    print(
        f"EuroCup test {report['games']['test']} games; log loss Elo "
        f"{report['log_loss']['test']['elo']}, B0 {report['log_loss']['test']['b0']}; "
        f"gap {gap['test']['mean']} CI97.5 {gap['test']['ci97_5']}; verdict {report['verdict']}"
    )
    print(f"wrote {EUROCUP.live_backtest.report}")


if __name__ == "__main__":
    main()
