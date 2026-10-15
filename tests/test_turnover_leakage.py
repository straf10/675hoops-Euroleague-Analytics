"""Leakage tests for the M5 retune's new code (roster continuity and the walk-forward residual fit).

* ``turnover.roster_continuity``: a game's ``c_home`` / ``c_away`` use only current-season games
  tipped off before the game's round cutoff (``minutes.round_cutoffs``) and last season's seconds.
  Editing a game's player rows in round k therefore cannot move the continuity of any game in
  rounds <= k of that season, nor of any earlier season.
* ``m5.fit_residual``: a game's ``adjustment``, ``r_home`` and ``r_away`` use only rows tipped off
  before its round cutoff. With ``season_only=True`` the ridge also resets at each season start,
  so nothing from the previous season may reach a current-season value.

The synthetic league has 4 teams, seasons 2025 and 2026, 3 rounds per season, 2 games per round
(every team plays once per round). Players: ``{team}1`` and ``{team}2`` play every 2025 game
(600 s and 400 s); in 2026 round 1 only ``{team}1`` plays, round 2 both, round 3 ``{team}3`` too.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eurohoops.models.m5 import ResidualFit, fit_residual
from eurohoops.models.turnover import roster_continuity

SEED = 7
PAIRINGS = {
    1: (("A", "B"), ("C", "D")),
    2: (("A", "C"), ("B", "D")),
    3: (("A", "D"), ("B", "C")),
}
SEASON_START = {2025: "2025-10-01", 2026: "2026-10-01"}
KW = {"half_life_days": 200.0, "residual_ridge": 2.0, "rest_ridge": 1.0}
FIT_FIELDS = ("adjustment", "r_home", "r_away")


def _league(seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    games: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for season, start in SEASON_START.items():
        for rnd, pairs in PAIRINGS.items():
            for i, (home, away) in enumerate(pairs):
                game_id = f"S{season}-R{rnd}-{i}"
                games.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "phase": "RS",
                        "round": rnd,
                        "tipoff_utc": pd.Timestamp(start, tz="UTC")
                        + pd.Timedelta(days=7 * (rnd - 1), hours=i),
                        "home": home,
                        "away": away,
                        "played": True,
                        "forfeit": False,
                        "neutral": False,
                    }
                )
                for team in (home, away):
                    for n, sec in _seconds(season, rnd, rng):
                        rows.append(
                            {
                                "game_id": game_id,
                                "team": team,
                                "player_id": f"{team}{n}",
                                "sec": sec,
                            }
                        )
    return pd.DataFrame(games), pd.DataFrame(rows)


def _seconds(season: int, rnd: int, rng: np.random.Generator) -> list[tuple[int, int]]:
    if season == 2025:
        return [(1, 600), (2, 400)]
    active = {1: 1, 2: 2, 3: 3}[rnd]  # round 1: p1; round 2: p1, p2; round 3: p1..p3
    players = range(1, active + 1)
    return [(n, int(rng.integers(300, 1200))) for n in players]


def _continuity(games: pd.DataFrame, player_games: pd.DataFrame) -> pd.DataFrame:
    out: pd.DataFrame = roster_continuity(games, player_games).set_index("game_id")
    return out


def _up_to(games: pd.DataFrame, season: int, rnd: int) -> list[str]:
    """Games of earlier seasons and games of ``season`` in rounds <= ``rnd``."""
    mask = (games["season"] < season) | ((games["season"] == season) & (games["round"] <= rnd))
    return games.loc[mask, "game_id"].astype(str).tolist()


def _targets(games: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 5.0, len(games)), rng.normal(0.0, 1.0, (len(games), 2))


def _cutoff(games: pd.DataFrame, season: int, rnd: int) -> pd.Timestamp:
    """First tip-off of (season, round), computed directly from the games frame."""
    mask = (games["season"] == season) & (games["round"] == rnd)
    return pd.Timestamp(games.loc[mask, "tipoff_utc"].min())


# --- roster_continuity -------------------------------------------------------------------------


def test_roster_continuity_hand_checked_carry_share() -> None:
    games, player_games = _league(SEED)
    out = _continuity(games, player_games)
    # 2025: A1 plays 600 s and A2 400 s in each of A's 3 games, so A1 holds 1800 of 3000 team
    # seconds (0.6). 2026 round 1 has only A1 (and C1) before round 2, so the round-2 games carry
    # 0.6 for the home side A and for the away side C.
    assert out.loc["S2026-R2-0", "c_home"] == pytest.approx(0.6)
    assert out.loc["S2026-R2-0", "c_away"] == pytest.approx(0.6)
    # Round 1 has no earlier current-season game: c = 1.
    assert out.loc["S2026-R1-0", "c_home"] == 1.0
    assert out.loc["S2026-R1-0", "c_away"] == 1.0
    # Round 3: A1 and A2 both played in rounds 1-2, so the whole previous-season roster carries.
    assert out.loc["S2026-R3-0", "c_home"] == pytest.approx(1.0)


@pytest.mark.parametrize("rnd", [1, 2, 3])
def test_roster_continuity_edit_in_round_k_leaves_rounds_up_to_k_unchanged(rnd: int) -> None:
    games, player_games = _league(SEED)
    base = _continuity(games, player_games)
    game_id = f"S2026-R{rnd}-0"
    edited = player_games.copy()
    rows = edited["game_id"].eq(game_id).to_numpy()
    edited.loc[rows, "sec"] = edited.loc[rows, "sec"] * 2 + 50
    new_player = pd.DataFrame([{"game_id": game_id, "team": "A", "player_id": "A9", "sec": 300}])
    moved = _continuity(games, pd.concat([edited, new_player], ignore_index=True))
    ids = _up_to(games, 2026, rnd)
    pd.testing.assert_frame_equal(base.loc[ids], moved.loc[ids], check_exact=True)


def test_roster_continuity_control_prior_round_edit_moves_later_games() -> None:
    """The same kind of edit, made in an earlier round, does change a later game's continuity:
    A2 (who played last season) appears in round 1, so round 2's A game now carries 1.0, not 0.6.
    """
    games, player_games = _league(SEED)
    base = _continuity(games, player_games)
    extra = pd.DataFrame([{"game_id": "S2026-R1-0", "team": "A", "player_id": "A2", "sec": 300}])
    moved = _continuity(games, pd.concat([player_games, extra], ignore_index=True))
    assert base.loc["S2026-R2-0", "c_home"] == pytest.approx(0.6)
    assert moved.loc["S2026-R2-0", "c_home"] == pytest.approx(1.0)


# --- fit_residual ------------------------------------------------------------------------------


REST_CASES = pytest.mark.parametrize("with_rest", [False, True], ids=["no_rest", "rest"])


def _fit(
    games: pd.DataFrame,
    target: np.ndarray,
    rest: np.ndarray,
    *,
    with_rest: bool,
    season_only: bool,
) -> ResidualFit:
    """``with_rest=False`` is the retune's configuration (no rest features, rest ridge 0)."""
    if with_rest:
        return fit_residual(games, target, rest, season_only=season_only, **KW)
    kw = {**KW, "rest_ridge": 0.0}
    return fit_residual(games, target, None, season_only=season_only, **kw)


def _assert_fit_equal(before: object, after: object, mask: np.ndarray, err: str) -> None:
    for name in FIT_FIELDS:
        np.testing.assert_array_equal(
            getattr(after, name)[mask], getattr(before, name)[mask], err_msg=f"{err}: {name}"
        )


@REST_CASES
@pytest.mark.parametrize("season_only", [True, False])
def test_fit_residual_targets_at_or_after_round_cutoff_do_not_reach_earlier_games(
    season_only: bool, with_rest: bool
) -> None:
    games, _ = _league(SEED)
    target, rest = _targets(games, SEED)
    base = _fit(games, target, rest, with_rest=with_rest, season_only=season_only)
    late = (games["tipoff_utc"] >= _cutoff(games, 2026, 2)).to_numpy()
    early = ~late
    rng = np.random.default_rng(SEED + 1)
    target2 = target.copy()
    target2[late] += rng.normal(0.0, 50.0, int(late.sum()))
    moved = _fit(games, target2, rest, with_rest=with_rest, season_only=season_only)
    _assert_fit_equal(base, moved, early, f"season_only={season_only}")


@REST_CASES
@pytest.mark.parametrize("season_only", [True, False])
def test_fit_residual_control_earlier_target_edit_moves_later_games(
    season_only: bool, with_rest: bool
) -> None:
    games, _ = _league(SEED)
    target, rest = _targets(games, SEED)
    base = _fit(games, target, rest, with_rest=with_rest, season_only=season_only)
    first_r1 = int(np.flatnonzero((games["season"] == 2026) & (games["round"] == 1))[0])
    target2 = target.copy()
    target2[first_r1] += 10.0
    moved = _fit(games, target2, rest, with_rest=with_rest, season_only=season_only)
    later = ((games["season"] == 2026) & (games["round"] == 2)).to_numpy()
    assert not np.array_equal(moved.r_home[later], base.r_home[later])


@REST_CASES
def test_season_only_fit_ignores_previous_season_targets(with_rest: bool) -> None:
    games, _ = _league(SEED)
    target, rest = _targets(games, SEED)
    base = _fit(games, target, rest, with_rest=with_rest, season_only=True)
    first_2025 = int(np.flatnonzero((games["season"] == 2025).to_numpy())[0])
    target2 = target.copy()
    target2[first_2025] += 10.0
    moved = _fit(games, target2, rest, with_rest=with_rest, season_only=True)
    current = (games["season"] == 2026).to_numpy()
    _assert_fit_equal(base, moved, current, "season_only reset")
    # control: without the reset the previous-season edit does reach current-season values
    all_base = _fit(games, target, rest, with_rest=with_rest, season_only=False)
    all_moved = _fit(games, target2, rest, with_rest=with_rest, season_only=False)
    assert not np.array_equal(all_moved.r_home[current], all_base.r_home[current])
