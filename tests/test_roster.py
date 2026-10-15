"""Roster lists for ELOR (``models/roster.py``): parsing, cache-only reads and membership."""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.ingest.bios import el_people_path
from eurohoops.models import roster as rs

FIXTURE = Path(__file__).parent / "fixtures" / "elor" / "el_people_E2026.json"
PAYLOAD = FIXTURE.read_bytes()


def _ts(text: str) -> float:
    return pd.Timestamp(text, tz="UTC").timestamp()


def _games() -> pd.DataFrame:
    """2026: round 1 on 8 Oct (PAN-ULK 18:00Z), round 2 on 15 Oct, round 3 on 22 Oct."""
    rows = [
        ("E2026_1", 1, "2026-10-08T18:00:00Z", "PAN", "ULK"),
        ("E2026_2", 2, "2026-10-15T18:00:00Z", "ULK", "PAN"),
        ("E2026_3", 3, "2026-10-22T18:00:00Z", "PAN", "ULK"),
    ]
    return pd.DataFrame(
        [
            {
                "game_id": g,
                "season": 2026,
                "phase": "RS",
                "round": r,
                "tipoff_utc": pd.Timestamp(t),
                "home": h,
                "away": a,
            }
            for g, r, t, h, a in rows
        ]
    )


def test_parse_keeps_players_with_box_ids_and_utc_stamps() -> None:
    table = rs.parse_roster(PAYLOAD, 2026)
    assert table["player_id"].tolist() == ["P900002", "P900003", "P900004", "P900005"]
    assert table["club"].tolist() == ["PAN", "ULK", "ULK", "PAN"]
    assert table["start"].iloc[0] == pytest.approx(_ts("2026-08-11T10:25:22.916"))
    assert table["end"].iloc[1] == _ts("2026-10-20T23:59:59")
    assert table["end"].iloc[[0, 2, 3]].isna().all()  # null, "" and missing are open-ended


def test_missing_start_counts_from_before_the_season() -> None:
    payload = b'{"data": [{"person": {"code": "1"}, "club": {"code": "MAL"}, "type": "J"}]}'
    table = rs.parse_roster(payload, 2014)
    assert np.isnan(table["start"].iloc[0])
    assert rs.on_roster(table, 100.0, 2014)["player_id"].tolist() == ["P1"]


def test_read_rosters_reads_the_cache_only(tmp_path: Path) -> None:
    with pytest.raises(rs.RosterCacheError):
        rs.read_rosters(tmp_path, [2026])
    path = el_people_path(tmp_path, 2026)
    path.parent.mkdir(parents=True)
    path.write_bytes(gzip.compress(PAYLOAD))
    assert len(rs.read_rosters(tmp_path, [2026])) == 4
    assert rs.read_rosters(tmp_path, []).empty


def test_club_codes_are_checked_against_the_games() -> None:
    table = rs.parse_roster(PAYLOAD, 2026)
    assert rs.unmatched_clubs(table, _games()) == {}
    renamed = _games().replace({"ULK": "FBT"})  # a display code must never reach the data
    assert rs.unmatched_clubs(table, renamed) == {
        2026: {"roster_only": ["ULK"], "games_only": ["FBT"]}
    }


def _members(cutoff: str) -> list[str]:
    table = rs.parse_roster(PAYLOAD, 2026)
    out = rs.on_roster(table, _ts(cutoff), 2026)
    return sorted(out["player_id"])


def test_membership_at_cutoffs() -> None:
    # Round 1: 900004 is stamped on 9 Oct, after round 1 began, so not yet (strict).
    assert _members("2026-10-08T18:00:00") == ["P900002", "P900003"]
    # Round 2: 900004 is in; 900003 still in (ends 20 Oct).
    assert _members("2026-10-15T18:00:00") == ["P900002", "P900003", "P900004"]
    # Round 3: 900003's end is before the cutoff.
    assert _members("2026-10-22T18:00:00") == ["P900002", "P900004"]
    # A start exactly at the cutoff is not before it; an end exactly at it is not after it.
    assert "P900005" not in _members("2026-11-15T00:00:00")
    assert "P900005" in _members("2026-11-15T00:00:01")
    assert "P900003" not in _members("2026-10-20T23:59:59")


def test_only_the_approved_strict_rule_exists() -> None:
    assert rs.FIRST_ROUND_RULE == "strict"
    assert not hasattr(rs, "FIRST_ROUND_RULES")
    # Stamped during round 1 (9 Oct): in from round 2's cutoff, not at round 1's.
    assert "P900004" not in _members("2026-10-08T18:00:00")
    assert "P900004" in _members("2026-10-15T18:00:00")


def test_start_date_counts() -> None:
    counts = rs.start_date_counts(rs.parse_roster(PAYLOAD, 2026), _games())
    assert counts == {
        "2026": {
            "players": 4,
            "start_after_round1_began": 2,
            "start_during_round1": 1,
            "start_after_round1": 1,
        }
    }


def test_season_rounds_with_a_single_round() -> None:
    one = _games().iloc[:1]
    rounds = rs.season_rounds(one)
    assert np.isnan(rounds.second[2026])
    counts = rs.start_date_counts(rs.parse_roster(PAYLOAD, 2026), one)
    assert counts["2026"]["start_during_round1"] == 2  # no second round: all later stamps
