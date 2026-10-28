"""ELOH (experiments/eloh.md): the shrinkage of the home residuals by hand, the fit's residual
table, the frozen file, the forecast (live Elo with a team's home advantage), no lookahead, and the
shadow log written once per upcoming game. Fixtures under tests/fixtures/eloh; no data/ paths."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.config import ELOH_LIVE_ENABLED, EUROLEAGUE
from eurohoops.eval.backtest import TunedModel
from eurohoops.live_eloh import LiveEloh, eloh_forecasts, load_eloh, predict_upcoming_eloh
from eurohoops.models import elo
from eurohoops.models.elo import EloParams, prepare, replay, win_probability
from eurohoops.models.eloh import fit_from_stats, fit_home_effects, load_deltas
from tests import eloc_synthetic as syn

FIXTURES = Path(__file__).parent / "fixtures" / "eloh"
PARAMS = EloParams(k=20.0, hca=90.0, reversion=0.25)
SEASON = 2011
LAST_ROUND = 14


def _model(deltas: dict[str, float] | None = None) -> LiveEloh:
    return LiveEloh(PARAMS, 25.0, deltas or {}, 2007, "0.0.0+eloh.test")


def _stats(rows: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Team -> (ebar, s2) with n = 50 and pbar = 0.5 (the hand example's values)."""
    return pd.DataFrame(
        {
            "n": [50] * len(rows),
            "ebar": [e for e, _ in rows.values()],
            "pbar": [0.5] * len(rows),
            "s2": [s for _, s in rows.values()],
        },
        index=list(rows),
    )


def _sample_games() -> pd.DataFrame:
    games = pd.read_csv(FIXTURES / "games_sample.csv", parse_dates=["tipoff_utc"])
    return games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)


# ---- the fit: shrinkage by hand -------------------------------------------------------------


def test_shrinkage_by_hand() -> None:
    # ebar = 0.2 and 0.0, s2 = 0.01 each. Mean ebar 0.1, sample variance (ddof 1) = 0.01 + 0.01
    # = 0.02; mean s2 = 0.01; tau2 = 0.02 - 0.01 = 0.01; B = 0.01 / (0.01 + 0.01) = 0.5.
    # A's shrunk residual 0.5 * 0.2 = 0.1; delta = 0.1 / (ln10/400 * 0.5 * 0.5) = 69.48 points.
    fit = fit_from_stats(_stats({"A": (0.2, 0.01), "B": (0.0, 0.01)}), PARAMS)
    assert fit.tau2 == pytest.approx(0.01)
    assert fit.teams["A"].shrink == pytest.approx(0.5)
    assert fit.teams["A"].delta == pytest.approx(0.1 / (np.log(10.0) / 400.0 * 0.25))
    assert fit.teams["A"].delta == pytest.approx(69.48, abs=0.01)
    assert fit.teams["B"].delta == pytest.approx(0.0)


def test_no_between_team_variance_shrinks_every_delta_to_zero() -> None:
    # Equal residuals: var 0, so tau2 = max(0, 0 - mean s2) = 0 and every B is 0.
    fit = fit_from_stats(_stats({"A": (0.1, 0.01), "B": (0.1, 0.01), "C": (0.1, 0.01)}), PARAMS)
    assert fit.tau2 == 0.0
    assert all(effect.delta == 0.0 for effect in fit.teams.values())


def test_a_team_with_precise_residuals_keeps_more_of_its_effect() -> None:
    # Same ebar, different sampling variance: the team with the smaller s2 has the larger B.
    fit = fit_from_stats(_stats({"A": (0.3, 0.001), "B": (-0.3, 0.1), "C": (0.0, 0.05)}), PARAMS)
    assert fit.teams["A"].shrink > fit.teams["B"].shrink > 0.0
    assert abs(fit.teams["A"].delta) > abs(fit.teams["B"].delta)


def test_the_fit_needs_two_teams() -> None:
    with pytest.raises(ValueError, match="two teams"):
        fit_from_stats(_stats({"A": (0.1, 0.01)}), PARAMS)


def test_fit_home_effects_uses_only_rated_home_games() -> None:
    games = _sample_games()
    fit = fit_home_effects(games, PARAMS)
    # Rated home games: played, not forfeit (G10), not neutral (G09), not unplayed (G11).
    assert {team: effect.n for team, effect in fit.teams.items()} == {
        "A": 2,
        "B": 2,
        "C": 2,
        "D": 3,
    }
    # Residuals are home wins minus Elo's pre-game p, with p from the replay of every game.
    diffs = replay(prepare(games), PARAMS)
    p = {i: win_probability(float(d)) for i, d in enumerate(diffs)}
    expected_a = np.mean(
        [
            (1.0 if games.loc[i, "home_score"] > games.loc[i, "away_score"] else 0.0) - p[i]
            for i in (0, 4)
        ]
    )  # G01 and G05 are A's rated home games
    assert fit.teams["A"].mean_residual == pytest.approx(expected_a)
    assert fit.tau2 >= 0.0


def test_frozen_file_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "eloh_fit.json"
    path.write_text((FIXTURES / "fit_sample.json").read_text(encoding="utf-8"), encoding="utf-8")
    assert load_deltas(path) == {"AAA": 69.48, "BBB": -34.74}


# ---- the frozen file and the live model ------------------------------------------------------


def _tuned() -> TunedModel:
    return TunedModel(params=PARAMS, margin_scale=25.0, b0_home_win_rate=0.6, b0_home_margin=5.0)


def test_no_fit_file_means_no_model(tmp_path: Path) -> None:
    assert load_eloh(tmp_path / "missing.json", _tuned(), 2023) is None


def test_load_eloh_reads_the_frozen_deltas_and_names_its_fit() -> None:
    model = load_eloh(FIXTURES / "fit_sample.json", _tuned(), 2023)
    assert model is not None
    assert model.deltas == {"AAA": 69.48, "BBB": -34.74}
    assert model.params == PARAMS and model.margin_scale == 25.0 and model.first_season == 2023
    assert model.version.split("+", 1)[1].startswith("eloh.")


def test_the_shadow_log_is_live() -> None:
    # switched on at go-live (workflow.md step 5); logged from the merge onward
    assert ELOH_LIVE_ENABLED is True
    assert EUROLEAGUE.eloh_prediction_log == Path("predictions/euroleague_eloh_2026-27.csv")


# ---- the forecast ----------------------------------------------------------------------------


def test_with_no_team_shifts_the_forecast_is_live_elo() -> None:
    games = syn.games()
    fc = eloh_forecasts(games, _model(), SEASON)
    part = games[games["season"].between(2007, SEASON)]
    part = part.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    diff = elo.replay(prepare(part), PARAMS)
    live = (part["season"] == SEASON).to_numpy()
    expected = [f"{win_probability(float(d)):.4f}" for d in diff[live]]
    assert fc["p_home"].tolist() == expected


def test_a_home_team_shift_adds_to_that_teams_home_games() -> None:
    games = pd.DataFrame(
        {
            "game_id": ["g1", "g2"],
            "season": [2011, 2011],
            "tipoff_utc": pd.to_datetime(["2011-10-01T18:00Z", "2011-10-08T18:00Z"]),
            "home": ["AAA", "BBB"],
            "away": ["CCC", "DDD"],
            "home_score": [80.0, 70.0],
            "away_score": [70.0, 75.0],
            "played": [True, True],
            "forfeit": [False, False],
            "neutral": [False, False],
        }
    )
    fc = eloh_forecasts(games, _model({"AAA": 40.0}), 2011)
    # The first game of a fresh league: both at 1500, so p = win_probability(hca + delta).
    assert fc.loc[0, "p_home"] == f"{win_probability(130.0):.4f}"
    # The second game is BBB (no shift) at home: its ratings are still 1500, so p = hca 90 only.
    assert fc.loc[1, "p_home"] == f"{win_probability(90.0):.4f}"


def test_no_lookahead_a_later_result_changes_no_earlier_forecast() -> None:
    games = syn.games()
    model = _model({"A": 35.0, "B": -20.0})
    before = eloh_forecasts(games, model, SEASON)
    changed = games.copy()
    last = changed["tipoff_utc"].idxmax()
    changed.loc[last, ["home_score", "away_score"]] = [60.0, 110.0]  # an upset of the last game
    after = eloh_forecasts(changed, model, SEASON)
    pd.testing.assert_frame_equal(before, after)


def test_no_lookahead_an_added_later_game_changes_no_earlier_forecast() -> None:
    games = syn.games()
    model = _model({"A": 35.0})
    before = eloh_forecasts(games, model, SEASON)
    extra = games.iloc[[-1]].copy()
    extra["game_id"] = "LATER"
    extra["tipoff_utc"] = extra["tipoff_utc"] + pd.Timedelta(days=400)
    extra["season"] = SEASON
    extended = pd.concat([games, extra], ignore_index=True)
    after = eloh_forecasts(extended, model, SEASON)
    pd.testing.assert_frame_equal(before, after.iloc[: len(before)].reset_index(drop=True))


# ---- the shadow log --------------------------------------------------------------------------


def _league_with_open_round() -> tuple[pd.DataFrame, datetime]:
    games = syn.games()
    open_round = (games["season"] == SEASON) & (games["round"] == LAST_ROUND)
    games.loc[open_round, ["home_score", "away_score"]] = np.nan
    games.loc[open_round, "played"] = False
    first = games.loc[open_round, "tipoff_utc"].min()
    return games, (first - pd.Timedelta(hours=10)).to_pydatetime()


def test_predict_logs_each_upcoming_game_once(tmp_path: Path) -> None:
    games, now = _league_with_open_round()
    log = tmp_path / "euroleague_eloh_2011.csv"
    kwargs = {
        "log_path": log,
        "season": SEASON,
        "round_lead": timedelta(hours=48),
        "clock": lambda: now.replace(tzinfo=UTC),
    }
    assert predict_upcoming_eloh(games, _model({"A": 35.0}), **kwargs) == 4
    rows = pd.read_csv(log, dtype=str)
    assert set(rows["model"]) == {"eloh"}
    assert set(rows["model_version"]) == {"0.0.0+eloh.test"}
    assert len(rows) == 4
    # Logged once: a second run at the same version adds nothing.
    assert predict_upcoming_eloh(games, _model({"A": 35.0}), **kwargs) == 0
    assert len(pd.read_csv(log, dtype=str)) == 4


def test_the_logged_p_home_is_the_forecast(tmp_path: Path) -> None:
    games, now = _league_with_open_round()
    model = _model({"A": 35.0})
    log = tmp_path / "eloh.csv"
    predict_upcoming_eloh(
        games,
        model,
        log_path=log,
        season=SEASON,
        round_lead=timedelta(hours=48),
        clock=lambda: now.replace(tzinfo=UTC),
    )
    rows = pd.read_csv(log, dtype=str).set_index("game_id")
    fc = eloh_forecasts(games, model, SEASON).set_index("game_id")
    assert len(rows) == 4
    assert rows["p_home"].tolist() == fc.loc[rows.index, "p_home"].tolist()
