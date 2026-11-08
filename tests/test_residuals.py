"""Residual diagnostics: the tests, the holm/reliability/binned helpers, and the no-lookahead
guarantee of the pre-game features (a later game's result changes no earlier game's features)."""

from datetime import timedelta

import numpy as np
import pandas as pd
from scipy.special import expit

from eurohoops.eval.residuals import (
    binned_residuals,
    elo_pregame,
    encompassing,
    holm,
    margin_residual_test,
    pregame_features,
    reliability,
)
from eurohoops.models.elo import EloParams


def _synthetic(n: int, planted: float, seed: int) -> tuple[np.ndarray, ...]:
    """Model probabilities, a raw feature with sd 2, and outcomes that follow the planted effect
    of the standardized feature on top of the model's log-odds."""
    rng = np.random.default_rng(seed)
    p = expit(rng.normal(0.4, 0.5, size=n))
    x = rng.normal(0.0, 2.0, size=n)
    z = (x - x.mean()) / x.std(ddof=1)
    eta = np.log(p) - np.log1p(-p) + planted * z
    y = (rng.uniform(size=n) < expit(eta)).astype(np.float64)
    return p, y, x


def test_encompassing_recovers_planted_coefficient() -> None:
    p, y, x = _synthetic(40_000, planted=0.3, seed=1)
    fit = encompassing(p, y, x)
    assert abs(fit.coef - 0.3) < 3 * fit.se
    assert fit.p < 0.01
    assert fit.n == 40_000


def test_encompassing_gives_zero_for_noise() -> None:
    p, y, _ = _synthetic(40_000, planted=0.0, seed=2)
    x = np.random.default_rng(3).normal(size=40_000)
    fit = encompassing(p, y, x)
    assert abs(fit.coef) < 3 * fit.se
    assert fit.p > 0.01


def test_margin_residual_test_recovers_slope() -> None:
    rng = np.random.default_rng(4)
    x = rng.normal(size=5_000)
    resid = 1.5 * x + rng.normal(scale=10.0, size=5_000)
    fit = margin_residual_test(resid, x)
    assert abs(fit.coef - 1.5) < 3 * fit.se
    assert fit.p < 1e-6


def test_holm_matches_hand_example() -> None:
    # sorted: 0.005*4=0.02, 0.01*3=0.03, 0.03*2=0.06, 0.04*1=0.04 -> running max 0.06
    adjusted = holm([0.01, 0.04, 0.03, 0.005])
    assert adjusted == [0.03, 0.06, 0.06, 0.02]


def test_holm_caps_at_one() -> None:
    assert holm([0.9, 0.8]) == [1.0, 1.0]


def test_reliability_bins() -> None:
    p = np.array([0.1, 0.3, 0.5, 0.9, 1.0])
    y = np.array([0.0, 1.0, 1.0, 1.0, 1.0])
    rows = reliability(p, y)
    assert [(r["lo"], r["hi"], r["n"]) for r in rows] == [
        (0.0, 0.2, 1),
        (0.2, 0.4, 1),
        (0.4, 0.6, 1),
        (0.8, 1.0, 2),
    ]
    top = rows[-1]
    assert top["predicted"] == 0.95
    assert top["observed"] == 1.0
    assert top["high"] == 1.0
    assert rows[0]["observed"] == 0.0


def test_binned_residuals_discrete_and_quantile() -> None:
    flag = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
    resid = np.array([-2.0, 0.0, 4.0, 6.0, 8.0])
    rows = binned_residuals(flag, resid, n_bins=10)
    assert [r["n"] for r in rows] == [2, 3]
    assert rows[0]["residual_mean"] == -1.0
    assert rows[1]["residual_mean"] == 6.0

    x = np.arange(100, dtype=np.float64)
    quant = binned_residuals(x, x, n_bins=10)
    assert len(quant) == 10
    assert sum(r["n"] for r in quant) == 100
    assert quant[0]["residual_mean"] < quant[-1]["residual_mean"]


def _games() -> pd.DataFrame:
    """Four teams, two seasons, two games per round, every game played and not neutral."""
    pairs = [
        [("AAA", "BBB"), ("CCC", "DDD")],
        [("AAA", "CCC"), ("BBB", "DDD")],
        [("AAA", "DDD"), ("BBB", "CCC")],
    ]
    base = pd.Timestamp("2020-10-01 18:00", tz="UTC")
    rows = []
    i = 0
    for season in (2020, 2021):
        for rnd, games in enumerate(pairs, start=1):
            for slot, (home, away) in enumerate(games):
                tip = base + timedelta(days=365 * (season - 2020) + 3 * rnd, hours=2 * slot)
                home_score = 70 + (7 * i) % 15
                away_score = 68 + (5 * i) % 17
                if home_score == away_score:
                    home_score += 1
                rows.append(
                    {
                        "game_id": f"E{season}_{i}",
                        "season": season,
                        "round": rnd,
                        "phase": "RS",
                        "tipoff_utc": tip,
                        "home": home,
                        "away": away,
                        "home_score": home_score,
                        "away_score": away_score,
                        "played": True,
                        "forfeit": False,
                        "neutral": False,
                    }
                )
                i += 1
    return pd.DataFrame(rows).sort_values(["tipoff_utc", "game_id"], ignore_index=True)


def test_pregame_features_and_elo_have_no_lookahead() -> None:
    games = _games()
    k = 9  # a game in the second season, so the prior-season feature is exercised too
    changed = games.copy()
    changed.loc[k, ["home_score", "away_score"]] = changed.loc[
        k, ["away_score", "home_score"]
    ].to_numpy()
    assert changed.loc[k, "home_score"] != games.loc[k, "home_score"]

    params = EloParams(k=20.0, hca=90.0, reversion=0.25)
    before_f = pregame_features(games)
    after_f = pregame_features(changed)
    before_e = elo_pregame(games, params)
    after_e = elo_pregame(changed, params)

    earlier = games["game_id"].iloc[: k + 1].tolist()
    pd.testing.assert_frame_equal(before_f.loc[earlier], after_f.loc[earlier])
    pd.testing.assert_frame_equal(before_e.loc[earlier], after_e.loc[earlier])
    # the test is not vacuous: a later game's Elo prediction does move
    later = games["game_id"].iloc[k + 1 :].tolist()
    assert not np.allclose(before_e.loc[later, "elo_p_home"], after_e.loc[later, "elo_p_home"])


def test_pregame_features_rest_counts_only_earlier_games() -> None:
    games = _games()
    feats = pregame_features(games)
    first = games.iloc[0]["game_id"]
    assert feats.loc[first, "home_rest"] == 7.0  # no earlier game: the cap
    assert feats.loc[first, "home_last7"] == 0
    assert feats["is_playoff"].eq(0.0).all()
    assert feats["round"].between(1, 3).all()
