"""``gate_passed``: the one reading of a backtest report's gate verdict, and the readers that
use it (M1, M5 and the simulation load a model only on an explicit pass)."""

import json
from pathlib import Path
from typing import Any

import pytest

from eurohoops.eval.common import gate_passed
from eurohoops.live_m5 import load_m5
from eurohoops.live_sim import load_sim


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        ({"gate": {"passed": True}}, True),
        ({"gate": {"passed": False}}, False),
        ({"gate": {"passed": None}}, False),  # undecided is not a pass
        ({"gate": {"passed": 1}}, False),  # only a JSON true
        ({"gate": {"passed": "true"}}, False),
        ({"gate": {}}, False),
        ({"gate": "v2"}, False),  # a report whose gate is a label, not a verdict block
        ({"gate": None}, False),
        ({}, False),
    ],
)
def test_only_an_explicit_true_is_a_pass(report: dict[str, Any], expected: bool) -> None:
    assert gate_passed(report) is expected


def test_the_committed_reports_read_as_they_always_did() -> None:
    for name, expected in (("m1", True), ("m5", True), ("m2", False), ("m7", False)):
        report = json.loads(Path(f"reports/backtest_{name}.json").read_text(encoding="utf-8"))
        assert gate_passed(report) is expected, name


def test_a_model_without_a_gate_block_does_not_go_live(tmp_path: Path) -> None:
    report = Path("reports/backtest_m5.json")
    data = json.loads(report.read_text(encoding="utf-8"))
    del data["gate"]
    path = tmp_path / "no_gate.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_m5(path)
    assert loaded is not None and loaded.gate_passed is False


def test_the_simulation_reads_the_same_verdict(tmp_path: Path) -> None:
    data = json.loads(Path("reports/backtest_m7.json").read_text(encoding="utf-8"))
    path = tmp_path / "m7.json"
    for passed, expected in ((True, True), (False, False), (None, False)):
        data["gate"]["passed"] = passed
        path.write_text(json.dumps(data), encoding="utf-8")
        model = load_sim(path, None)
        assert model is not None and model.gate_passed is expected
