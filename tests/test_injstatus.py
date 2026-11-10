"""Injury-status diagnostic (B3): small inline fixtures, expected values worked out by hand."""

import pandas as pd
import pytest

from eurohoops.eval.injstatus import (
    build_report,
    finished_sides,
    player_games,
    side_snapshot,
    wilson,
)
from eurohoops.models.availability import RosterPlayer, match_injuries

ROSTER = [
    RosterPlayer("P1", "ULK", "SMITH, JOHN"),
    RosterPlayer("P2", "ULK", "JONES, AL"),
    RosterPlayer("P3", "PAM", "DOE, JANE"),
]
TIPOFF = pd.Timestamp("2026-11-05T18:00:00Z")


def _matched(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    """Injury rows (snapshot_utc, team, player, status), matched on names only (no alias file)."""
    return match_injuries(
        pd.DataFrame(
            {
                "snapshot_utc": [r[0] for r in rows],
                "team": [r[1] for r in rows],
                "player": [r[2] for r in rows],
                "bn_player_id": ["0"] * len(rows),
                "position": ["G"] * len(rows),
                "status": [r[3] for r in rows],
            }
        ),
        ROSTER,
        aliases={},
    )


def _games(rows: list[tuple[str, bool, bool]]) -> pd.DataFrame:
    """Games (game_id, played, forfeit) of season 2026, ULK at home to PAM, tip-off at TIPOFF."""
    return pd.DataFrame(
        {
            "game_id": [r[0] for r in rows],
            "season": [2026] * len(rows),
            "home": ["ULK"] * len(rows),
            "away": ["PAM"] * len(rows),
            "tipoff_utc": [TIPOFF] * len(rows),
            "played": [r[1] for r in rows],
            "forfeit": [r[2] for r in rows],
        }
    )


def _box(rows: list[tuple[str, str, int]]) -> pd.DataFrame:
    """Box rows (game_id, player_id, sec): a player without a row did not play."""
    return pd.DataFrame(
        {
            "game_id": [r[0] for r in rows],
            "player_id": [r[1] for r in rows],
            "sec": [r[2] for r in rows],
        }
    )


def test_snapshot_after_tipoff_is_not_used() -> None:
    # The 18:30 snapshot is after the 18:00 tip-off: only the 09:00 one counts.
    matched = _matched(
        [
            ("2026-11-05T09:00:00Z", "ULK", "John Smith", "Out"),
            ("2026-11-05T18:30:00Z", "ULK", "Al Jones", "Out"),
        ]
    )
    assert side_snapshot(matched, TIPOFF) == pd.Timestamp("2026-11-05T09:00:00Z")
    games = _games([("G1", True, False)])
    found = player_games(matched, finished_sides(games, 2026), _box([("G1", "P1", 600)]))
    assert list(found.table["player_id"]) == ["P1"]  # Jones, listed only after tip-off, is absent


def test_snapshot_older_than_24_hours_is_not_used() -> None:
    matched = _matched([("2026-11-04T17:00:00Z", "ULK", "John Smith", "Out")])  # 25 h before
    assert side_snapshot(matched, TIPOFF) is None
    games = _games([("G1", True, False)])
    found = player_games(matched, finished_sides(games, 2026), _box([]))
    assert found.sides_without_snapshot == 2  # both sides of G1 (ULK and PAM)
    assert found.table.empty


def test_snapshot_exactly_24_hours_before_is_used() -> None:
    matched = _matched([("2026-11-04T18:00:00Z", "ULK", "John Smith", "Out")])
    assert side_snapshot(matched, TIPOFF) == pd.Timestamp("2026-11-04T18:00:00Z")


def test_seconds_decide_played_and_no_row_is_not_played() -> None:
    matched = _matched(
        [
            ("2026-11-05T12:00:00Z", "ULK", "John Smith", "Out"),
            ("2026-11-05T12:00:00Z", "ULK", "Al Jones", "Uncertain"),
            ("2026-11-05T12:00:00Z", "PAM", "Jane Doe", "Ready"),
        ]
    )
    games = _games([("G1", True, False)])
    box = _box([("G1", "P1", 600), ("G1", "P2", 0)])  # P2 has a 0-second row; P3 has no row
    table = player_games(matched, finished_sides(games, 2026), box).table
    played = dict(zip(table["player_id"], table["played"], strict=True))
    assert played == {"P1": True, "P2": False, "P3": False}


def test_unmatched_row_is_excluded_and_counted() -> None:
    matched = _matched(
        [
            ("2026-11-05T12:00:00Z", "ULK", "John Smith", "Out"),
            ("2026-11-05T12:00:00Z", "ULK", "Ghost Player", "Out"),
        ]
    )
    games = _games([("G1", True, False)])
    found = player_games(matched, finished_sides(games, 2026), _box([("G1", "P1", 600)]))
    assert list(found.table["player_id"]) == ["P1"]
    assert found.unmatched_rows == 1


def test_status_under_30_player_games_gives_n_only() -> None:
    matched = _matched([("2026-11-05T12:00:00Z", "ULK", "John Smith", "Out")])
    games = _games([("G1", True, False)])
    report = build_report(games, matched, _box([("G1", "P1", 600)]), 2026)
    assert report["statuses"] == {"Out": {"n": 1}}


def test_status_with_30_player_games_gives_rate_and_interval() -> None:
    # 30 games, Smith listed Out in each; he played in the first 12 of them.
    games = _games([(f"G{i}", True, False) for i in range(30)])
    matched = _matched([("2026-11-05T12:00:00Z", "ULK", "John Smith", "Out")])
    box = _box([(f"G{i}", "P1", 300) for i in range(12)])
    out = build_report(games, matched, box, 2026)["statuses"]["Out"]
    assert out["n"] == 30
    assert out["played"] == 12
    assert out["rate"] == pytest.approx(0.4)
    assert out["ci95"][0] == pytest.approx(wilson(12, 30)[0], abs=1e-6)


def test_wilson_matches_hand_value() -> None:
    low, high = wilson(8, 10)
    assert low == pytest.approx(0.4902, abs=1e-4)
    assert high == pytest.approx(0.9433, abs=1e-4)


def test_unplayed_and_forfeit_games_are_ignored() -> None:
    games = _games([("G1", True, False), ("G2", False, False), ("G3", True, True)])
    sides = finished_sides(games, 2026)
    assert set(sides["game_id"]) == {"G1"}
    assert len(sides) == 2  # the home side and the away side of G1
