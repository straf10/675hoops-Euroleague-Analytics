"""Entity resolution inputs (EuroLeague only): the owner's ``match`` and ``no_match`` decisions.

``eurohoops entity`` (``research.entity``) builds the ``player_names`` and ``player_xwalk`` marts
from the EuroLeague box scores and these overrides (``entity/overrides.csv``).
"""

from pathlib import Path

import pandas as pd

OVERRIDE_COLUMNS = [
    "competition_a",
    "source_a",
    "competition_b",
    "source_b",
    "decision",
    "reason",
    "date",
]


def read_overrides(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OVERRIDE_COLUMNS, dtype=str)
    return pd.read_csv(path, dtype=str, keep_default_na=False)[OVERRIDE_COLUMNS]
