"""POOL-c diagnostic (docs/models/pool_c.md): fit c on POOL rounds 1-19, then score rounds 20 on.

Stage ``fit`` writes reports/pool_c_fit.json once. It refuses (exit 1, nothing written) until every
regular-season game of rounds 1-19 is played; ``--force`` overwrites a frozen fit. Stage ``eval``
needs that file, scores every later game with the frozen c and writes reports/diag_pool_c.json; it
can run any time after the fit and reports n so far. Reads the POOL log and the games mart
read-only. Run: ``uv run python scripts/diag_pool_c.py --stage fit`` then ``--stage eval``.
"""

import argparse
import json
import sys
from pathlib import Path

from eurohoops.config import EUROLEAGUE, LIVE_SEASON, MART_PATH
from eurohoops.eval.pool_c import StageRefused, run_eval, run_fit
from eurohoops.eval.scorecard import read_log
from eurohoops.marts import read_games

REPO = Path(__file__).resolve().parent.parent
FIT_JSON = REPO / "reports" / "pool_c_fit.json"
OUT_JSON = REPO / "reports" / "diag_pool_c.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", choices=("fit", "eval"), required=True)
    parser.add_argument("--force", action="store_true", help="fit only: overwrite a frozen fit")
    parser.add_argument("--db", type=Path, default=REPO / MART_PATH)
    args = parser.parse_args()
    if args.force and args.stage != "fit":
        parser.error("--force applies to --stage fit only")
    pool_log_path = EUROLEAGUE.pool_prediction_log
    if pool_log_path is None:
        raise SystemExit("EuroLeague has no POOL prediction log configured")
    pool_log = read_log(REPO / pool_log_path)
    games = read_games(args.db, EUROLEAGUE.name)
    try:
        if args.stage == "fit":
            payload = run_fit(
                pool_log,
                games,
                LIVE_SEASON,
                EUROLEAGUE.manual_pushes,
                FIT_JSON,
                force=args.force,
            )
            out = FIT_JSON
        else:
            payload = run_eval(
                pool_log, games, LIVE_SEASON, EUROLEAGUE.manual_pushes, FIT_JSON, OUT_JSON
            )
            out = OUT_JSON
    except StageRefused as exc:
        print(f"{exc}. Nothing written.", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(payload, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
