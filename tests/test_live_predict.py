"""The ``predict`` command's handling of the M5 shadow log (missing inputs warn, a late
prediction stops the run, and nothing else is blocked), and the ``backfill-inputs`` command
(matches, already-present rows, rows that disagree with the Elo log). The Elo forecast is real
on the synthetic league; M5 is stubbed, since its forecast has its own tests. The backfill tests
write the Elo log through ``predict.predict_upcoming`` itself, without the snapshots.
Every log points at tmp_path; the guard in tests/prediction_guard.py checks the repo's logs."""

import csv
import dataclasses
import logging
from collections.abc import Iterator
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import typer

from eurohoops import config
from eurohoops.cli import live as live_mod
from eurohoops.cli._shared import Live
from eurohoops.config import EUROLEAGUE
from eurohoops.inputs import INPUT_COLUMNS
from eurohoops.predict import predict_upcoming
from eurohoops.shadow_log import LatePredictionError, run_shadows
from tests import eloc_synthetic as syn
from tests.prediction_guard import real_prediction_logs_untouched  # noqa: F401

SEASON = 2011
LAST_ROUND = 14
REPLAY_FROM = 2007


class Recorder:
    """A stand-in for a shadow forecast: records its calls, returns ``result`` or raises."""

    def __init__(self, result: int = 0, error: Exception | None = None) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result
        self.error = error

    def __call__(self, *args: Any, **kwargs: Any) -> int:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tuned: Any) -> Iterator[dict[str, Any]]:
    """The synthetic league with its last round open and EuroLeague's logs pointed at tmp_path.
    Yields what the tests need to drive ``backfill-inputs``."""
    games = syn.games()
    open_round = (games["season"] == SEASON) & (games["round"] == LAST_ROUND)
    games.loc[open_round, ["home_score", "away_score"]] = np.nan
    games.loc[open_round, "played"] = False
    open_ids = sorted(games.loc[open_round, "game_id"])
    first = games.loc[open_round, "tipoff_utc"].min()
    now = (first - pd.Timedelta(hours=10)).to_pydatetime().replace(tzinfo=UTC)

    comp = dataclasses.replace(
        EUROLEAGUE,
        m1=None,  # M1 is not under test: no report is read
        log_dir=tmp_path,
        inputs_log=tmp_path / "inputs.csv",
    )
    live = Live(games=games, model=tuned, season=SEASON, replay_from=REPLAY_FROM)
    monkeypatch.setattr(live_mod, "EUROLEAGUE", comp)
    monkeypatch.setattr(live_mod, "_live", lambda _comp: live)
    yield {
        "comp": comp,
        "games": games,
        "tuned": tuned,
        "open_ids": open_ids,
        "now": now,
        "monkeypatch": monkeypatch,
    }


@pytest.fixture
def predicting(world: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """``world`` with the clock fixed and the M5 forecast stubbed, to drive ``predict``."""
    monkeypatch.setattr(live_mod, "utc_now", lambda: world["now"])
    m5 = Recorder()
    monkeypatch.setattr(live_mod, "load_m5", lambda _path: object())
    monkeypatch.setattr(live_mod, "predict_upcoming_m5", m5)
    for flag in ("M5INJ_LIVE_ENABLED", "ELOC_LIVE_ENABLED", "ELOH_LIVE_ENABLED"):
        monkeypatch.setattr(config, flag, False)  # only M5 is under test
    return {**world, "m5": m5}


def _write_elo_log(world: dict[str, Any]) -> None:
    """The Elo log of the open round, written without the snapshots."""
    predict_upcoming(
        world["games"],
        world["tuned"],
        log_path=world["comp"].prediction_log,
        season=SEASON,
        replay_from=REPLAY_FROM,
        round_lead=timedelta(hours=48),
        clock=lambda: world["now"],
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_predict_echoes_each_shadow_and_passes_its_log_and_lead(
    predicting: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    comp = predicting["comp"]
    predicting["m5"].result = 4
    live_mod.predict()
    out = capsys.readouterr().out
    assert f"4 predictions appended to {comp.prediction_log}" in out
    assert f"4 M5 predictions appended to {comp.log_path('m5')}" in out
    ((args, kwargs),) = predicting["m5"].calls
    assert args[0] is predicting["games"] and kwargs["log_path"] == comp.log_path("m5")
    assert kwargs["season"] == SEASON and kwargs["round_lead"] == timedelta(hours=48)
    assert sorted(r["game_id"] for r in _rows(comp.prediction_log)) == predicting["open_ids"]


def _reads_its_inputs(*args: Any, **_kwargs: Any) -> int:
    """A shadow forecast that builds M5's live inputs (``args[2]``) as the real one does."""
    args[2]()
    return 0


def test_m5_missing_its_inputs_warns_and_the_run_goes_on(
    predicting: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="eurohoops")
    # the world's EuroLeague has no M1 report: M5's inputs are missing
    predicting["monkeypatch"].setattr(live_mod, "predict_upcoming_m5", _reads_its_inputs)
    live_mod.predict()  # returns normally: the Elo log and the other shadows are not blocked
    assert "no committed M1 report for euroleague" in caplog.text
    assert "M5 skipped: its marts" in caplog.text
    assert len(_rows(predicting["comp"].prediction_log)) == len(predicting["open_ids"])
    assert not predicting["comp"].log_path("m5").exists()


def test_m5_and_m5inj_missing_their_inputs_both_sit_the_run_out(
    predicting: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="eurohoops")
    mp = predicting["monkeypatch"]
    mp.setattr(config, "M5INJ_LIVE_ENABLED", True)
    mp.setattr(live_mod, "read_injuries", lambda _path: pd.DataFrame())
    mp.setattr(live_mod, "read_roster_names", lambda _path: {})
    mp.setattr(live_mod, "predict_upcoming_m5", _reads_its_inputs)
    mp.setattr(live_mod, "predict_upcoming_m5inj", _reads_its_inputs)
    live = live_mod._live(predicting["comp"])
    shadows = live_mod._shadows(live, predicting["comp"], 48.0)
    outcomes = {o.label: o for o in run_shadows(shadows, lambda _line: None)}
    assert outcomes["M5"].status == outcomes["M5-INJ"].status == "inactive"
    assert "M5-INJ skipped: its marts" in caplog.text
    assert not predicting["comp"].log_path("m5inj").exists()


def test_a_late_m5_prediction_refuses_the_run(
    predicting: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger="eurohoops")
    predicting["m5"].error = LatePredictionError("stamped at tip-off")
    with pytest.raises(typer.Exit) as raised:
        live_mod.predict()
    assert raised.value.exit_code == 1
    assert "refusing to log: stamped at tip-off" in caplog.text


def _backfill(world: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> str:
    live_mod.backfill_inputs()
    return capsys.readouterr().out


def test_backfill_without_an_inputs_log_does_nothing(
    world: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    world["monkeypatch"].setattr(
        live_mod, "EUROLEAGUE", dataclasses.replace(world["comp"], inputs_log=None)
    )
    assert _backfill(world, capsys) == ""


def test_backfill_with_no_elo_log_says_so(
    world: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    out = _backfill(world, capsys)
    assert f"no Elo log at {world['comp'].prediction_log}; nothing to backfill" in out
    assert not world["comp"].inputs_log.exists()


def test_backfill_replays_each_logged_elo_row_once(
    world: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    comp = world["comp"]
    _write_elo_log(world)
    assert not comp.inputs_log.exists()

    out = _backfill(world, capsys)
    assert f"{len(world['open_ids'])} matched and appended to {comp.inputs_log}" in out
    assert "0 already present, 0 skipped" in out
    snapshots = _rows(comp.inputs_log)
    assert sorted(r["game_id"] for r in snapshots) == world["open_ids"]
    assert {r["model_version"] for r in snapshots} == {world["tuned"].version()}
    assert list(snapshots[0]) == list(INPUT_COLUMNS)

    again = _backfill(world, capsys)
    assert "0 matched and appended" in again
    assert f"{len(world['open_ids'])} already present, 0 skipped" in again
    assert len(_rows(comp.inputs_log)) == len(world["open_ids"])


def test_backfill_skips_an_elo_row_whose_logged_p_home_disagrees(
    world: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    comp = world["comp"]
    _write_elo_log(world)
    rows = _rows(comp.prediction_log)
    tampered = rows[0]["game_id"]
    rows[0]["p_home"] = "0.123456"  # not what Elo replays to: the row must not get a snapshot
    with comp.prediction_log.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    out = _backfill(world, capsys)
    assert f"{len(world['open_ids']) - 1} matched and appended" in out
    assert "1 skipped" in out
    snapshotted = [r["game_id"] for r in _rows(comp.inputs_log)]
    assert tampered not in snapshotted
    assert sorted(snapshotted) == sorted(set(world["open_ids"]) - {tampered})
