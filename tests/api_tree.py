"""A small repository tree for the API tests: the layout ``eurohoops.config`` names, under a
temporary root, built from the committed fixtures.

- EuroLeague: the cached schedules and box scores of ``stats_raw`` (rounds 1-6 of 2024-25 and
  round 1 of 2010-11) plus a synthetic live season 2026 on six of their clubs (round 1 played).
- ``player_xwalk`` maps the EuroLeague player P013382 to one person (``EL_PERSON``).
- ``tests/fixtures/api``: the reports and prediction logs (ungated simulation optional).
"""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from eurohoops.config import EL_TITLES_SEED, EUROLEAGUE, MART_PATH
from eurohoops.marts import write_tables
from eurohoops.parse.games import conform
from eurohoops.stats.export import load_cached_games
from tests.conftest import FIXTURES, TEAMS, make_games, teams_table

NOW = datetime(2026, 10, 8, 8, 0, tzinfo=UTC)
API_FIXTURES = FIXTURES / "api"
EL_CLUBS = dict(zip(TEAMS, ("BAR", "MAD", "OLY", "PAN", "ULK", "PAM"), strict=True))
EL_PERSON = "P:P013382"  # Levi Randolph: EuroLeague id P013382
UNPUBLISHED_PERSON = "P:UNPUBLISHED"  # no crosswalk row: not on the site


def _euroleague_games(cached: pd.DataFrame, *, live_season: bool = True) -> pd.DataFrame:
    """The cached 2010 and 2024 games plus the live season on six clubs; round 1 is played."""
    if not live_season:
        return conform(cached)
    live = make_games({2026: False})
    live = live.assign(home=live["home"].map(EL_CLUBS), away=live["away"].map(EL_CLUBS))
    first = live["round"] == 1
    live.loc[first, ["home_score", "away_score", "played"]] = [90, 80, True]
    return conform(pd.concat([cached, live], ignore_index=True))


def build_tree(root: Path, *, ungated: bool = True, live_season: bool = True) -> None:
    """Write the tree under ``root`` (the marts, the raw caches, reports, prediction logs).

    ``live_season=False`` leaves the synthetic 2026 games out of the marts (finished seasons only).
    """
    raw = root / EUROLEAGUE.raw_dir
    shutil.copytree(FIXTURES / "stats_raw", raw)
    for source in ("reports", "predictions"):
        shutil.copytree(API_FIXTURES / source, root / source)
    (root / EL_TITLES_SEED.parent).mkdir(parents=True, exist_ok=True)
    shutil.copy(EL_TITLES_SEED, root / EL_TITLES_SEED)  # publish reads the titles seed
    if not ungated:
        (root / "reports" / "sim_ungated_euroleague.json").unlink()

    cached, cached_teams = load_cached_games(raw)
    el_games = _euroleague_games(cached, live_season=live_season)
    el_teams = pd.concat([cached_teams, teams_table(el_games)]).drop_duplicates("team")
    teams = el_teams.assign(competition="euroleague")
    xwalk = pd.DataFrame(
        {
            "person_id": [EL_PERSON],
            "competition": ["euroleague"],
            "source_id": ["P013382"],
            "method": ["none"],
            "score": [None],
        }
    )
    mart = root / MART_PATH
    mart.parent.mkdir(parents=True)
    write_tables(
        mart,
        {
            "games": el_games.assign(competition="euroleague"),
            "teams": teams,
            "player_xwalk": xwalk,
        },
    )
