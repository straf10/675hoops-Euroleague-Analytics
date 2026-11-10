"""Injury-status diagnostic (B3, research only): the played rate of players listed with each
BasketNews status in their club's next game. Rule: docs/models/diag_injstatus.md.

Reads the games mart, the injury log, the cached people listing and the cached box scores
read-only. Writes only the JSON report. Run: ``uv run python scripts/diag_injstatus.py``.
"""

import argparse
from pathlib import Path

from eurohoops.config import EUROLEAGUE, INJURY_LOG, LIVE_SEASON, MART_PATH
from eurohoops.eval.injstatus import build_report
from eurohoops.ingest.bios import el_people_path
from eurohoops.logs import write_json
from eurohoops.marts import read_games
from eurohoops.models.availability import match_injuries, read_injuries, read_roster_names
from eurohoops.stats.box import build_box_games

REPO = Path(__file__).resolve().parent.parent
OUT_JSON = REPO / "reports" / "diag_injstatus.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, default=LIVE_SEASON)
    parser.add_argument("--db", type=Path, default=REPO / MART_PATH)
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    games = read_games(args.db, EUROLEAGUE.name)
    box = build_box_games(REPO / EUROLEAGUE.raw_dir, games[games["season"] == args.season])
    roster = read_roster_names(REPO / el_people_path(EUROLEAGUE.raw_dir, args.season))
    matched = match_injuries(read_injuries(REPO / INJURY_LOG), roster)
    report = build_report(games, matched, box.players, args.season)
    write_json(args.out, report)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
