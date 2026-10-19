"""Documented crosswalk decisions: every ``match`` links two persons with the same birth date.

The birth dates come from the cached bios (``data/staging/player_bios.parquet``, never committed),
so the test runs only where that staging file exists and skips otherwise.
"""

from pathlib import Path

import pandas as pd
import pytest

from eurohoops.entity.pipeline import read_overrides

OVERRIDES = Path("entity/overrides.csv")
BIOS = Path("data/staging/player_bios.parquet")
# Documented match of 2026-09-30 (one player, two EuroLeague ids in 2014 and 2015): the cached bios
# hold no birth date for the second id, so its birth date cannot be checked. Listed, not skipped.
NO_BIRTH_DATE_ON_FILE = {("euroleague", "P005983")}


def test_every_match_decision_names_two_known_persons_with_the_same_birth_date() -> None:
    if not BIOS.exists():
        pytest.skip("cached bios not staged (data/ is local): birth dates cannot be checked")
    bios = pd.read_parquet(BIOS)
    dates = {
        (str(r.competition), str(r.source_id)): str(r.birth_date)
        for r in bios.itertuples()
        if r.birth_date is not None and str(r.birth_date) not in ("", "None", "NaT")
    }
    matches = read_overrides(OVERRIDES)
    matches = matches[matches["decision"] == "match"]
    assert not matches.empty
    for row in matches.itertuples():
        sides = [
            (str(row.competition_a), str(row.source_a)),
            (str(row.competition_b), str(row.source_b)),
        ]
        if any(side in NO_BIRTH_DATE_ON_FILE for side in sides):
            continue
        left, right = (dates.get(side) for side in sides)
        assert left is not None, f"no birth date for {sides[0]}"
        assert right is not None, f"no birth date for {sides[1]}"
        assert left == right, f"{sides[0][1]} {left} vs {sides[1][1]} {right}"
