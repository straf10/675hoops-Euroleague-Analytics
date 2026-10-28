"""The live-season commands of ``cli/live.py``: ``first-tipoff``, ``simulate`` and ``sim-ungated``.

The synthetic league of ``tests/m7_synthetic.py`` plays the live season (2021, after round 9). The
marts, the M1 report, the M7 gate and the log paths are replaced by tmp_path or by the synthetic
frames. The simulation itself is real, with 400 runs instead of the production LIVE_SIMS; the
tests check that the call carries the production spec and count before it is shrunk."""

import dataclasses
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import typer

from eurohoops.cli import live as live_mod
from eurohoops.config import EUROLEAGUE
from eurohoops.eval.m7_backtest import M7Inputs
from eurohoops.live_sim import SIM_LOG_COLUMNS, LiveSim, run_live_sim
from tests.m7_synthetic import build_inputs, small_spec, synthetic_formats
from tests.prediction_guard import real_prediction_logs_untouched  # noqa: F401

LIVE = 2021
DONE = 9  # rounds 1-9 complete; round 10 half played
SMALL_RUNS = 400
MODEL = LiveSim(key="sim_full", spread=1.0, net=False, version="m7-sim_full-v1", gate_passed=True)


@cache  # built once per run; every use below copies what it changes
def _synthetic() -> M7Inputs:
    return build_inputs()


def _live_games() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The synthetic league with 2021's rounds after DONE unplayed (round DONE + 1 half played)."""
    inputs = _synthetic()
    games = inputs.games.copy()
    games = games[~((games["season"] == LIVE) & (games["phase"] != "RS"))]
    live = (games["season"] == LIVE) & (games["round"] > DONE)
    half = live & (games["round"] == DONE + 1) & (games["game_code"] % 2 == 0)
    unplayed = live & ~half
    games.loc[unplayed, ["home_score", "away_score"]] = pd.NA
    games.loc[unplayed, "played"] = False
    team_games = inputs.team_games[
        inputs.team_games["game_id"].isin(games.loc[~unplayed, "game_id"])
    ]
    return games.reset_index(drop=True), team_games.reset_index(drop=True)


@pytest.fixture
def sim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    games, team_games = _live_games()
    tuned_m1 = _synthetic().tuned_m1
    m1_report = tmp_path / "m1.json"
    m1_report.write_text(json.dumps({"tuned": tuned_m1}), encoding="utf-8")
    state: dict[str, Any] = {"model": MODEL, "run_calls": []}
    real_run = run_live_sim

    def small_run(*args: Any, **kwargs: Any) -> Any:
        state["run_calls"].append(
            dict(kwargs)
        )  # the production spec and count, as the CLI passes them
        kwargs["spec"] = small_spec()
        kwargs["n_sims"] = SMALL_RUNS
        return real_run(*args, **kwargs)

    monkeypatch.setattr(live_mod, "LIVE_SEASON", LIVE)
    monkeypatch.setattr(
        live_mod, "season_format", lambda _c, _s: synthetic_formats("euroleague", LIVE)
    )
    monkeypatch.setattr(live_mod, "read_games", lambda _p, _c: games)
    monkeypatch.setattr(
        live_mod, "read_table", lambda _p, table, _c: team_games if table == "team_games" else None
    )
    monkeypatch.setattr(
        live_mod,
        "EUROLEAGUE",
        dataclasses.replace(EUROLEAGUE, m1=dataclasses.replace(EUROLEAGUE.m1, report=m1_report)),
    )
    monkeypatch.setattr(live_mod, "load_sim", lambda _m7, _v2=None: state["model"])
    monkeypatch.setattr(live_mod, "run_live_sim", small_run)
    monkeypatch.setattr(live_mod, "SIM_LOG", tmp_path / "sim_log.csv")
    monkeypatch.setattr(live_mod, "SIM_LATEST", tmp_path / "sim_latest.json")
    monkeypatch.setattr(live_mod, "SIM_UNGATED", tmp_path / "sim_ungated.json")
    state.update(games=games, tmp=tmp_path)
    yield state


def _first_open_day(games: pd.DataFrame) -> date:
    open_games = games[~games["played"].astype(bool) & games["confirmed_date"].astype(bool)]
    return pd.to_datetime(open_games["tipoff_utc"], utc=True).min().date()


def _rows(path: Path) -> list[dict[str, str]]:
    return pd.read_csv(path, dtype=str).to_dict("records")


# --- first-tipoff ----------------------------------------------------------------------------


def test_first_tipoff_prints_the_earliest_open_tip_of_the_day(
    sim: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    games = sim["games"]
    day = _first_open_day(games)
    open_games = games[~games["played"].astype(bool) & games["confirmed_date"].astype(bool)]
    tips = pd.to_datetime(open_games["tipoff_utc"], utc=True)
    expected = tips[tips.dt.date == day].min().strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(
        live_mod, "utc_now", lambda: datetime(day.year, day.month, day.day, tzinfo=UTC)
    )
    live_mod.first_tipoff(today=True)
    assert capsys.readouterr().out == f"{expected}\n"


def test_first_tipoff_prints_nothing_on_a_day_without_open_games(
    sim: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(live_mod, "utc_now", lambda: datetime(2000, 1, 1, tzinfo=UTC))
    live_mod.first_tipoff(today=True)
    assert capsys.readouterr().out == ""


def test_first_tipoff_needs_today(sim: dict[str, Any]) -> None:
    with pytest.raises(typer.Exit) as raised:
        live_mod.first_tipoff(today=False)
    assert raised.value.exit_code == 2


# --- simulate --------------------------------------------------------------------------------


def test_simulate_dry_run_prints_one_row_per_team_and_writes_nothing(
    sim: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    live_mod.simulate(dry_run=True)
    out = capsys.readouterr().out.splitlines()
    assert out[-2] == f"after round {DONE}, seed {small_spec().seed + DONE}, gate passed True"
    assert out[-1].startswith("RUNTIME simulate euroleague")
    assert len(out) - 2 == len(set(sim["games"]["home"]))  # one table line per team
    assert not (sim["tmp"] / "sim_log.csv").exists()
    assert not (sim["tmp"] / "sim_latest.json").exists()


def test_simulate_passes_the_production_spec_and_run_count(sim: dict[str, Any]) -> None:
    live_mod.simulate(dry_run=True)
    ((call),) = sim["run_calls"]
    assert call["spec"] is live_mod.M7
    assert call["n_sims"] == live_mod.LIVE_SIMS == 10_000
    assert call["season"] == LIVE


def test_simulate_logs_probabilities_that_are_valid_and_appends_once(
    sim: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    log = sim["tmp"] / "sim_log.csv"
    live_mod.simulate()
    assert "rows appended to" in capsys.readouterr().out
    rows = _rows(log)
    assert list(pd.read_csv(log, nrows=0).columns) == list(SIM_LOG_COLUMNS)
    assert len(rows) == len(set(sim["games"]["home"]))
    assert {r["after_round"] for r in rows} == {str(DONE)}
    assert {r["model"] for r in rows} == {"m7-sim_full"}
    for column in ("p_direct_playoffs", "p_play_in", "p_top10", "p_final_four", "p_title"):
        values = [float(r[column]) for r in rows]
        assert all(0.0 <= v <= 1.0 for v in values), column
    assert abs(sum(float(r["p_title"]) for r in rows) - 1.0) < 1e-3  # exactly one champion
    for r in rows:
        assert int(r["rank_p10"]) <= int(r["rank_p50"]) <= int(r["rank_p90"])
    assert (sim["tmp"] / "sim_latest.json").exists()

    before = log.read_bytes()
    live_mod.simulate()  # the same round is already logged: nothing appended
    assert log.read_bytes() == before


def test_simulate_logs_nothing_when_the_gate_failed(
    sim: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    sim["model"] = dataclasses.replace(MODEL, gate_passed=False)
    live_mod.simulate()
    out = capsys.readouterr().out
    assert "gate passed False" in out and "0 rows appended to" in out
    assert not (sim["tmp"] / "sim_log.csv").exists()


def test_simulate_without_a_gate_or_report_exits_1(sim: dict[str, Any]) -> None:
    sim["model"] = None
    with pytest.raises(typer.Exit) as raised:
        live_mod.simulate()
    assert raised.value.exit_code == 1


# --- sim-ungated -----------------------------------------------------------------------------


def test_sim_ungated_writes_the_gated_run_with_its_reason(sim: dict[str, Any]) -> None:
    live_mod.sim_ungated()
    report = _load_json(sim["tmp"] / "sim_ungated.json")
    assert report["season"] == LIVE and report["after_round"] == DONE
    assert report["gated"] is True
    assert report["gate"]["passed"] is True
    assert "passed its validation gate" in report["gate"]["reason"]
    assert not (sim["tmp"] / "sim_log.csv").exists()  # never appends to the simulation log


def test_sim_ungated_is_rewritten_only_when_the_round_or_gate_changes(
    sim: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    path = sim["tmp"] / "sim_ungated.json"
    live_mod.sim_ungated()
    first = path.read_bytes()
    capsys.readouterr()
    live_mod.sim_ungated()
    assert f"after round {DONE} already in {path}" in capsys.readouterr().out
    assert path.read_bytes() == first

    sim["model"] = dataclasses.replace(MODEL, gate_passed=False)
    live_mod.sim_ungated()
    report = _load_json(path)
    assert report["gated"] is False
    assert "failed its validation gate" in report["gate"]["reason"]
    assert "(not gated)" in capsys.readouterr().out


def _load_json(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def test_sim_ungated_without_a_gate_or_report_exits_1(sim: dict[str, Any]) -> None:
    sim["model"] = None
    with pytest.raises(typer.Exit) as raised:
        live_mod.sim_ungated()
    assert raised.value.exit_code == 1


@pytest.mark.parametrize("command", ["simulate", "sim_ungated"])
def test_without_team_games_the_run_exits_1(
    sim: dict[str, Any], monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr(live_mod, "read_table", lambda _p, _t, _c: None)
    with pytest.raises(typer.Exit) as raised:
        getattr(live_mod, command)()
    assert raised.value.exit_code == 1


@pytest.mark.parametrize("command", ["simulate", "sim_ungated"])
def test_a_finished_regular_season_has_nothing_to_simulate(
    sim: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    played = _synthetic().games.copy()  # every 2021 game is played: no round is left
    monkeypatch.setattr(live_mod, "read_games", lambda _p, _c: played)
    getattr(live_mod, command)()
    out = capsys.readouterr().out
    assert "the 2021 regular season is over" in out
    if command == "simulate":
        assert "nothing to simulate" in out
        assert not (sim["tmp"] / "sim_log.csv").exists()
    else:
        assert "sim_ungated.json stays" in out
        assert not (sim["tmp"] / "sim_ungated.json").exists()
