"""ELOR model pieces (``models/elor.py``): fade schedule, round index, shares, w0 = 0, centring."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from eurohoops.config import ELOR_CV
from eurohoops.models import elo, minutes
from eurohoops.models.elor import (
    Appearances,
    ElorSetting,
    NewcomerPrior,
    Offsets,
    WalkForwardRatings,
    club_strength,
    elor_diff,
    fade_weight,
    margin_scales,
    newcomer_priors,
    offsets,
    roster_strengths,
    round_index,
    season_starts,
    win_probabilities,
)
from eurohoops.models.minutes import round_cutoffs
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
    assert app.share("A1", 2023, syn.round_start(2023, 1).timestamp()) == 0.0


PRIOR = NewcomerPrior(
    2025,
    rating=-2.0,
    share=0.3,
    rating_players=1,
    rating_seconds=1.0,
    share_player_games=1,
    history=(2024,),
)


def test_club_strength_uses_the_prior_and_caps_shares_at_five() -> None:
    games, box = syn.games_and_box()
    app = Appearances(_sorted(games), box)
    cutoff = syn.round_start(2025, 1).timestamp()
    many = [f"{c}{n}" for c in "AB" for n in range(1, 5)] + ["Z9"]
    out = club_strength(
        many, "A", 2025, cutoff, appearances=app, rating=syn.fake_rating, prior=PRIOR
    )
    shares = {p: app.share(p, 2025, cutoff) for p in many}
    assert shares["Z9"] == 0.0
    shares["Z9"] = PRIOR.share
    values = {p: syn.fake_rating(2025, cutoff, p, "A") for p in many}
    values["Z9"] = PRIOR.rating
    total = sum(shares.values())
    assert total > 5
    expected = sum(5 / total * shares[p] * float(values[p] or 0.0) for p in many)
    assert out.q == pytest.approx(expected)
    assert (out.rostered, out.share_prior, out.rating_prior) == (9, 1, 1)


def test_rating_and_share_priors_apply_separately() -> None:
    games, box = syn.games_and_box()
    app = Appearances(_sorted(games), box)
    cutoff = syn.round_start(2025, 1).timestamp()

    def no_a1(season: int, c: float, player: str, club: str) -> float | None:
        return None if player == "A1" else syn.fake_rating(season, c, player, club)

    out = club_strength(["A1"], "A", 2025, cutoff, appearances=app, rating=no_a1, prior=PRIOR)
    share = app.share("A1", 2025, cutoff)
    assert share > 0  # his own share, the prior rating
    assert (out.share_prior, out.rating_prior) == (0, 1)
    assert out.q == pytest.approx(share * PRIOR.rating)
    # Rated but no share (never played for anyone in 2024-2025): prior share, own rating.
    out = club_strength(
        ["Q1"], "A", 2025, cutoff, appearances=app, rating=syn.fake_rating, prior=PRIOR
    )
    assert (out.share_prior, out.rating_prior) == (1, 0)
    assert out.q == pytest.approx(PRIOR.share * syn.fake_value(2025, cutoff, "Q1"))


def _priors(
    games: pd.DataFrame | None = None, box: pd.DataFrame | None = None
) -> dict[int, NewcomerPrior]:
    base_games, base_box = syn.games_and_box()
    games = _sorted(base_games if games is None else games)
    box = base_box if box is None else box
    app = Appearances(games, box)
    return newcomer_priors(app, syn.ratings(games, box).at_season_end, [2024, 2025, 2026])


def _season_means(
    games: pd.DataFrame, box: pd.DataFrame, sigma: int, value: Callable[[int, str], float | None]
) -> tuple[float, float, float]:
    """By hand from the box: (all_mean, new_mean, newcomer weight) of season sigma, weights =
    seconds in sigma before its last round cutoff; newcomers are players first seen in sigma."""
    last = float(round_cutoffs(games)[games["season"] == sigma].max())
    ids = games.set_index("game_id")
    tip = ids["tipoff_utc"].map(pd.Timestamp.timestamp)
    rows = box.assign(t=box["game_id"].map(tip), s=box["game_id"].map(ids["season"]))
    first = rows.groupby("player_id")["s"].min()
    rows = rows[(rows["s"] == sigma) & (rows["t"] < last)]
    weights = rows.groupby("player_id")["sec"].sum().astype(float)
    means = {p: (weights[p] * float(value(sigma, p) or 0.0)) for p in weights.index}
    all_mean = sum(means.values()) / float(weights.sum())
    newcomers = [p for p in weights.index if first[p] == sigma]
    new_w = float(weights[newcomers].sum())
    new_mean = sum(means[p] for p in newcomers) / new_w
    return all_mean, new_mean, new_w


def test_newcomer_priors_by_hand() -> None:
    games, box = syn.games_and_box()
    games = _sorted(games)
    priors = _priors()
    value = syn.ratings(games, box).at_season_end
    assert np.isnan(priors[2024].rating) and np.isnan(priors[2024].share)  # no newcomer season
    assert np.isnan(priors[2024].gap) and np.isfinite(priors[2024].anchor)
    # 2023 has no newcomers, so 2025 is anchored on 2024's mean with 2024's gap (C5).
    m24, n24, w24 = _season_means(games, box, 2024, value)
    assert priors[2025].anchor == pytest.approx(m24)
    assert priors[2025].gap == pytest.approx(n24 - m24)
    assert priors[2025].rating == pytest.approx(n24)
    c24 = games[(games["season"] == 2024) & ((games["home"] == "C") | (games["away"] == "C"))]
    rows = box[box["game_id"].isin(c24["game_id"]) & (box["team"] == "C")]
    team_sec = rows.groupby("game_id")["sec"].sum()
    c5 = rows[rows["player_id"] == "C5"].set_index("game_id")["sec"]
    share = float(np.minimum(1.0, 5 * c5 / team_sec).mean())
    assert priors[2025].share == pytest.approx(share)
    assert priors[2025].history == (2024,) and priors[2025].rating_players == 1
    # 2026: anchor on 2025's mean, gap pooled over 2024 and 2025 by newcomer weight.
    m25, n25, w25 = _season_means(games, box, 2025, value)
    assert priors[2026].anchor == pytest.approx(m25)
    assert priors[2026].gap == pytest.approx((w24 * (n24 - m24) + w25 * (n25 - m25)) / (w24 + w25))
    assert priors[2026].rating == pytest.approx(priors[2026].anchor + priors[2026].gap)
    assert priors[2026].all_mean[2024] == pytest.approx(m24)
    assert set(priors[2026].all_mean) == {2023, 2024, 2025}
    assert priors[2026].all_mean[2025] == pytest.approx(m25)
    assert priors[2026].history == (2024, 2025) and priors[2026].share_player_games == 8
    assert priors[2026].rating != 0.0 and priors[2026].share > 0.0


def test_rating_prior_is_the_previous_season_mean_plus_the_pooled_newcomer_gap() -> None:
    """Worked by hand. Every box row has 1000 seconds, so each player's weight in a season is
    1000 x his games before the last round cutoff: 3 games (rounds 1-3) for everyone who plays
    the whole season. Ratings: season value c plus 1 for the season's newcomer (C5 in 2024,
    A5 in 2025). 2024: 17 rated players, all_mean = c24 + 3000/(17 x 3000) = c24 + 1/17, new_mean
    = c24 + 1, gap = 16/17. 2025: 18 players, all_mean = c25 + 1/18, gap = 17/18. Pooled gap
    for 2026 (equal newcomer weights 3000 each) = (16/17 + 17/18) / 2. Prior = all_mean(2025)
    + pooled gap."""
    games, box = syn.games_and_box()
    games = _sorted(games)
    box = box.assign(sec=1000)
    base = {2024: 2.0, 2025: 5.0}
    newcomers = {(2024, "C5"), (2025, "A5")}

    def value(sigma: int, player: str) -> float | None:
        return base.get(sigma, 0.0) + (1.0 if (sigma, player) in newcomers else 0.0)

    app = Appearances(games, box)
    priors = newcomer_priors(app, value, [2025, 2026])
    gap_24, gap_25 = 16 / 17, 17 / 18
    assert priors[2025].anchor == pytest.approx(2.0 + 1 / 17)
    assert priors[2025].gap == pytest.approx(gap_24)
    assert priors[2025].rating == pytest.approx(3.0)
    assert priors[2025].rating_seconds == pytest.approx(3000.0)
    assert priors[2026].anchor == pytest.approx(5.0 + 1 / 18)
    assert priors[2026].gap == pytest.approx((gap_24 + gap_25) / 2)
    assert priors[2026].rating == pytest.approx(5.0 + 1 / 18 + (gap_24 + gap_25) / 2)
    assert priors[2026].rating_seconds == pytest.approx(6000.0)
    assert priors[2026].all_mean[2024] == pytest.approx(2.0 + 1 / 17)
    assert priors[2026].all_mean[2025] == pytest.approx(5.0 + 1 / 18)


def _shifted(
    base: Callable[[int, str], float | None], by: Callable[[int], float]
) -> Callable[[int, str], float | None]:
    def out(season: int, player: str) -> float | None:
        value = base(season, player)
        return None if value is None else value + by(season)

    return out


def _priors_with(by: Callable[[int], float]) -> dict[int, NewcomerPrior]:
    games, box = syn.games_and_box()
    games = _sorted(games)
    base = syn.ratings(games, box).at_season_end
    return newcomer_priors(Appearances(games, box), _shifted(base, by), [2024, 2025, 2026])


@pytest.mark.parametrize("c", [3.0, -7.5])
def test_rating_prior_shifts_with_a_constant_shift_of_every_season(c: float) -> None:
    base = _priors_with(lambda s: 0.0)
    shifted = _priors_with(lambda s: c)
    for target in (2025, 2026):
        assert shifted[target].rating == pytest.approx(base[target].rating + c)
        assert shifted[target].gap == pytest.approx(base[target].gap)
        assert shifted[target].share == base[target].share


@pytest.mark.parametrize(("target", "old"), [(2025, 2023), (2026, 2023), (2026, 2024)])
def test_shifting_a_season_two_or_more_back_leaves_the_prior_unchanged(
    target: int, old: int
) -> None:
    base = _priors_with(lambda s: 0.0)[target]
    moved = _priors_with(lambda s: 4.25 if s == old else 0.0)[target]
    assert moved.rating == pytest.approx(base.rating)
    assert moved.gap == pytest.approx(base.gap)


@pytest.mark.parametrize("target", [2025, 2026])
def test_shifting_the_previous_season_shifts_the_prior_by_exactly_that(target: int) -> None:
    base = _priors_with(lambda s: 0.0)[target]
    moved = _priors_with(lambda s: 4.25 if s == target - 1 else 0.0)[target]
    assert moved.rating == pytest.approx(base.rating + 4.25)
    assert moved.gap == pytest.approx(base.gap)


@pytest.mark.parametrize("target", [2025, 2026])
def test_newcomer_prior_ignores_edits_and_removals_from_its_season_on(target: int) -> None:
    games, box = syn.games_and_box()
    base = _priors()[target]
    late_ids = set(games.loc[games["season"] >= target, "game_id"])
    edited_box = box.copy()
    rows = edited_box["game_id"].isin(late_ids).to_numpy()
    edited_box.loc[rows, "sec"] = edited_box.loc[rows, "sec"] * 3 + 7
    newcomer = pd.DataFrame(
        [{"game_id": g, "team": "B", "player_id": "N1", "sec": 2000} for g in sorted(late_ids)]
    )
    edited = _priors(games, pd.concat([edited_box, newcomer], ignore_index=True))[target]
    assert edited == base
    kept = games[games["season"] < target]
    removed = _priors(kept, box[box["game_id"].isin(set(kept["game_id"]))])[target]
    assert removed == base


def test_control_an_earlier_season_edit_moves_the_prior() -> None:
    games, box = syn.games_and_box()
    base = _priors()[2025]
    rows = (box["player_id"] == "C5") & box["game_id"].str.startswith("E2024")
    box.loc[rows, "sec"] = 2390
    moved = _priors(games, box)[2025]
    assert moved.share != base.share


def _strengths(rosters: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    games, box = syn.games_and_box()
    games = _sorted(games)
    rosters = syn.roster() if rosters is None else rosters
    app = Appearances(games, box)
    source = syn.ratings(games, box)
    priors = newcomer_priors(app, source.at_season_end, [2025, 2026])
    folds = games[games["season"] >= 2025].reset_index(drop=True)
    out = roster_strengths(folds, rosters, app, source, priors=priors)
    return games, out


def test_roster_strengths_follow_signings_departures_and_newcomers() -> None:
    _, table = _strengths()
    t26 = table[table["season"] == 2026].sort_values("cutoff")
    b = t26[t26["club"] == "B"]
    assert b["rostered"].tolist() == [5, 5, 6, 6]  # B1-B4 and A4; B9 signs after round 2
    assert b["share_prior"].tolist() == [0, 0, 1, 1]  # B9 never plays
    assert b["rating_prior"].tolist() == [0, 0, 1, 1]
    c = t26[t26["club"] == "C"]
    assert c["rostered"].tolist() == [5, 5, 5, 4]  # C3 leaves between rounds 3 and 4
    # D5 is on the prior until his first game (round 3) is before the cutoff: round 4.
    d = t26[t26["club"] == "D"]
    assert d["share_prior"].tolist() == [1, 1, 1, 0]
    assert d["rating_prior"].tolist() == [1, 1, 1, 0]
    assert set(table["season"]) == {2025, 2026}


def test_newcomer_switches_to_his_own_values_at_the_first_cutoff_after_his_debut() -> None:
    games, box = syn.games_and_box()
    games = _sorted(games)
    app = Appearances(games, box)
    source = syn.ratings(games, box)
    prior = newcomer_priors(app, source.at_season_end, [2026])[2026]
    r3, r4 = (float(syn.round_start(2026, r).timestamp()) for r in (3, 4))
    own_share = app.share("D5", 2026, r4)
    own_rating = source(2026, r4, "D5", "D")
    assert app.share("D5", 2026, r3) == 0.0 and source(2026, r3, "D5", "D") is None
    assert own_share > 0 and own_rating is not None
    alone = club_strength(["D5"], "D", 2026, r4, appearances=app, rating=source, prior=prior)
    assert alone.q == pytest.approx(own_share * own_rating)
    before = club_strength(["D5"], "D", 2026, r3, appearances=app, rating=source, prior=prior)
    assert before.q == pytest.approx(prior.share * prior.rating)
    assert before.q != 0.0  # the prior is nonzero and used


def test_roster_strengths_skip_cutoffs_without_m3_state() -> None:
    games, box = syn.games_and_box()
    games = _sorted(games)
    app = Appearances(games, box)
    priors = newcomer_priors(app, syn.ratings(games, box).at_season_end, [2025, 2026])
    out = roster_strengths(
        games[games["season"] >= 2025],
        syn.roster(),
        app,
        syn.fake_rating,
        priors=priors,
        has_state=lambda s, c: s > 2025,
    )
    assert set(out["season"]) == {2026}


def _offsets(rosters: pd.DataFrame | None = None) -> tuple[pd.DataFrame, Offsets, np.ndarray]:
    games, table = _strengths(rosters)
    arrays = elo.prepare(games)
    diff = elo.replay(arrays, ELOR_CV.elo_params)
    starts = season_starts(arrays, ELOR_CV.elo_params, [2023, 2024, 2025, 2026])
    scales = margin_scales(games, diff)
    poss = pd.Series(syn.POSSESSIONS, index=games["game_id"])
    return games, offsets(games, table, starts, scales, poss), diff


def test_offsets_are_centred_and_unavailable_outside_the_folds() -> None:
    games, offs, _ = _offsets()
    early = (games["season"] < 2025).to_numpy()
    assert not offs.available[early].any()  # no strengths before the folds
    assert (offs.home[early] == 0.0).all()
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
    assert np.isnan(scales[2023])
    early = (games["season"] < 2025).to_numpy()
    margin = (games["home_score"] - games["away_score"]).to_numpy(dtype=float)
    assert scales[2025] == elo.fit_margin_scale(diff[early], margin[early])


def test_walk_forward_ratings_need_a_lookup_and_an_earlier_game() -> None:
    games, box = syn.games_and_box()
    games = _sorted(games)
    lookup = RatingLookup({"A1": 1.5, "D5": 2.0, "Q1": 1.0}, {"A1": -0.5})
    lookups: list[RatingLookup | None] = [
        None if s == 2023 else lookup for s in games["season"].tolist()
    ]
    source = WalkForwardRatings(games, lookups, box)
    rounds = season_rounds(games)
    assert not source.has_state(2023, rounds.first[2023])
    assert source.has_state(2025, rounds.first[2025])
    assert source(2025, rounds.first[2025], "A1", "A") == 1.0
    assert source(2025, rounds.first[2025], "B1", "B") is None  # not in the lookup
    assert source(2023, rounds.first[2023], "A1", "A") is None  # no state
    assert source(2025, rounds.first[2025], "Q1", "A") is None  # in the lookup, never played
    r3, r4 = (float(syn.round_start(2026, r).timestamp()) for r in (3, 4))
    assert source(2026, r3, "D5", "D") is None  # debuts in round 3: not before its cutoff
    assert source(2026, r4, "D5", "D") == 2.0
    assert source.at_season_end(2025, "A1") == 1.0
    assert source.at_season_end(2030, "A1") is None
