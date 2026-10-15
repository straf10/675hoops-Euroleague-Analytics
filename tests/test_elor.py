"""ELOR model pieces (``models/elor.py``): fade schedule, round index, shares, w0 = 0, centring."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eurohoops.config import ELOR_CV
from eurohoops.models import elo, minutes
from eurohoops.models.elor import (
    Appearances,
    ElorSetting,
    Offsets,
    WalkForwardRatings,
    club_strength,
    elor_diff,
    fade_weight,
    margin_scales,
    offsets,
    roster_strengths,
    round_index,
    season_starts,
    win_probabilities,
)
from eurohoops.models.rapm import RatingLookup
from eurohoops.models.roster import season_rounds
from tests import elor_synthetic as syn


def _sorted(games: pd.DataFrame) -> pd.DataFrame:
    return games.sort_values("tipoff_utc").reset_index(drop=True)


def test_fade_schedule() -> None:
    r = np.arange(1, 12)
    w = fade_weight(r, 0.5, 4)
    np.testing.assert_allclose(w[:5], [0.5, 0.375, 0.25, 0.125, 0.0])
    assert (w[4:] == 0.0).all()
    assert float(fade_weight(1, 0.35, 24)) == 0.35
    assert float(fade_weight(24, 0.2, 24)) == pytest.approx(0.2 / 24)
    assert float(fade_weight(25, 0.2, 24)) == 0.0
    assert (fade_weight(r, 0.0, 8) == 0.0).all()


def test_round_index_counts_distinct_cutoffs_and_keeps_a_postponed_game_in_its_round() -> None:
    games, _ = syn.games_and_box()
    late = games.copy()
    # Postpone round 1's second 2025 game past round 3: it keeps round 1's index.
    row = late.index[(late["game_id"] == "E2025_11")][0]
    late.loc[row, "tipoff_utc"] = syn.round_start(2025, 3) + pd.Timedelta(days=2)
    ordered = _sorted(late)
    idx = dict(zip(ordered["game_id"], round_index(ordered), strict=True))
    assert idx["E2025_10"] == idx["E2025_11"] == 1
    assert idx["E2025_20"] == 2 and idx["E2025_41"] == 4
    assert idx["E2024_10"] == 1  # every season restarts at 1


def test_w0_zero_is_live_elo_exactly() -> None:
    games = _sorted(syn.games_and_box()[0])
    arrays = elo.prepare(games)
    diff = elo.replay(arrays, ELOR_CV.elo_params)
    rng = np.random.default_rng(1)
    offs = Offsets(
        rng.normal(0, 50, len(games)), rng.normal(0, 50, len(games)), np.ones(len(games), bool)
    )
    for n in ELOR_CV.n_rounds:
        same = elor_diff(diff, round_index(games), offs, ElorSetting(0.0, n))
        np.testing.assert_array_equal(same, diff)
        np.testing.assert_array_equal(
            win_probabilities(same), [elo.win_probability(d) for d in diff]
        )
    moved = elor_diff(diff, round_index(games), offs, ElorSetting(0.5, 4))
    assert not np.array_equal(moved, diff)


def test_blended_rating_matches_the_protocol_formula_by_hand() -> None:
    diff = np.array([100.0, 100.0, 100.0])
    rounds = np.array([1, 3, 9])
    offs = Offsets(np.array([40.0, 40.0, 40.0]), np.array([-20.0, -20.0, -20.0]), np.ones(3, bool))
    out = elor_diff(diff, rounds, offs, ElorSetting(0.5, 8))
    # w(1) = 0.5, w(3) = 0.5 * 6/8 = 0.375, w(9) = 0: d = 100 + w * (40 - (-20))
    np.testing.assert_allclose(out, [130.0, 122.5, 100.0])


def test_share_is_proj_hc_for_a_player_who_played_his_clubs_last_game() -> None:
    games, box = syn.games_and_box()
    games = _sorted(games)
    app = Appearances(games, box)
    proj = minutes.projected_shares(games, box)
    cutoffs = minutes.round_cutoffs(games)
    checked = 0
    for i in np.flatnonzero((games["season"] == 2025).to_numpy()):
        game_id, cutoff = str(games["game_id"].iloc[i]), float(cutoffs.iloc[i])
        part = proj[proj["game_id"] == game_id]
        for player, share in zip(part["player_id"], part["share"], strict=True):
            assert app.share(player, 2025, cutoff) == pytest.approx(share, abs=1e-12)
            checked += 1
    assert checked > 50


def test_share_of_a_transfer_uses_his_previous_club() -> None:
    games, box = syn.games_and_box()
    games = _sorted(games)
    app = Appearances(games, box)
    first_2026 = syn.round_start(2026, 1).timestamp()
    # A4 played every 2025 game for A: his whole-season share with A.
    rows = box[box["game_id"].str.startswith("E2025") & (box["team"] == "A")]
    expected = min(1.0, 5 * rows.loc[rows["player_id"] == "A4", "sec"].sum() / rows["sec"].sum())
    assert app.share("A4", 2026, first_2026) == pytest.approx(expected)
    # No appearance in this or last season: no share; unknown player: no share.
    assert app.share("A4", 2028, syn.round_start(2026, 4).timestamp() + 1e9) == 0.0
    assert app.share("B9", 2026, first_2026) == 0.0
    # Before any box score at all.
    assert app.share("A1", 2024, syn.round_start(2024, 1).timestamp()) == 0.0


def test_club_strength_caps_shares_at_five_and_counts_unrated() -> None:
    games, box = syn.games_and_box()
    app = Appearances(_sorted(games), box)
    cutoff = syn.round_start(2025, 1).timestamp()
    many = [f"{c}{n}" for c in "AB" for n in range(1, 5)] + ["Z9"]
    out = club_strength(many, "A", 2025, cutoff, appearances=app, rating=syn.fake_rating)
    shares = {p: app.share(p, 2025, cutoff) for p in many}
    total = sum(shares.values())
    assert total > 5
    expected = sum(
        5 / total * s * (syn.fake_rating(2025, cutoff, p, "A") or 0.0) for p, s in shares.items()
    )
    assert out.q == pytest.approx(expected)
    assert (out.rostered, out.with_share, out.unrated) == (9, 8, 1)


def _strengths(rosters: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    games, box = syn.games_and_box()
    games = _sorted(games)
    rosters = syn.roster() if rosters is None else rosters
    app = Appearances(games, box)
    folds = games[games["season"] >= 2025].reset_index(drop=True)
    out = roster_strengths(folds, rosters, app, syn.fake_rating, rule="strict")
    return games, out


def test_roster_strengths_follow_signings_and_departures() -> None:
    _, table = _strengths()
    b = table[(table["season"] == 2026) & (table["club"] == "B")].sort_values("cutoff")
    assert b["rostered"].tolist() == [5, 5, 6, 6]  # B1-B4 and A4; B9 signs after round 2
    assert b["unrated"].tolist() == [0, 0, 1, 1]
    c = table[(table["season"] == 2026) & (table["club"] == "C")].sort_values("cutoff")
    assert c["rostered"].tolist() == [4, 4, 4, 3]  # C3 leaves between rounds 3 and 4
    assert set(table["season"]) == {2025, 2026}


def test_roster_strengths_skip_cutoffs_without_m3_state() -> None:
    games, box = syn.games_and_box()
    games = _sorted(games)
    app = Appearances(games, box)
    out = roster_strengths(
        games, syn.roster(), app, syn.fake_rating, rule="strict", has_state=lambda s, c: s > 2025
    )
    assert set(out["season"]) == {2026}


def _offsets(rosters: pd.DataFrame | None = None) -> tuple[pd.DataFrame, Offsets, np.ndarray]:
    games, table = _strengths(rosters)
    arrays = elo.prepare(games)
    diff = elo.replay(arrays, ELOR_CV.elo_params)
    starts = season_starts(arrays, ELOR_CV.elo_params, [2024, 2025, 2026])
    scales = margin_scales(games, diff)
    poss = pd.Series(syn.POSSESSIONS, index=games["game_id"])
    return games, offsets(games, table, starts, scales, poss), diff


def test_offsets_are_centred_and_unavailable_without_an_earlier_season() -> None:
    games, offs, _ = _offsets()
    in_2024 = (games["season"] == 2024).to_numpy()
    assert not offs.available[in_2024].any()  # no strengths (and no scale) in 2024
    assert (offs.home[in_2024] == 0.0).all()
    first = ((games["season"] == 2025) & (games["round"] == 1)).to_numpy()
    assert offs.available[first].all()
    # Every club plays once in round 1: the four offsets sum to zero (centred).
    assert offs.home[first].sum() + offs.away[first].sum() == pytest.approx(0.0, abs=1e-9)


def test_centre_cancels_in_the_game_difference() -> None:
    """A fifth club on the roster list moves the centre, never a game's offset difference."""
    _, base, _ = _offsets()
    extra = syn.roster()
    extra = pd.concat(
        [
            extra,
            extra[extra["club"] == "A"].assign(club="E", player_id=lambda f: "E" + f["player_id"]),
        ],
        ignore_index=True,
    )
    games, moved, _ = _offsets(extra)
    ok = base.available & moved.available
    np.testing.assert_allclose((moved.home - moved.away)[ok], (base.home - base.away)[ok])
    assert not np.allclose(moved.home[ok], base.home[ok])
    assert ok[(games["season"] >= 2025).to_numpy()].all()


def test_margin_scales_use_earlier_seasons_only() -> None:
    games = _sorted(syn.games_and_box()[0])
    diff = elo.replay(elo.prepare(games), ELOR_CV.elo_params)
    scales = margin_scales(games, diff)
    assert np.isnan(scales[2024])
    early = (games["season"] == 2024).to_numpy()
    margin = (games["home_score"] - games["away_score"]).to_numpy(dtype=float)
    assert scales[2025] == elo.fit_margin_scale(diff[early], margin[early])


def test_walk_forward_ratings_map_cutoffs_to_lookups() -> None:
    games = _sorted(syn.games_and_box()[0])
    lookup = RatingLookup({"A1": 1.5}, {"A1": -0.5})
    lookups: list[RatingLookup | None] = [
        None if s == 2024 else lookup for s in games["season"].tolist()
    ]
    source = WalkForwardRatings(games, lookups)
    rounds = season_rounds(games)
    assert not source.has_state(2024, rounds.first[2024])
    assert source.has_state(2025, rounds.first[2025])
    assert source(2025, rounds.first[2025], "A1", "A") == 1.0
    assert source(2025, rounds.first[2025], "B1", "B") is None
    assert source(2024, rounds.first[2024], "A1", "A") is None
