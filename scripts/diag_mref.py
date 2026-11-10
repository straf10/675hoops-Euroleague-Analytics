"""Market-referenced diagnostic (mref): each active shadow against Elo, scored against the
bookmakers' pre-tip probability. Research only. Spec: experiments/mref.md.

Reads the games mart, the odds log and the prediction logs read-only. Writes only the JSON
report. Run at a checkpoint: ``uv run python scripts/diag_mref.py --look 1``.
"""

import argparse
from pathlib import Path

import pandas as pd

from eurohoops.config import EUROLEAGUE, LIVE_SEASON, MART_PATH, season_label
from eurohoops.eval.forecasts import _calls, _market_calls
from eurohoops.eval.mref import build_report
from eurohoops.logs import write_json
from eurohoops.marts import read_games
from eurohoops.model_catalog import active_shadows

REPO = Path(__file__).resolve().parent.parent
ODDS = REPO / "odds" / f"euroleague_{season_label(LIVE_SEASON)}.csv"
OUT_JSON = REPO / "reports" / "diag_mref.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--look", type=int, choices=(1, 2), required=True)
    parser.add_argument("--season", type=int, default=LIVE_SEASON)
    parser.add_argument("--db", type=Path, default=REPO / MART_PATH)
    parser.add_argument("--odds", type=Path, default=ODDS)
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    pushes = EUROLEAGUE.manual_pushes
    games = read_games(args.db, EUROLEAGUE.name)
    market = _market_calls(args.odds, games, args.season)
    elo, _ = _calls(EUROLEAGUE.prediction_log, games, args.season, pushes)
    shadows: dict[str, pd.DataFrame] = {
        tag: _calls(path, games, args.season, pushes)[0]
        for tag, path in active_shadows(EUROLEAGUE).items()
    }
    report = build_report(games, args.season, args.look, market, shadows, elo)
    write_json(args.out, report)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
