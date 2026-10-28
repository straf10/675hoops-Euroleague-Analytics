"""The site's season window must not reach the models: history is site-only.

``SITE_SEASONS`` sets how many EuroLeague seasons the stats site publishes. Model inputs are the
competitions' ``default_seasons`` and each model's own season tuples; these tests pin them, and
check that only the site and the ingest history default read ``SITE_SEASONS``.
"""

from pathlib import Path

from eurohoops.config import EUROLEAGUE, LIVE_SEASON, SITE_SEASONS, M2Seasons
from eurohoops.stats.export import site_window

SRC = Path(__file__).resolve().parents[1] / "src" / "eurohoops"


def test_model_seasons_are_unchanged_by_site_history() -> None:
    assert LIVE_SEASON == 2026
    assert EUROLEAGUE.default_seasons == tuple(range(2007, 2027))
    assert M2Seasons().development == tuple(range(2011, 2023))


def test_site_window_selects_latest_seasons_only() -> None:
    seasons = list(range(2007, 2027))
    assert site_window(seasons) == seasons[-SITE_SEASONS:]


def test_only_site_and_ingest_history_read_site_seasons() -> None:
    allowed = {"config.py", "stats/export.py", "stats/downloads.py", "cli/ingest.py"}
    readers = {
        str(p.relative_to(SRC)).replace("\\", "/")
        for p in SRC.rglob("*.py")
        if "SITE_SEASONS" in p.read_text(encoding="utf-8")
    }
    assert readers <= allowed, readers - allowed
