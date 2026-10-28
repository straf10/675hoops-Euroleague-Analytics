"""The shadow-log helpers of ``cli/live.py`` (M5-INJ, ELOC, ELOH, POOL, POOL3) called directly:
their gates (flags, missing inputs), what they pass on, what they print, and that a failing
shadow never blocks the run. ELOH and ELOC run their real forecast on the small synthetic league;
M5-INJ, POOL and POOL3 are checked as wiring, since their row logic has its own tests.

Every shadow log points at ``tmp_path``. The autouse guard below fails any test that changes a
file under the repo's ``predictions/`` (rule 1: logs are append-only)."""

import dataclasses
import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from eurohoops import live_eloc
from eurohoops.cli import live as live_mod
from eurohoops.cli._shared import Live
from eurohoops.config import ELOC_CV, EUROLEAGUE, Competition
from eurohoops.models.elo_cal import Calibration
from eurohoops.predict import LatePredictionError
from tests import eloc_synthetic as syn
from tests.conftest import REPO

SEASON = 2011
LAST_ROUND = 14
ELOH_FIT = Path(__file__).parent / "fixtures" / "eloh" / "fit_sample.json"
ELOC_REPORT = {
    "elo_params": {"k": 20.0, "hca": 90.0, "reversion": 0.25},
    "elo_warmup": [2007, 2014],
    "live_fit": {"a": 0.25, "b": 0.7, "games": 1200, "iterations": 4},
    "shadow_criteria": {"all": False},
}


def _predictions_state() -> dict[str, tuple[int, int]]:
    """Size and mtime of every file in the repo's predictions/ (stat only, nothing is read)."""
    state = {}
    for path in (REPO / "predictions").iterdir():
        if path.is_file():
            info = path.stat()
            state[path.name] = (info.st_size, info.st_mtime_ns)
    return state


@pytest.fixture(autouse=True)
def real_prediction_logs_untouched() -> Iterator[None]:
    """Fails the test if any file under the repo's predictions/ is added, removed or changed."""
    before = _predictions_state()
    yield
    assert _predictions_state() == before


@pytest.fixture
def comp(tmp_path: Path) -> Competition:
    """EuroLeague with every shadow log pointed at tmp_path."""
    return dataclasses.replace(
        EUROLEAGUE,
        eloh_prediction_log=tmp_path / "eloh.csv",
        eloc_prediction_log=tmp_path / "eloc.csv",
        m5inj_prediction_log=tmp_path / "m5inj.csv",
        pool_prediction_log=tmp_path / "pool.csv",
        pool3_prediction_log=tmp_path / "pool3.csv",
    )


class Recorder:
    """A stand-in for a shadow predictor: records its calls, returns ``result`` or raises."""

    def __init__(self, result: int = 0, error: Exception | None = None) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result
        self.error = error

    def __call__(self, *args: Any, **kwargs: Any) -> int:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


def _open_round_league() -> tuple[pd.DataFrame, datetime, list[str]]:
    """2011's last round is unplayed and confirmed. Returns the league, a clock 10 h before its
    first tip-off, and the ids of the open round's games."""
    games = syn.games()
    open_round = (games["season"] == SEASON) & (games["round"] == LAST_ROUND)
    games.loc[open_round, ["home_score", "away_score"]] = np.nan
    games.loc[open_round, "played"] = False
    first = games.loc[open_round, "tipoff_utc"].min()
    now = (first - pd.Timedelta(hours=10)).to_pydatetime().replace(tzinfo=UTC)
    return games, now, list(games.loc[open_round, "game_id"])


def _clock(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    monkeypatch.setattr(live_mod, "utc_now", lambda: now)


# --- ELOH: the real forecast on the synthetic league -----------------------------------------


def _eloh_live(games: pd.DataFrame, tuned: Any) -> Live:
    return Live(games=games, model=tuned, season=SEASON, replay_from=2007)


def test_eloh_off_by_flag_writes_nothing(
    comp: Competition, tuned: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    games, now, _ = _open_round_league()
    monkeypatch.setattr(live_mod, "ELOH_LIVE_ENABLED", False)
    _clock(monkeypatch, now)
    live_mod._predict_eloh(_eloh_live(games, tuned), comp, 48.0)
    assert not comp.eloh_prediction_log.exists()


def test_eloh_without_a_fit_file_warns_and_writes_nothing(
    comp: Competition, tuned: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    games, now, _ = _open_round_league()
    monkeypatch.setattr(live_mod, "ELOH_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "ELOH_FIT", comp.eloh_prediction_log.parent / "no_fit.json")
    _clock(monkeypatch, now)
    live_mod._predict_eloh(_eloh_live(games, tuned), comp, 48.0)
    assert "ELOH skipped" in caplog.text and "no_fit.json is missing" in caplog.text
    assert not comp.eloh_prediction_log.exists()


def test_eloh_logs_the_open_round_once_and_says_so(
    comp: Competition,
    tuned: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    games, now, open_ids = _open_round_league()
    monkeypatch.setattr(live_mod, "ELOH_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "ELOH_FIT", ELOH_FIT)
    _clock(monkeypatch, now)
    live = _eloh_live(games, tuned)

    live_mod._predict_eloh(live, comp, 48.0)
    rows = pd.read_csv(comp.eloh_prediction_log, dtype={"game_id": str})
    assert sorted(rows["game_id"]) == sorted(open_ids)
    assert set(rows["model"]) == {"eloh"}
    assert rows["p_home"].between(0.0, 1.0).all()
    assert f"{len(open_ids)} ELOH predictions appended to {comp.eloh_prediction_log}" in (
        capsys.readouterr().out
    )

    before = comp.eloh_prediction_log.read_bytes()
    live_mod._predict_eloh(live, comp, 48.0)  # same version, nothing due: no new rows
    assert comp.eloh_prediction_log.read_bytes() == before
    assert f"0 ELOH predictions appended to {comp.eloh_prediction_log}" in capsys.readouterr().out


def test_eloh_refuses_a_late_prediction(
    comp: Competition, tuned: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    games, now, _ = _open_round_league()
    monkeypatch.setattr(live_mod, "ELOH_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "ELOH_FIT", ELOH_FIT)
    _clock(monkeypatch, now)
    stub = Recorder(error=LatePredictionError("stamped after tip-off"))
    monkeypatch.setattr(live_mod, "predict_upcoming_eloh", stub)
    with pytest.raises(LatePredictionError):
        live_mod._predict_eloh(_eloh_live(games, tuned), comp, 48.0)


def test_a_failing_eloh_forecast_never_blocks_the_run(
    comp: Competition, tuned: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    games, now, _ = _open_round_league()
    monkeypatch.setattr(live_mod, "ELOH_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "ELOH_FIT", ELOH_FIT)
    _clock(monkeypatch, now)
    monkeypatch.setattr(live_mod, "predict_upcoming_eloh", Recorder(error=ValueError("boom")))
    live_mod._predict_eloh(_eloh_live(games, tuned), comp, 48.0)
    assert "ELOH skipped: its forecast failed" in caplog.text
    assert not comp.eloh_prediction_log.exists()


# --- ELOC: the real forecast from a frozen report written under tmp_path ---------------------


def test_eloc_is_off_by_default_and_never_reads_its_report(
    comp: Competition, monkeypatch: pytest.MonkeyPatch
) -> None:
    games, _, _ = _open_round_league()
    monkeypatch.setattr(live_eloc, "ELOC_LIVE_ENABLED", False)
    monkeypatch.setattr(live_mod, "load_eloc", Recorder(error=AssertionError("read")))
    live_mod._predict_eloc(games, SEASON, comp, 48.0)
    assert not comp.eloc_prediction_log.exists()


def _eloc_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, passed: bool) -> None:
    report = tmp_path / "eloc_cv.json"
    shadow = {**ELOC_REPORT, "shadow_criteria": {"all": passed}}
    report.write_text(json.dumps(shadow), encoding="utf-8")
    monkeypatch.setattr(live_mod, "ELOC_CV", dataclasses.replace(ELOC_CV, report=report))
    monkeypatch.setattr(live_eloc, "ELOC_LIVE_ENABLED", True)


def test_eloc_logs_the_open_round_when_its_cv_passed(
    comp: Competition,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    games, now, open_ids = _open_round_league()
    _eloc_report(tmp_path, monkeypatch, passed=True)
    _clock(monkeypatch, now)

    live_mod._predict_eloc(games, SEASON, comp, 48.0)
    rows = pd.read_csv(comp.eloc_prediction_log, dtype={"game_id": str})
    assert sorted(rows["game_id"]) == sorted(open_ids)
    assert set(rows["model"]) == {"eloc"}
    assert rows["p_home"].between(0.0, 1.0).all()
    assert f"{len(open_ids)} ELOC predictions appended" in capsys.readouterr().out


def test_eloc_logs_nothing_when_its_cv_did_not_pass(
    comp: Competition,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    games, now, _ = _open_round_league()
    caplog.set_level(logging.INFO, logger="eurohoops")
    _eloc_report(tmp_path, monkeypatch, passed=False)
    _clock(monkeypatch, now)
    live_mod._predict_eloc(games, SEASON, comp, 48.0)
    assert "ELOC did not pass its shadow criteria" in caplog.text
    assert not comp.eloc_prediction_log.exists()


def test_a_failing_eloc_forecast_never_blocks_the_run(
    comp: Competition, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    games, now, _ = _open_round_league()
    eloc = live_eloc.LiveEloc(
        Calibration(a=0.2, b=0.8, n=100, iterations=3),
        ELOC_CV.elo_params,
        2007,
        "0.0.0+eloc.test",
        True,
    )
    monkeypatch.setattr(live_eloc, "ELOC_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "load_eloc", lambda _path: eloc)
    monkeypatch.setattr(live_mod, "predict_upcoming_eloc", Recorder(error=ValueError("boom")))
    _clock(monkeypatch, now)
    live_mod._predict_eloc(games, SEASON, comp, 48.0)
    assert "ELOC skipped: its forecast failed" in caplog.text
    assert not comp.eloc_prediction_log.exists()


def test_eloc_refuses_a_late_prediction(comp: Competition, monkeypatch: pytest.MonkeyPatch) -> None:
    games, now, _ = _open_round_league()
    eloc = live_eloc.LiveEloc(
        Calibration(a=0.2, b=0.8, n=100, iterations=3),
        ELOC_CV.elo_params,
        2007,
        "0.0.0+eloc.test",
        True,
    )
    monkeypatch.setattr(live_eloc, "ELOC_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "load_eloc", lambda _path: eloc)
    monkeypatch.setattr(
        live_mod, "predict_upcoming_eloc", Recorder(error=LatePredictionError("late"))
    )
    _clock(monkeypatch, now)
    with pytest.raises(LatePredictionError):
        live_mod._predict_eloc(games, SEASON, comp, 48.0)


# --- M5-INJ, POOL, POOL3: wiring (the row logic has its own tests) ---------------------------


def test_m5inj_is_off_without_its_flag_or_m5(
    comp: Competition, monkeypatch: pytest.MonkeyPatch
) -> None:
    games, _, _ = _open_round_league()
    stub = Recorder()
    monkeypatch.setattr(live_mod, "predict_upcoming_m5inj", stub)
    frame = live_mod._LiveFrame(comp)
    monkeypatch.setattr(live_mod, "M5INJ_LIVE_ENABLED", False)
    live_mod._predict_m5inj(
        games, m5=object(), frame=frame, comp=comp, season=SEASON, round_lead_hours=48.0
    )
    monkeypatch.setattr(live_mod, "M5INJ_LIVE_ENABLED", True)
    live_mod._predict_m5inj(
        games, m5=None, frame=frame, comp=comp, season=SEASON, round_lead_hours=48.0
    )
    assert stub.calls == []
    assert not comp.m5inj_prediction_log.exists()


def test_m5inj_hands_its_log_season_and_lead_to_the_forecast(
    comp: Competition,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    games, _, _ = _open_round_league()
    m5 = object()
    stub = Recorder(result=3)
    monkeypatch.setattr(live_mod, "M5INJ_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "predict_upcoming_m5inj", stub)
    monkeypatch.setattr(live_mod, "read_injuries", lambda _path: pd.DataFrame())
    monkeypatch.setattr(live_mod, "read_roster_names", lambda _path: [])
    live_mod._predict_m5inj(
        games,
        m5=m5,
        frame=live_mod._LiveFrame(comp),
        comp=comp,
        season=SEASON,
        round_lead_hours=24.0,
    )
    ((args, kwargs),) = stub.calls
    assert args[0] is games and args[1] is m5
    assert kwargs["log_path"] == comp.m5inj_prediction_log
    assert kwargs["season"] == SEASON
    assert kwargs["round_lead"] == timedelta(hours=24)
    assert (
        f"3 M5-INJ predictions appended to {comp.m5inj_prediction_log}" in capsys.readouterr().out
    )


def test_m5inj_refuses_a_late_prediction_and_swallows_other_failures(
    comp: Competition, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    games, _, _ = _open_round_league()
    monkeypatch.setattr(live_mod, "M5INJ_LIVE_ENABLED", True)
    monkeypatch.setattr(live_mod, "read_injuries", lambda _path: pd.DataFrame())
    monkeypatch.setattr(live_mod, "read_roster_names", lambda _path: [])

    def call() -> None:
        live_mod._predict_m5inj(
            games,
            m5=object(),
            frame=live_mod._LiveFrame(comp),
            comp=comp,
            season=SEASON,
            round_lead_hours=48.0,
        )

    monkeypatch.setattr(
        live_mod, "predict_upcoming_m5inj", Recorder(error=LatePredictionError("late"))
    )
    with pytest.raises(LatePredictionError):
        call()
    monkeypatch.setattr(live_mod, "predict_upcoming_m5inj", Recorder(error=RuntimeError("bad")))
    call()
    assert "M5-INJ skipped: its forecast failed" in caplog.text


@pytest.mark.parametrize(
    ("helper", "name"),
    [(live_mod._predict_pool, "POOL"), (live_mod._predict_pool3, "POOL3")],
    ids=["pool", "pool3"],
)
def test_pool_helpers_write_to_their_log_and_echo_only_new_rows(
    helper: Callable[[Path | None], None],
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stub_name = "predict_pool" if name == "POOL" else "predict_pool3"
    stub = Recorder(result=2)
    monkeypatch.setattr(live_mod, stub_name, stub)
    log = tmp_path / "pool.csv"

    helper(None)  # no log configured: nothing is called
    assert stub.calls == []

    helper(log)
    assert stub.calls == [((), {"log_path": log})]
    assert f"2 {name} predictions appended to {log}" in capsys.readouterr().out

    stub.result = 0
    helper(log)  # nothing due: silent
    assert "predictions appended" not in capsys.readouterr().out


POOL_CASES = [
    (live_mod._predict_pool, "predict_pool", "POOL"),
    (live_mod._predict_pool3, "predict_pool3", "POOL3"),
]


@pytest.mark.parametrize("case", POOL_CASES, ids=["pool", "pool3"])
def test_a_failing_pool_forecast_never_blocks_the_run(
    case: tuple[Callable[[Path | None], None], str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    helper, stub_name, label = case
    monkeypatch.setattr(live_mod, stub_name, Recorder(error=OSError("component log gone")))
    helper(tmp_path / "pool.csv")
    assert f"{label} skipped: nothing appended to its log" in caplog.text
    assert not (tmp_path / "pool.csv").exists()
