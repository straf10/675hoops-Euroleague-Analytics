"""POOL3 screen (experiments/pool3.md, diagnostic): are POOL's Elo and ELOR logits near-duplicates?

Reads the four POOL member logs at their pinned versions (config.POOL_COMPONENTS) and the games
mart, read-only. Writes only reports/diag_pool3.json. Run: ``uv run python scripts/diag_pool3.py``.
"""

import argparse
from pathlib import Path

from eurohoops.config import EUROLEAGUE, MART_PATH, POOL_COMPONENTS
from eurohoops.eval.pool3 import MEMBERS, member_rows, screen
from eurohoops.eval.scorecard import read_log
from eurohoops.logs import write_json
from eurohoops.marts import read_games

REPO = Path(__file__).resolve().parent.parent
OUT_JSON = REPO / "reports" / "diag_pool3.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=REPO / MART_PATH)
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    members = {}
    for name in MEMBERS:
        path, version = POOL_COMPONENTS[name]
        members[name] = member_rows(
            read_log(REPO / path), version, manual_pushes=EUROLEAGUE.manual_pushes
        )
    report = screen(members, read_games(args.db, EUROLEAGUE.name))
    report["pinned_versions"] = {name: POOL_COMPONENTS[name][1] for name in MEMBERS}
    write_json(args.out, report)
    rule = report["rule"]
    print(f"n={report['n_games']} corr(elo, elor)={rule['value']} declared={rule['declared']}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
