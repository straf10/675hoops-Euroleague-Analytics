"""Live ELOR shadow log (EuroLeague only): the CV report's setting and criteria, the append-only
log, the walk-forward (nothing at or after the round's cutoff) and the plain-Elo fallback.

The league is ``tests/elor_synthetic.py``'s; its last season (2026) is the "live" season: from
round 3 on it is unplayed (no scores, no box lines), as a real season is before its rounds are
played.
"""

import csv
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.config import ELOR_ELO_PARAMS
from eurohoops.eval.elor_cv import ElorInputs
from eurohoops.live_elor import (
    ELOR_LOG_COLUMNS,
    LiveElor,
    elor_forecasts,
    load_elor,
    predict_upcoming_elor,
)
from eurohoops.models import elo
from eurohoops.models.elor import ElorSetting
from eurohoops.predict import LatePredictionError
from tests import elor_synthetic as syn

SEASON = 2026
FIRST_UNPLAYED_ROUND = 3
NOW = syn.round_start(SEASON, FIRST_UNPLAYED_ROUND).to_pydatetime() - timedelta(hours=10)
ROUND_LEAD = timedelta(hours=48)  # round 4 is more than 48 h later: out
SETTING = ElorSetting(0.5, 24)


def frozen_model(setting: ElorSetting = SETTING, *, passed: bool = True) -> LiveElor:
    return LiveElor(setting, ELOR_ELO_PARAMS, 2023, "0.0.0+elor.test", passed)


@cache
def full() -> ElorInputs:
    """The synthetic league with every game played: the oracle of the live season's future."""
    return syn.inputs()


@cache
def live() -> ElorInputs:
    """The league as of ``NOW``: round 3 onwards unplayed, with no scores and no box lines."""
    games, box = syn.games_and_box()
    games = games.astype({"home_score": "Int64", "away_score": "Int64"})
    future = ((games["season"] == SEASON) & (games["round"] >= FIRST_UNPLAYED_ROUND)).to_numpy()
    games.loc[future, "played"] = False
    games.loc[future, ["home_score", "away_score"]] = pd.NA
    games["confirmed_date"] = True
    box = box[~box["game_id"].isin(set(games.loc[future, "game_id"]))]
    return syn.inputs(games, box.reset_index(drop=True))


def run(
    model: LiveElor,
    log: Path,
    *,
    inputs: ElorInputs | None = None,
    calls: list[int] | None = None,
    at: datetime = NOW,
) -> int:
    chosen = live() if inputs is None else inputs

    def build() -> ElorInputs:
        if calls is not None:
            calls.append(1)
        return chosen

    return predict_upcoming_elor(
        chosen.games,
        model,
        build,
        log_path=log,
        season=SEASON,
        round_lead=ROUND_LEAD,
        clock=lambda: at,
    )


def rows(log: Path) -> list[dict[str, str]]:
    with log.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def report(tmp_path: Path, *, passed: bool = True, w0: float = 0.5) -> Path:
    path = tmp_path / "elor_cv.json"
    body = {
        "selected": {"w0": w0, "n_rounds": 24, "key": f"w{w0:g}|n24"},
        "elo_params": {"k": 20.0, "hca": 90.0, "reversion": 0.25},
        "elo_warmup": [2007, 2008],
        "first_round_rule": "strict",
        "git_head": "abc",
        "shadow_criteria": {"all": passed},
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_load_elor_reads_the_selected_setting_and_the_criteria(tmp_path: Path) -> None:
    assert load_elor(tmp_path / "none.json") is None
    model = load_elor(report(tmp_path))
    assert model is not None
    assert model.setting == SETTING
    assert model.elo_params == ELOR_ELO_PARAMS
    assert model.first_season == 2007
    assert model.passed
    assert "+elor." in model.version
    other = load_elor(report(tmp_path, w0=0.35))
    assert other is not None and other.version != model.version
    failed = load_elor(report(tmp_path, passed=False))
    assert failed is not None and not failed.passed


def test_a_failed_cv_logs_nothing_and_builds_nothing(tmp_path: Path) -> None:
    calls: list[int] = []
    assert run(frozen_model(passed=False), tmp_path / "elor.csv", calls=calls) == 0
    assert not calls
    assert not (tmp_path / "elor.csv").exists()


def test_logs_the_upcoming_round_once(tmp_path: Path) -> None:
    log = tmp_path / "elor.csv"
    calls: list[int] = []
    assert run(frozen_model(), log, calls=calls) == 2
    logged = rows(log)
    assert list(logged[0]) == list(ELOR_LOG_COLUMNS)
    assert {r["round"] for r in logged} == {str(FIRST_UNPLAYED_ROUND)}
    assert {r["model"] for r in logged} == {"elor"}
    assert {r["model_version"] for r in logged} == {"0.0.0+elor.test"}
    assert run(frozen_model(), log, calls=calls) == 0
    assert len(rows(log)) == 2
    assert calls == [1]  # the second run had nothing to log: no build


def test_weight_zero_is_the_elo_replay() -> None:
    fc = elor_forecasts(live(), frozen_model(ElorSetting(0.0, 24)), SEASON)
    games = live().games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    diff = elo.replay(elo.prepare(games), ELOR_ELO_PARAMS)
    expected = [elo.win_probability(float(d)) for d in diff[(games["season"] == SEASON).to_numpy()]]
    assert fc["p_home"].to_numpy() == pytest.approx(expected, abs=1e-12)


def test_the_roster_prior_moves_the_forecast() -> None:
    plain = elor_forecasts(live(), frozen_model(ElorSetting(0.0, 24)), SEASON)
    blended = elor_forecasts(live(), frozen_model(), SEASON)
    assert blended["prior_available"].all()
    assert not np.allclose(plain["p_home"], blended["p_home"])


def test_the_upcoming_round_never_sees_its_own_or_later_results() -> None:
    """Round 3 forecast with the whole season played (oracle) equals the live forecast."""
    upcoming = live().games
    ids = upcoming.loc[
        (upcoming["season"] == SEASON) & (upcoming["round"] == FIRST_UNPLAYED_ROUND), "game_id"
    ]
    now = elor_forecasts(live(), frozen_model(), SEASON).set_index("game_id").loc[ids]
    oracle = elor_forecasts(full(), frozen_model(), SEASON).set_index("game_id").loc[ids]
    assert now["p_home"].to_numpy() == pytest.approx(oracle["p_home"].to_numpy(), abs=1e-12)
    assert now["exp_margin"].to_numpy() == pytest.approx(oracle["exp_margin"].to_numpy())


def test_a_game_without_a_roster_prior_is_plain_elo(tmp_path: Path) -> None:
    inputs = replace(live(), possessions=pd.Series(dtype="float64"))
    fc = elor_forecasts(inputs, frozen_model(), SEASON)
    plain = elor_forecasts(inputs, frozen_model(ElorSetting(0.0, 24)), SEASON)
    assert not fc["prior_available"].any()
    assert fc["p_home"].to_numpy() == pytest.approx(plain["p_home"].to_numpy(), abs=1e-12)
    assert run(frozen_model(), tmp_path / "elor.csv", inputs=inputs) == 2


def test_a_mismatched_roster_club_stops_the_forecast() -> None:
    roster = live().roster.copy()
    roster.loc[(roster["season"] == SEASON) & (roster["club"] == "D"), "club"] = "Z"
    with pytest.raises(ValueError, match="club codes"):
        elor_forecasts(replace(live(), roster=roster), frozen_model(), SEASON)


def test_refuses_to_log_at_or_after_tip_off(tmp_path: Path) -> None:
    log = tmp_path / "elor.csv"
    tip = syn.round_start(SEASON, FIRST_UNPLAYED_ROUND).to_pydatetime()
    ticks = iter([NOW, tip])
    with pytest.raises(LatePredictionError):
        predict_upcoming_elor(
            live().games,
            frozen_model(),
            live,
            log_path=log,
            season=SEASON,
            round_lead=ROUND_LEAD,
            clock=lambda: next(ticks),
        )
    assert not log.exists()


def test_now_is_before_the_upcoming_round() -> None:
    assert NOW.tzinfo == UTC
    assert syn.round_start(SEASON, FIRST_UNPLAYED_ROUND).to_pydatetime() > NOW
