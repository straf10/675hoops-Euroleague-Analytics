"""Cache older seasons for the site's history: EuroLeague schedules and GBL results pages.

Cache only: nothing is staged and no model input changes (EuroLeague ``default_seasons`` and
the GBL model seasons stay as they are). Every request goes through the throttled fetcher, and
a cached file is never fetched again, so the command can be re-run to resume.

    uv run python scripts/backfill_history.py --euroleague 2006 --gbl 2006 2007 ... 2017
"""

import argparse
import logging

from eurohoops.config import EUROLEAGUE, GBL, LIVE_SEASON
from eurohoops.ingest import euroleague, gbl
from eurohoops.ingest.cache import read_cached, write_atomic
from eurohoops.ingest.euroleague import SCHEDULE_URL, _schedule_games
from eurohoops.ingest.gbl import ingest_gbl
from eurohoops.ingest.http import Fetcher, make_client

log = logging.getLogger("backfill_history")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--euroleague", type=int, nargs="*", default=[], help="EuroLeague season start years"
    )
    parser.add_argument("--gbl", type=int, nargs="*", default=[], help="GBL season start years")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    with make_client() as client:
        for season in args.euroleague:
            path = EUROLEAGUE.raw_dir / "schedule" / f"E{season}.json.gz"
            if path.exists():
                games = _schedule_games(read_cached(path))
                log.info("EuroLeague %d schedule cached: %d games", season, len(games))
                continue
            fetcher = Fetcher(client, euroleague.MIN_INTERVAL_S)
            payload = fetcher.get(SCHEDULE_URL.format(season=season))
            write_atomic(path, payload)
            log.info(
                "EuroLeague %d schedule fetched: %d games", season, len(_schedule_games(payload))
            )

        if args.gbl:
            seasons = sorted(season for season in args.gbl if season in gbl.SEASON_IDS)
            missing = sorted(set(args.gbl) - set(seasons))
            if missing:
                raise SystemExit(f"no ESAKE season id for {missing}")
            fetcher = Fetcher(client, gbl.MIN_INTERVAL_S)
            rounds = ingest_gbl(fetcher, GBL.raw_dir, seasons, False, LIVE_SEASON)
            for season in seasons:
                pages = [r for r in rounds if r.season == season]
                games = [g for r in pages for g in r.page.games]
                played = sum(g.home_score is not None for g in games)
                log.info(
                    "GBL %d results: %d round pages, %d games, %d played",
                    season,
                    len(pages),
                    len(games),
                    played,
                )


if __name__ == "__main__":
    main()
