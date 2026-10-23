"""Early-season totals diagnostic (B2, research only): market total and M1 total against the actual
total, by EuroLeague round bucket (1-5, 6-10, 11+). Rule: docs/models/diag_early_totals.md.

Reads the games mart, the odds log and the M1 prediction log read-only. Writes only the JSON
report. Run: ``uv run python scripts/diag_early_totals.py --season 2026``.
"""

import argparse
from pathlib import Path

import duckdb
import pandas as pd

from eurohoops.config import EUROLEAGUE, MART_PATH
from eurohoops.eval.early_totals import build_report
from eurohoops.logs import write_json

REPO = Path(__file__).resolve().parent.parent
ODDS = REPO / "odds" / "euroleague_2026-27.csv"
M1_LOG = REPO / "predictions" / "euroleague_m1_2026-27.csv"
OUT_JSON = REPO / "reports" / "diag_early_totals.json"


def load_games(db: Path) -> pd.DataFrame:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.sql(
            """
            select game_id, season, round, phase, tipoff_utc, played, forfeit,
                   home_score, away_score
            from games
            where competition = 'euroleague'
            """
        ).df()
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--db", type=Path, default=REPO / MART_PATH)
    parser.add_argument("--odds", type=Path, default=ODDS)
    parser.add_argument("--m1-log", type=Path, default=M1_LOG)
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    odds = pd.read_csv(args.odds, dtype={"game_id": str})
    m1_log = pd.read_csv(args.m1_log, dtype={"game_id": str, "exp_total": float})
    report = build_report(
        load_games(args.db),
        odds,
        m1_log,
        args.season,
        manual_pushes=EUROLEAGUE.manual_pushes,
    )
    write_json(args.out, report)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
