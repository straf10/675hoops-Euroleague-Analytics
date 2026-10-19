"""Candidate ``blend`` (docs/models/candidate_elo_blend.md): ridge margin model and the backtest."""

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval.blend_backtest import WEIGHT_GRID, run_blend
from eurohoops.models.ridge_margin import RidgeParams, ridge_margin_forecast
from tests.conftest import make_games


def as_rated(games: pd.DataFrame) -> pd.DataFrame:
    frame = games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    frame["rated"] = (frame["played"] & ~frame["forfeit"]).astype(bool)
    frame["margin"] = (frame["home_score"] - frame["away_score"]).astype("float64")
    return frame


def one_game(day: str, neutral: bool, home: str = "AAA", away: str = "BBB") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "tipoff_utc": pd.to_datetime([f"{day}T18:00:00Z"], utc=True),
            "home": [home],
            "away": [away],
            "neutral": [neutral],
            "rated": [True],
            "margin": [10.0],
        }
    )


def test_minimum_norm_ridge_fits_one_game_exactly() -> None:
    # One rated home win by 10 on day 1. With a vanishing penalty the ridge solution is the
    # minimum-norm fit: beta = X'(XX')^-1 y with X = [+1, -1, hca] gives a home-court term of 10/3.
    # A non-neutral forecast for the same pairing is then 10, and a neutral one is 20/3.
    history = one_game("2020-01-01", neutral=False)
    later = pd.DataFrame(
        {
            "tipoff_utc": pd.to_datetime(
                ["2020-01-02T18:00:00Z", "2020-01-02T20:00:00Z"], utc=True
            ),
            "home": ["AAA", "AAA"],
            "away": ["BBB", "BBB"],
            "neutral": [False, True],
            "rated": [False, False],
            "margin": [np.nan, np.nan],
        }
    )
    games = pd.concat([history, later], ignore_index=True)
    params = RidgeParams(half_life_days=1e9, lam=1e-9, hca_penalty_scale=1.0)
    target = np.array([False, True, True])
    forecast = ridge_margin_forecast(games, params, target)
    assert forecast[1] == pytest.approx(10.0, abs=1e-6)
    assert forecast[2] == pytest.approx(20.0 / 3.0, abs=1e-6)
    assert np.isnan(forecast[0])


def test_forecast_ignores_its_own_day_and_later_results() -> None:
    games = as_rated(make_games({2019: True, 2020: True}))
    params = RidgeParams(half_life_days=200.0, lam=5.0)
    target = (games["season"] == 2020).to_numpy()
    base = ridge_margin_forecast(games, params, target)
    day = games["tipoff_utc"].dt.floor("D")
    cut = day[target].min() + pd.Timedelta(days=21)
    # Rewrite every result from the cut-off day on: forecasts before it must not move.
    altered = games.copy()
    later = (altered["tipoff_utc"] >= cut).to_numpy()
    altered.loc[later, "margin"] = -3.0 * altered.loc[later, "margin"] + 7.0
    moved = ridge_margin_forecast(altered, params, target)
    before = target & (games["tipoff_utc"] < cut).to_numpy()
    after = target & ~before
    assert np.array_equal(base[before], moved[before])
    assert not np.allclose(base[after], moved[after])
    # A game's own day: rewriting only that day's results leaves its forecasts unchanged.
    same_day = (day == day[target].min()).to_numpy()
    rewritten = games.copy()
    rewritten.loc[same_day, "margin"] = 99.0
    assert np.array_equal(
        base[target & same_day], ridge_margin_forecast(rewritten, params, target)[target & same_day]
    )


def test_forecast_rejects_unsorted_games() -> None:
    games = as_rated(make_games({2020: True})).iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="sorted by tipoff_utc"):
        ridge_margin_forecast(
            games, RidgeParams(half_life_days=100.0, lam=1.0), np.ones(len(games), bool)
        )


def test_run_blend_scores_every_rated_game_of_the_folds() -> None:
    games = make_games({2009: True, 2010: True, 2011: True, 2012: True})
    scored, report = run_blend(games, folds=(2011, 2012))
    expected = games[games["played"] & ~games["forfeit"] & games["season"].isin([2011, 2012])]
    assert report["all"]["games"] == len(expected) == len(scored.won)
    assert set(report["per_season"]) == {"2011", "2012"}
    assert report["all"]["pooled"]["blend"]["n"] == len(expected)
    for p in (scored.p_live, scored.p_blend, scored.p_roster, scored.p_b0):
        assert np.all((p > 0.0) & (p < 1.0))


def test_chosen_weight_ignores_later_seasons() -> None:
    games = make_games({2009: True, 2010: True, 2011: True, 2012: True}, seed=3)
    _, before = run_blend(games, folds=(2011,))
    altered = games.copy()
    later = (altered["season"] == 2012).to_numpy()
    altered.loc[later, "home_score"] = altered.loc[later, "away_score"] + 1
    _, after = run_blend(altered, folds=(2011,))
    assert before["chosen_by_season"] == after["chosen_by_season"]
    assert before["chosen_by_season"]["2011"]["weight"] in WEIGHT_GRID


def test_without_roster_inputs_the_roster_term_is_zero() -> None:
    games = make_games({2009: True, 2010: True, 2011: True}, seed=5)
    scored, _ = run_blend(games, folds=(2011,))
    assert np.array_equal(scored.mu_roster, scored.mu_blend)
    assert np.array_equal(scored.p_roster, scored.p_blend)
