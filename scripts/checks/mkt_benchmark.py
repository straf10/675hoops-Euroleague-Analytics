"""MKT benchmark on the live EuroLeague season (B1): encompassing test and lead-time scores as JSON.

Read-only: it writes nothing to ``predictions/`` or ``odds/``. Its gate is a draft
(``docs/models/mkt.md``): run it on the gate's evaluation games only after the owner
commits the gate.

Usage: ``uv run python scripts/checks/mkt_benchmark.py > reports/mkt_benchmark.json``
"""

import json
import sys

from eurohoops.config import EUROLEAGUE, LIVE_SEASON, MART_PATH
from eurohoops.eval.benchmark import benchmark
from eurohoops.marts import read_games


def main() -> None:
    comp = EUROLEAGUE
    assert comp.odds_log is not None
    logs = {tag: comp.log_path(tag) for tag in ("elo", "m1", "m5")}
    report = benchmark(
        logs, read_games(MART_PATH, comp.name), comp.odds_log, LIVE_SEASON, comp.manual_pushes
    )
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
