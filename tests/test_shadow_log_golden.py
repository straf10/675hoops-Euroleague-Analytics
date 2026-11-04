"""Golden logs: each shadow model's log, byte for byte, on a fixed synthetic league and clock.

Written before the shadow-log refactor and kept after it: the refactor must not change a column,
a rounding or a version string (rule 1: the public logs are append-only). The goldens are the
current code's output; regenerate them only for a deliberate log-format change:
``UPDATE_GOLDEN=1 uv run pytest tests/test_shadow_log_golden.py``.
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from eurohoops.live_eloc import LiveEloc, predict_upcoming_eloc
from eurohoops.live_eloh import LiveEloh, predict_upcoming_eloh
from eurohoops.live_m1 import LiveM1, predict_upcoming_m1
from eurohoops.live_m5 import LiveM5, predict_upcoming_m5
from eurohoops.live_m5inj import predict_upcoming_m5inj
from eurohoops.models.elo import EloParams
from eurohoops.models.elo_cal import Calibration
from eurohoops.models.team_eff import DecayParams, MarginModel
from tests import eloc_synthetic as syn
from tests.conftest import make_games, make_team_games
from tests.m5_synthetic import fake_player_part
from tests.test_live_m1 import NOW as M1_NOW
from tests.test_live_m1 import ROUND_LEAD as M1_LEAD
from tests.test_live_m5 import CHOICE, NOW, ROUND_LEAD, SEASON, SPEC, live
from tests.test_m5inj import _injury_log, _synthetic_roster

GOLDEN = Path(__file__).parent / "fixtures" / "shadow_log"
ELO_SEASON = 2011
ELO_LAST_ROUND = 14
ELO_PARAMS = EloParams(k=20.0, hca=90.0, reversion=0.25)


def check_golden(name: str, log: Path) -> None:
    golden = GOLDEN / f"{name}.csv"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(log.read_bytes())
    assert log.read_bytes() == golden.read_bytes()


def elo_league() -> tuple[pd.DataFrame, datetime]:
    """The ELOC/ELOH synthetic league with its last round unplayed, and a clock 10 h before it."""
    games = syn.games()
    open_round = (games["season"] == ELO_SEASON) & (games["round"] == ELO_LAST_ROUND)
    games.loc[open_round, ["home_score", "away_score"]] = float("nan")
    games.loc[open_round, "played"] = False
    first = games.loc[open_round, "tipoff_utc"].min()
    return games, (first - pd.Timedelta(hours=10)).to_pydatetime().replace(tzinfo=UTC)


def test_m1_log(tmp_path: Path) -> None:
    games = make_games({s: True for s in range(2016, 2026)} | {2026: False})
    model = LiveM1(
        rating=DecayParams(half_life_days=120.0, carry=0.5, ridge=500.0),
        pace=DecayParams(half_life_days=120.0, carry=0.5, ridge=5.0),
        margin=MarginModel("student_t_const", 11.0, 7.0),
        totals_sigma=18.0,
        version="0.0.0+m1.golden",
        gate_passed=True,
    )
    log = tmp_path / "m1.csv"
    added = predict_upcoming_m1(
        games,
        make_team_games(games),
        model,
        log_path=log,
        season=2026,
        replay_from=2016,
        round_lead=M1_LEAD,
        clock=lambda: M1_NOW,
    )
    assert added == 3
    check_golden("m1", log)


def test_m5_log(tmp_path: Path) -> None:
    inputs = live()
    log = tmp_path / "m5.csv"
    added = predict_upcoming_m5(
        inputs.games,
        LiveM5(CHOICE, "0.0.0+m5.golden", gate_passed=True),
        lambda: (inputs, fake_player_part),
        log_path=log,
        season=SEASON,
        round_lead=ROUND_LEAD,
        clock=lambda: NOW,
        spec=SPEC,
    )
    assert added > 0
    check_golden("m5", log)


def test_m5inj_log(tmp_path: Path) -> None:
    inputs = live()
    log = tmp_path / "m5inj.csv"
    injuries = _injury_log([("2022-10-29T04:00:00Z", "GRE", "Alpha Tester", "Out")])
    added = predict_upcoming_m5inj(
        inputs.games,
        LiveM5(CHOICE, "0.0.0+m5.golden", gate_passed=True),
        lambda: (inputs, fake_player_part),
        injuries=injuries,
        roster=_synthetic_roster(),
        log_path=log,
        season=SEASON,
        round_lead=ROUND_LEAD,
        clock=lambda: NOW,
        spec=SPEC,
    )
    assert added > 0
    check_golden("m5inj", log)


def test_eloc_log(tmp_path: Path) -> None:
    games, now = elo_league()
    model = LiveEloc(
        Calibration(a=0.2, b=0.8, n=100, iterations=3),
        ELO_PARAMS,
        2007,
        "0.0.0+eloc.golden",
        True,
    )
    log = tmp_path / "eloc.csv"
    added = predict_upcoming_eloc(
        games,
        model,
        log_path=log,
        season=ELO_SEASON,
        round_lead=timedelta(hours=48),
        clock=lambda: now,
    )
    assert added == 4
    check_golden("eloc", log)


def test_eloh_log(tmp_path: Path) -> None:
    games, now = elo_league()
    model = LiveEloh(ELO_PARAMS, 25.0, {"A": 35.0}, 2007, "0.0.0+eloh.golden")
    log = tmp_path / "eloh.csv"
    added = predict_upcoming_eloh(
        games,
        model,
        log_path=log,
        season=ELO_SEASON,
        round_lead=timedelta(hours=48),
        clock=lambda: now,
    )
    assert added == 4
    check_golden("eloh", log)


def test_goldens_are_not_empty() -> None:
    for name in ("m1", "m5", "m5inj", "eloc", "eloh"):
        text = (GOLDEN / f"{name}.csv").read_text(encoding="utf-8")
        assert len(text.splitlines()) > 1, name
