"""Live ELOC shadow log (``live_eloc.py``): off by default, the frozen report's fit, forecasts that
match the calibrated Elo replay, the pre-tip-off rounds, and append-only rows logged once."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops import live_eloc
from eurohoops.config import ELOC_CV, ELOC_LIVE_ENABLED, EUROLEAGUE
from eurohoops.live_eloc import (
    LiveEloc,
    eloc_forecasts,
    eloc_logging_on,
    load_eloc,
    predict_upcoming_eloc,
)
from eurohoops.models import elo
from eurohoops.models.elo_cal import Calibration, apply
from tests import eloc_synthetic as syn

SEASON = 2011
LAST_ROUND = 14
CAL = Calibration(a=0.2, b=0.8, n=100, iterations=3)


def _model(*, passed: bool = True) -> LiveEloc:
    return LiveEloc(CAL, ELOC_CV.elo_params, 2007, "0.0.0+eloc.test", passed)


def _league_with_open_round() -> tuple[pd.DataFrame, datetime]:
    """2011's last round is unplayed and confirmed. Returns the league and a clock 10 h before
    its first tip-off."""
    games = syn.games()
    open_round = (games["season"] == SEASON) & (games["round"] == LAST_ROUND)
    games.loc[open_round, ["home_score", "away_score"]] = np.nan
    games.loc[open_round, "played"] = False
    first = games.loc[open_round, "tipoff_utc"].min()
    return games, (first - pd.Timedelta(hours=10)).to_pydatetime()


def test_the_shadow_log_is_off_by_default() -> None:
    assert ELOC_LIVE_ENABLED is False
    assert eloc_logging_on(EUROLEAGUE) is False


def test_the_flag_needs_a_log_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_eloc, "ELOC_LIVE_ENABLED", True)
    assert eloc_logging_on(EUROLEAGUE) is True


def test_no_report_means_no_model(tmp_path: Path) -> None:
    assert load_eloc(tmp_path / "missing.json") is None


def test_load_eloc_reads_the_frozen_fit_and_the_criteria(tmp_path: Path) -> None:
    report = tmp_path / "eloc_cv.json"
    report.write_text(
        json.dumps(
            {
                "elo_params": {"k": 20.0, "hca": 90.0, "reversion": 0.25},
                "elo_warmup": [2007, 2014],
                "live_fit": {"a": 0.25, "b": 0.7, "games": 1200, "iterations": 4},
                "shadow_criteria": {"all": False},
            }
        ),
        encoding="utf-8",
    )
    model = load_eloc(report)
    assert model is not None
    assert (model.calibration.a, model.calibration.b) == (0.25, 0.7)
    assert model.first_season == 2007 and model.passed is False
    assert "+eloc." in model.version


def test_forecasts_are_the_calibrated_elo_replay() -> None:
    games, _ = _league_with_open_round()
    fc = eloc_forecasts(games, _model(), SEASON).set_index("game_id")
    part = games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    diff = elo.replay(elo.prepare(part), ELOC_CV.elo_params)
    live = (part["season"] == SEASON).to_numpy()
    expected = apply(CAL, diff[live])
    np.testing.assert_allclose(fc.loc[part.loc[live, "game_id"], "p_home"].to_numpy(), expected)


def test_a_forecast_never_sees_its_own_or_a_later_result() -> None:
    """The last game of the league (in tip-off order) has no later game: changing its result
    moves no forecast. The control: an earlier game's result does move later forecasts."""
    games = syn.games()
    ordered = games.sort_values("tipoff_utc", kind="stable")
    last_idx = ordered.index[-1]
    base = eloc_forecasts(games, _model(), SEASON)
    swapped = games.copy()
    swapped.loc[last_idx, ["home_score", "away_score"]] = games.loc[
        last_idx, ["away_score", "home_score"]
    ].to_numpy()
    np.testing.assert_array_equal(
        base["p_home"].to_numpy(), eloc_forecasts(swapped, _model(), SEASON)["p_home"].to_numpy()
    )
    early_idx = ordered.index[len(ordered) // 2]
    swapped = games.copy()
    swapped.loc[early_idx, ["home_score", "away_score"]] = games.loc[
        early_idx, ["away_score", "home_score"]
    ].to_numpy()
    moved = eloc_forecasts(swapped, _model(), SEASON)["p_home"].to_numpy()
    assert not np.array_equal(base["p_home"].to_numpy(), moved)


def test_a_failed_shadow_logs_nothing(tmp_path: Path) -> None:
    games, now = _league_with_open_round()
    log = tmp_path / "eloc.csv"
    added = predict_upcoming_eloc(
        games,
        _model(passed=False),
        log_path=log,
        season=SEASON,
        round_lead=timedelta(hours=48),
        clock=lambda: now.replace(tzinfo=UTC),
    )
    assert added == 0 and not log.exists()


def test_upcoming_games_are_logged_once(tmp_path: Path) -> None:
    games, now = _league_with_open_round()
    log = tmp_path / "eloc.csv"

    def clock() -> datetime:
        return now.replace(tzinfo=UTC)

    first = predict_upcoming_eloc(
        games, _model(), log_path=log, season=SEASON, round_lead=timedelta(hours=48), clock=clock
    )
    again = predict_upcoming_eloc(
        games, _model(), log_path=log, season=SEASON, round_lead=timedelta(hours=48), clock=clock
    )
    rows = pd.read_csv(log)
    assert first == 4 and again == 0
    assert len(rows) == 4 and set(rows["model"]) == {"eloc"}
    assert set(rows["model_version"]) == {"0.0.0+eloc.test"}
    assert (rows["p_home"].between(0.0, 1.0)).all()


def test_a_game_outside_the_round_lead_is_not_logged(tmp_path: Path) -> None:
    games, now = _league_with_open_round()
    log = tmp_path / "eloc.csv"
    added = predict_upcoming_eloc(
        games,
        _model(),
        log_path=log,
        season=SEASON,
        round_lead=timedelta(hours=1),  # the round tips off 10 h after this clock reads
        clock=lambda: now.replace(tzinfo=UTC),
    )
    assert added == 0 and not log.exists()


def test_forecast_margins_are_finite_once_earlier_seasons_exist() -> None:
    games, _ = _league_with_open_round()
    fc = eloc_forecasts(games, _model(), SEASON)
    assert np.isfinite(fc["exp_margin"]).all()
    assert len(fc) == syn.GAMES_PER_SEASON
    assert pd.Series(fc["game_id"]).str.startswith(f"S{SEASON}-").all()
