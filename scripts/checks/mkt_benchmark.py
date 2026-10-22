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
    logs = {
        "elo": comp.prediction_log,
        "m1": comp.m1_prediction_log,
        "m5": comp.m5_prediction_log,
        "elor": comp.elor_prediction_log,
    }
    report = benchmark(
        logs, read_games(MART_PATH, comp.name), comp.odds_log, LIVE_SEASON, comp.manual_pushes
    )
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
