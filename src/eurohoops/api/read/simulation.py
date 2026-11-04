"""M7's verdict, the live season simulation and the live scorecard."""

from typing import Any

from eurohoops.api.read.store import NotFound, Store, _competition, _report
from eurohoops.config import (
    EUROLEAGUE,
    M7,
    M7_V2,
    SIM_UNGATED,
)

SPIEGELHALTER_LIMIT = (
    1.96  # the M7 gate's bound on the pooled |z| (config.M7, reports/m7_progress.md)
)


def m7_verdict(store: Store) -> dict[str, Any]:
    """M7's gate verdict from its backtest report: ``passed`` and, when it failed, the rules it
    missed in one line."""
    v2 = _report(store, M7_V2.report)
    if v2 is not None and v2.get("gate_v2", {}).get("passed"):
        return {
            "passed": True,
            "reason": f"M7 passed its validation gate (gate v2, {M7_V2.report.as_posix()})",
        }
    report = _report(store, M7.report)
    if report is None:
        return {"passed": False, "reason": f"{M7.report.as_posix()} not found: M7 has no verdict"}
    gate = report["gate"]
    if gate["passed"]:
        return {"passed": True, "reason": "M7 passed its validation gate"}
    missed = []
    if gate["brier_chosen"] >= gate["brier_point_sim"]:
        missed.append(
            f"validation Brier {gate['brier_chosen']:.4f} is not below the point rule's "
            f"{gate['brier_point_sim']:.4f}"
        )
    if gate["brier_chosen"] >= gate["brier_standings_now"]:
        missed.append(
            f"validation Brier {gate['brier_chosen']:.4f} is not below standings-now's "
            f"{gate['brier_standings_now']:.4f}"
        )
    if abs(gate["spiegelhalter_z_pooled"]) >= SPIEGELHALTER_LIMIT:
        missed.append(
            f"pooled Spiegelhalter |z| {abs(gate['spiegelhalter_z_pooled']):.2f} is not below "
            f"{SPIEGELHALTER_LIMIT}"
        )
    return {
        "passed": False,
        "reason": "M7 failed its validation gate: " + "; ".join(missed)
        if missed
        else "M7 did not pass its validation gate",
    }


def simulation_latest(store: Store, competition: str) -> dict[str, Any]:
    """The latest season simulation with M7's verdict; ``gated`` once a gate passed (gate v2,
    docs/models/m7.md)."""
    comp = _competition(competition)
    verdict = m7_verdict(store)
    report = _report(store, SIM_UNGATED)
    if report is None:
        raise NotFound(
            f"no ungated simulation report for {comp.name}: {verdict['reason']}",
            gated=False,
            gate=verdict,
        )
    return {**report, "gated": verdict["passed"], "gate": verdict}


def metrics_live(store: Store) -> dict[str, Any]:
    """The live scorecards (Elo, B0, and the M1 and M5 shadow blocks they carry) per competition."""
    cards = []
    for comp in (EUROLEAGUE,):
        card = _report(store, comp.scorecard)
        if card is not None:
            cards.append({"competition": comp.name, "scorecard": card})
    if not cards:
        raise NotFound("no live scorecard has been written")
    return {"competitions": cards}
