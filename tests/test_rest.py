"""Rest features (M5): hand-derived fixtures, leakage under edits from a game on, determinism."""

import numpy as np
import pandas as pd
import pandera.errors
import pytest

from eurohoops.models.rest import REST_SCHEMA, rest_features

COLUMNS = [
    "game_id",
    "season",
    "phase",
    "round",
    "tipoff_utc",
    "home",
    "away",
    "home_score",
    "away_score",
    "played",
    "forfeit",
    "neutral",
]


def _games(rows: list[tuple[str, str, str, str, bool]]) -> pd.DataFrame:
    """Rows of (game_id, tip-off 'YYYY-MM-DD HH:MM' UTC, home, away, played)."""
    frame = pd.DataFrame(
        {
            "game_id": [r[0] for r in rows],
            "season": 2026,
            "phase": "RS",
            "round": range(1, len(rows) + 1),
            "tipoff_utc": pd.to_datetime([r[1] for r in rows], utc=True),
            "home": [r[2] for r in rows],
            "away": [r[3] for r in rows],
            "home_score": [80 if r[4] else 0 for r in rows],
            "away_score": [75 if r[4] else 0 for r in rows],
            "played": [r[4] for r in rows],
            "forfeit": False,
            "neutral": False,
        }
    )
    return frame[COLUMNS]


def _row(out: pd.DataFrame, game_id: str, side: str) -> pd.Series:
    rows = out[(out["game_id"] == game_id) & (out["side"] == side)]
    assert len(rows) == 1
    return rows.iloc[0]


def test_games_last_7d_counts_the_window_and_days_rest_the_previous_game() -> None:
    games = _games(
        [
            ("E1", "2026-10-01 19:00", "PAN", "OLY", True),
            ("E2", "2026-10-04 17:00", "PAN", "ULK", True),
            ("E3", "2026-10-08 17:00", "PAN", "BAR", False),
        ]
    )
    pan = _row(rest_features(games), "E3", "home")
    # Window [Oct 1 17:00, Oct 8 17:00): E1 (Oct 1 19:00) and E2 are in; 2 games.
    assert pan["games_last_7d"] == 2
    # Previous game is E2, 4 days earlier: not short.
    assert pan["days_rest"] == pytest.approx(4.0)
    assert not pan["short_rest"]
    assert pan["team"] == "PAN"


def test_short_rest_after_a_day_and_a_half() -> None:
    games = _games(
        [
            ("E1", "2026-10-08 19:00", "PAN", "OLY", True),
            ("E2", "2026-10-10 17:00", "PAN", "BAR", False),
        ]
    )
    pan = _row(rest_features(games), "E2", "home")
    # Thu 19:00 -> Sat 17:00 = 1 day 22 hours = 46 / 24 days.
    assert pan["days_rest"] == pytest.approx(46 / 24)
    assert pan["short_rest"]
    assert pan["games_last_7d"] == 1


def test_other_comp_prev_is_always_false() -> None:
    games = _games(
        [
            ("E1", "2026-10-01 19:00", "PAN", "OLY", True),
            ("E2", "2026-10-02 19:00", "PAN", "ULK", True),
            ("E3", "2026-10-05 17:00", "PAN", "BAR", False),
        ]
    )
    out = rest_features(games)
    assert not out["other_comp_prev"].any()
    assert list(out.columns) == list(REST_SCHEMA.columns)


def test_season_opener_has_no_previous_game() -> None:
    games = _games([("E1", "2026-10-04 17:00", "A", "B", False)])
    out = rest_features(games)
    for side in ("home", "away"):
        row = _row(out, "E1", side)
        assert row["days_rest"] == 7.0
        assert not row["short_rest"]
        assert row["games_last_7d"] == 0


def test_postponed_game_does_not_count() -> None:
    games = _games(
        [
            ("G1", "2026-10-01 17:00", "A", "B", True),
            ("G2", "2026-10-03 17:00", "A", "C", False),  # postponed, never played
            ("G3", "2026-10-05 17:00", "A", "D", False),
        ]
    )
    row = _row(rest_features(games), "G3", "home")
    # Only G1 counts: 4 days back, one game in the window.
    assert row["days_rest"] == pytest.approx(4.0)
    assert row["games_last_7d"] == 1
    assert not row["short_rest"]


def test_forfeit_counts_when_played() -> None:
    games = _games(
        [
            ("G1", "2026-10-03 17:00", "A", "B", True),
            ("G2", "2026-10-05 17:00", "A", "C", False),
        ]
    )
    games.loc[0, "forfeit"] = True
    row = _row(rest_features(games), "G2", "home")
    assert row["days_rest"] == pytest.approx(2.0)
    assert row["short_rest"]
    assert row["games_last_7d"] == 1


def test_cap_at_seven_days() -> None:
    games = _games(
        [
            ("G1", "2026-10-01 17:00", "A", "B", True),
            ("G2", "2026-10-20 17:00", "A", "B", False),
            ("G3", "2026-10-08 17:00", "C", "D", True),
            ("G4", "2026-10-15 17:00", "C", "D", False),
        ]
    )
    out = rest_features(games)
    # G1 -> G2: 19 days, capped to 7.0; the game is outside the 7-day window.
    capped = _row(out, "G2", "home")
    assert capped["days_rest"] == 7.0
    assert capped["games_last_7d"] == 0
    # G3 -> G4: exactly 7 days: days_rest 7.0, and the half-open window [t - 7d, t) holds G3.
    exact = _row(out, "G4", "home")
    assert exact["days_rest"] == 7.0
    assert exact["games_last_7d"] == 1


def test_tie_at_same_tipoff_does_not_count() -> None:
    games = _games(
        [
            ("G1", "2026-10-03 17:00", "A", "B", True),
            ("G2", "2026-10-03 17:00", "A", "C", False),
        ]
    )
    row = _row(rest_features(games), "G2", "home")
    assert (row["days_rest"], row["games_last_7d"]) == (7.0, 0)


def _schedule(rng: np.random.Generator) -> pd.DataFrame:
    teams = [f"E{i}" for i in range(6)]
    rows = []
    for i in range(40):
        home, away = rng.choice(teams, size=2, replace=False)
        hours = int(rng.integers(0, 60 * 24))
        tip = pd.Timestamp("2026-10-01", tz="UTC") + pd.Timedelta(hours=hours)
        rows.append(
            (f"E{i}", tip.strftime("%Y-%m-%d %H:%M"), home, away, bool(rng.random() < 0.85))
        )
    return _games(rows)


def _edit_from(
    frame: pd.DataFrame, cutoff: pd.Timestamp, keep_id: str, rng: np.random.Generator, tag: str
) -> pd.DataFrame:
    """Delete, move and add games, all at or after ``cutoff`` (``keep_id`` itself is untouched)."""
    edited = frame.copy()
    late = (edited["tipoff_utc"] >= cutoff) & (edited["game_id"] != keep_id)
    drop = late & (rng.random(len(edited)) < 0.3)
    edited = edited[~drop].copy()
    move = (
        (edited["tipoff_utc"] >= cutoff)
        & (edited["game_id"] != keep_id)
        & (rng.random(len(edited)) < 0.5)
    )
    shift = pd.to_timedelta(rng.integers(0, 72, size=int(move.sum())), unit="h")
    edited.loc[move, "tipoff_utc"] = edited.loc[move, "tipoff_utc"] + shift
    teams = pd.concat([frame["home"], frame["away"]]).unique()
    added = []
    for k in range(5):
        home, away = rng.choice(teams, size=2, replace=False)
        tip = cutoff + pd.Timedelta(hours=int(rng.integers(0, 96)))
        added.append((f"{tag}{k}", tip.strftime("%Y-%m-%d %H:%M"), home, away, True))
    edited = pd.concat([edited, _games(added)], ignore_index=True)
    edited["tipoff_utc"] = pd.to_datetime(edited["tipoff_utc"], utc=True)
    return edited


def test_features_ignore_games_at_or_after_tipoff() -> None:
    rng = np.random.default_rng(20261005)
    games = _schedule(rng)
    for _ in range(25):
        g = games.iloc[int(rng.integers(0, len(games)))]
        cutoff = g["tipoff_utc"]
        base = rest_features(games)
        after = rest_features(_edit_from(games, cutoff, g["game_id"], rng, "NG"))
        pd.testing.assert_frame_equal(
            base[base["game_id"] == g["game_id"]].reset_index(drop=True),
            after[after["game_id"] == g["game_id"]].reset_index(drop=True),
        )


def test_features_ignore_scores() -> None:
    rng = np.random.default_rng(7)
    games = _schedule(rng)
    base = rest_features(games)
    noisy = games.copy()
    noisy["home_score"] = rng.integers(0, 200, size=len(noisy))
    noisy["away_score"] = rng.integers(0, 200, size=len(noisy))
    pd.testing.assert_frame_equal(base, rest_features(noisy))


def test_output_follows_games_order_and_is_deterministic() -> None:
    rng = np.random.default_rng(3)
    games = _schedule(rng)
    first = rest_features(games)
    second = rest_features(games)
    pd.testing.assert_frame_equal(first, second)
    assert first.to_csv(index=False) == second.to_csv(index=False)
    assert list(first["game_id"]) == [g for g in games["game_id"] for _ in range(2)]
    assert list(first["side"]) == ["home", "away"] * len(games)


@pytest.mark.parametrize("days", [0.0, 8.0])
def test_schema_rejects_out_of_range_days(days: float) -> None:
    good = rest_features(_games([("G1", "2026-10-04 17:00", "A", "B", False)]))
    bad = good.assign(days_rest=days)
    with pytest.raises(pandera.errors.SchemaError):
        REST_SCHEMA.validate(bad)
