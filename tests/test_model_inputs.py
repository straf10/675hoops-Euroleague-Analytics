"""``model_inputs``: the inputs the models read, and ``InputsMissing`` naming what is missing.

The marts are the synthetic EuroLeague built into a tmp DuckDB (``write_pipeline``); the
committed reports are written under tmp_path, the working directory."""

import json
from pathlib import Path

import pandas as pd
import pytest

from eurohoops.config import EUROLEAGUE, LIVE_SEASON, M3, M5, M6, M7, MART_PATH
from eurohoops.eval.m5_backtest import M5Inputs
from eurohoops.marts import read_games, write_tables
from eurohoops.model_inputs import (
    InputsMissing,
    m2_shots,
    m5_inputs,
    m5_player_ratings,
    m6_inputs,
    m7_inputs,
    sim_inputs,
)
from tests.conftest import make_games, make_team_games, write_pipeline

TUNED = {"tuned": {"k": 20.0}, "comparison_elo": {"k": 20.0}}


@pytest.fixture
def marts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The synthetic EuroLeague marts (no team games yet) with tmp_path as the working dir."""
    monkeypatch.chdir(tmp_path)
    write_pipeline(make_games({s: True for s in range(2007, 2026)} | {2026: False}))
    return tmp_path


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _m1_report() -> None:
    assert EUROLEAGUE.m1 is not None
    _write(EUROLEAGUE.m1.report, TUNED)


def _team_games() -> None:
    write_tables(MART_PATH, {"team_games": make_team_games(read_games(MART_PATH, "euroleague"))})


@pytest.mark.usefixtures("marts")
def test_m5_and_m7_need_the_m1_report_then_the_team_games() -> None:
    with pytest.raises(InputsMissing, match="no committed M1 report for euroleague"):
        m5_inputs(EUROLEAGUE, M5)
    with pytest.raises(InputsMissing, match="no committed M1 report for euroleague"):
        m7_inputs(EUROLEAGUE, M7, M7.tuning)
    _m1_report()
    with pytest.raises(InputsMissing, match="no team_games in the marts; run: eurohoops build"):
        m5_inputs(EUROLEAGUE, M5)
    with pytest.raises(InputsMissing, match="no team_games in the marts"):
        m7_inputs(EUROLEAGUE, M7, M7.tuning)


@pytest.mark.usefixtures("marts")
def test_the_live_simulation_reads_m7_m1_and_the_team_games_up_to_the_season() -> None:
    with pytest.raises(InputsMissing, match="no committed M7 or M1 report"):
        sim_inputs(EUROLEAGUE, LIVE_SEASON)
    _write(
        M7.report,
        {
            "model_version": "m7-sim_full-v1",
            "chosen": {"key": "sim_full", "spread": 1.0, "net": False},
            "gate": {"passed": False},
        },
    )
    with pytest.raises(InputsMissing, match="no committed M7 or M1 report"):
        sim_inputs(EUROLEAGUE, LIVE_SEASON)  # M7 without M1
    _m1_report()
    with pytest.raises(InputsMissing, match="no team_games in the marts"):
        sim_inputs(EUROLEAGUE, LIVE_SEASON)
    _team_games()
    sim = sim_inputs(EUROLEAGUE, 2020)
    assert sim.games["season"].max() == 2020
    assert sim.tuned_m1 == TUNED["tuned"]
    assert sim.model.key == "sim_full" and not sim.model.gate_passed
    assert len(sim.team_games) == len(make_team_games(read_games(MART_PATH, "euroleague")))


@pytest.mark.usefixtures("marts")
def test_a_wrong_m3_choice_is_a_missing_m5_input() -> None:
    _write(M3.report, {"chosen": {"variant": "box_only"}})
    empty = pd.DataFrame()
    inputs = M5Inputs(empty, empty, empty, tuned_m1={}, elo={})
    with pytest.raises(InputsMissing, match="M3 chosen variant must be rapm_spm"):
        m5_player_ratings(inputs, empty)


@pytest.mark.usefixtures("marts")
def test_m6_and_m2_name_their_missing_marts() -> None:
    with pytest.raises(InputsMissing, match="player_xwalk/stints missing"):
        m6_inputs(M6)
    with pytest.raises(InputsMissing, match="shots/shot_xpts missing"):
        m2_shots(2025)
