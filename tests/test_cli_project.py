"""``eurohoops project``: the live M6 checkpoint, its projections and the digest, on the synthetic
M6 world (no marts, no committed reports). The M6 report, the inputs loader and the live season are
pointed at tmp_path or at the synthetic world; nothing is read from the repository."""

import hashlib
import logging
import types
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eurohoops import cli
from eurohoops.cli import live as live_mod
from eurohoops.config import EUROLEAGUE, M6, M6_PROJECTIONS
from eurohoops.eval.m6_backtest import World, prepare
from eurohoops.live_m6 import live_people, live_projections, player_rows
from tests.m6_synthetic import M6Inputs, build_inputs, small_spec, synthetic_rounds

runner = CliRunner()
SPEC = small_spec()
LIVE = SPEC.test[-1]  # the synthetic world's last season plays the live one
CHOSEN = {"variant": "proj_shrunk", "half_life": 1.0}


@pytest.fixture(scope="module")
def inputs() -> M6Inputs:
    return build_inputs()


@pytest.fixture(scope="module")
def world(inputs: M6Inputs) -> World:
    return prepare(inputs)


@pytest.fixture
def live_season(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_mod, "LIVE_SEASON", LIVE)
    monkeypatch.setattr(
        live_mod,
        "season_format",
        lambda c, s: types.SimpleNamespace(regular_season_rounds=synthetic_rounds(c, s)),
    )


def _report(tmp_path: Path, *, passed: bool = True) -> Path:
    path = tmp_path / "m6.json"
    report = {
        "gate": {"passed": passed},
        "chosen": CHOSEN,
        "calibration": {"scale": {"0.25": {}, "0.5": {}, "0.75": {}}},
    }
    path.write_text(__import__("json").dumps(report), encoding="utf-8")
    return path


@pytest.fixture
def project_world(
    tmp_path: Path,
    inputs: M6Inputs,
    live_season: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """The CLI with the synthetic inputs and a passed M6 report under tmp_path (cwd too)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_mod, "_m6_inputs", lambda _spec, live=False: inputs)
    # the synthetic box lines carry no display names: each person is named by its id
    monkeypatch.setattr(
        live_mod, "_live_names", lambda data: {p: p for p in data.xwalk["person_id"]}
    )
    monkeypatch.setattr(live_mod, "M6", replace(M6, report=_report(tmp_path)))
    return tmp_path


def test_live_block_projects_the_checkpoint_with_its_own_scale(
    inputs: M6Inputs, world: World, live_season: None
) -> None:
    scale = {"pts": 2.0}
    report = {"calibration": {"scale": {"0.25": {}, "0.5": scale, "0.75": {}}}}
    checkpoint, rows, ti = live_mod._live_block(inputs, world, EUROLEAGUE, SPEC, report, CHOSEN)
    assert checkpoint == 0.5  # every live round is complete on the synthetic season
    people = list(live_people(world.complete, EUROLEAGUE.name, LIVE))
    expected, expected_ti = live_projections(
        inputs,
        EUROLEAGUE.name,
        LIVE,
        checkpoint,
        people,
        chosen=CHOSEN,
        scale=scale,
        spec=SPEC,
        rounds=synthetic_rounds(EUROLEAGUE.name, LIVE),
        world=world,
    )
    keys = ["person_id", "stat"]
    cols = ["person_id", "stat", "mean", "sd"]
    assert (
        rows.sort_values(keys)[cols]
        .reset_index(drop=True)
        .equals(expected.sort_values(keys)[cols].reset_index(drop=True))
    )
    assert ti.targets["person_id"].tolist() == expected_ti.targets["person_id"].tolist()


def test_project_dry_run_prints_the_digest_and_writes_nothing(
    project_world: Path, inputs: M6Inputs, world: World
) -> None:
    result = runner.invoke(cli.app, ["project", "--projections-only", "--dry-run"])
    assert result.exit_code == 0, result.output
    digest_line, count_line = result.output.strip().splitlines()[-3:-1]
    path, _, sha = digest_line.partition(": sha256 ")
    assert Path(path) == M6_PROJECTIONS and len(sha) == 64
    assert "dry run, nothing written" in count_line
    assert not (project_world / "reports").exists()
    # the player count is the number of players with live rows in the block
    _, rows, _ = live_mod._live_block(
        inputs,
        world,
        EUROLEAGUE,
        SPEC,
        {"calibration": {"scale": {"0.25": {}, "0.5": {}, "0.75": {}}}},
        CHOSEN,
    )
    live = world.complete[
        (world.complete["season"] == LIVE) & (world.complete["competition"] == EUROLEAGUE.name)
    ]
    names = {p: p for p in inputs.xwalk["person_id"]}
    players = player_rows(rows, live, names)
    assert f"{len(players)} projections" in count_line
    again = runner.invoke(cli.app, ["project", "--projections-only", "--dry-run"])
    # the digest is a function of the inputs only (the RUNTIME line carries the wall clock)
    digests = [line for line in result.output.splitlines() if "sha256" in line]
    assert [line for line in again.output.splitlines() if "sha256" in line] == digests


def test_project_writes_the_report_whose_digest_it_prints(project_world: Path) -> None:
    result = runner.invoke(cli.app, ["project", "--projections-only"])
    assert result.exit_code == 0, result.output
    written = (project_world / M6_PROJECTIONS).read_bytes()
    printed = next(line for line in result.output.splitlines() if "sha256" in line)
    assert printed.endswith(hashlib.sha256(written).hexdigest())
    assert written.endswith(b"}\n")  # logs.write_json's form
    assert '"player' in written.decode("utf-8")


def test_project_refuses_without_a_committed_m6_report(
    tmp_path: Path,
    live_season: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_mod, "M6", replace(M6, report=tmp_path / "missing.json"))
    caplog.set_level(logging.ERROR, logger="eurohoops")
    result = runner.invoke(cli.app, ["project", "--projections-only"])
    assert result.exit_code == 1
    assert "no committed M6 report" in caplog.text
    assert not (tmp_path / "reports").exists()


def test_project_leaves_the_committed_reports_when_the_m6_gate_failed(
    tmp_path: Path, live_season: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_mod, "M6", replace(M6, report=_report(tmp_path, passed=False)))
    result = runner.invoke(cli.app, ["project", "--projections-only"])
    assert result.exit_code == 0
    assert "M6 did not pass its validation gate: the committed reports stay (L-l)" in result.output
    assert not (tmp_path / "reports").exists()
