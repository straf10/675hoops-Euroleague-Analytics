"""E1: power of the R1 promotion looks, from the existing backtest outputs.

Writes reports/r1_power.json.

Reporting only. Nothing here feeds a promotion verdict. Inputs (read only): the per-game backtest
file ``reports/backtest_m5_games.csv`` (EuroLeague: M5, M1, Elo), plus the gate and
comparison blocks of ``reports/backtest_*.json`` for cross-checks. Game counts come from the
games mart (read only, 2026-10-22) and are written in ``LOOKS`` below with their derivation.

Run: ``uv run python scripts/r1_power.py``
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.eval.promotion import CI_LEVEL, MIN_GAP, RESAMPLES, SEED, bootstrap_ci
from eurohoops.eval.r1_power import (
    Z_UPPER,
    Look,
    bootstrap_indices,
    bootstrap_upper,
    normal_cumulative_prob,
    simulate_promotion,
)
from eurohoops.logs import write_json

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = REPORTS / "r1_power.json"

SIM_SEED = 20261022  # the simulation's own seed (the rule's bootstrap keeps SEED)
SIMS = 2000
TRUE_GAPS = (-0.003, -0.005, -0.01, -0.02)
REFERENCE_GAPS = (0.0,)  # no gap: how often the rule fires by chance

# The schedule counts (games mart, read 2026-10-22). Season 2026-27: EuroLeague 38 regular-season
# rounds of 10 games. Look 1 counts the flagship's logged rounds up to the
# look round (M5 from round 4, M1 from round 1). Look 2 counts the whole logged season: the
# regular season plus the playoffs. Playoff game counts are not scheduled yet: they take the
# 2025-26 counts (EuroLeague play-in 3 + playoffs 16 + Final Four 3 = 22).
EL_GAMES_PER_ROUND = 10
LOOKS = {
    "euroleague": (
        Look("round 19", 16 * EL_GAMES_PER_ROUND),  # rounds 4-19
        Look("season end", 35 * EL_GAMES_PER_ROUND + 22),  # rounds 4-38 + playoffs
    ),
}
PAIR = {"euroleague": ("m5", "elo")}  # the R1 statistic: flagship - Elo
FILES = {"euroleague": "backtest_m5_games.csv"}
GATE_JSON = {"euroleague": ("backtest_m5.json", "backtest_m1.json")}


def _variant(json_name: str) -> str:
    return str(json.loads((REPORTS / json_name).read_text(encoding="utf-8"))["gate"]["variant"])


def _per_game(competition: str) -> pd.DataFrame:
    """One row per game: split, home win, and the three models' home-win probabilities."""
    m5_json, m1_json = GATE_JSON[competition]
    df = pd.read_csv(REPORTS / FILES[competition])
    keep = (
        ((df["model"] == "m5") & (df["variant"] == _variant(m5_json)))
        | ((df["model"] == "m1") & (df["variant"] == _variant(m1_json)))
        | ((df["model"] == "elo") & (df["variant"] == "elo"))
    )
    probs = df[keep].pivot_table(index="game_id", columns="model", values="p_home", aggfunc="first")
    meta = df.groupby("game_id").agg(split=("split", "first"), margin=("actual_margin", "first"))
    out = probs.join(meta)
    out["home_won"] = (out["margin"] > 0).astype(np.float64)
    return out


def _losses(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    y = frame["home_won"].to_numpy(dtype=np.float64)
    return {
        m: per_game_log_loss(frame[m].to_numpy(dtype=np.float64), y) for m in ("m5", "m1", "elo")
    }


def _ci_sd(json_block: dict[str, Any], n: int) -> float:
    """SD implied by a published 95% CI (normal, z 1.96): half-width / 1.96 * sqrt(n)."""
    lo, hi = json_block["ci95"]
    return float((hi - lo) / 2.0 / 1.96 * np.sqrt(n))


def gap_sd_table(per_game: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Per-game gap SD for the three pairs on each split, with checks against the JSON outputs."""
    rows: list[dict[str, Any]] = []
    for competition, frame_all in per_game.items():
        for split in ("validation", "test"):
            frame = frame_all[frame_all["split"] == split]
            loss = _losses(frame)
            pairs = [("m5", "elo"), ("m1", "elo"), ("m5", "m1")]
            for a, b in pairs:
                diff = loss[a] - loss[b]
                rows.append(
                    {
                        "competition": competition,
                        "pair": f"{a}-{b}",
                        "split": split,
                        "n_games": len(diff),
                        "mean": round(float(diff.mean()), 6),
                        "sd": round(float(diff.std(ddof=1)), 6),
                        "source": f"per-game {FILES[competition]} ({split})",
                    }
                )
    return rows


def _checks(competition: str, per_game: pd.DataFrame) -> dict[str, Any]:
    """The per-game losses against the published means and the CI-implied SDs (cross-checks)."""
    m5_json, m1_json = GATE_JSON[competition]
    gate = json.loads((REPORTS / m5_json).read_text(encoding="utf-8"))["gate"]
    gate_m1 = json.loads((REPORTS / m1_json).read_text(encoding="utf-8"))
    validation = per_game[per_game["split"] == "validation"]
    test = per_game[per_game["split"] == "test"]
    loss_v = _losses(validation)
    loss_t = _losses(test)
    return {
        "validation_m5_log_loss": [round(float(loss_v["m5"].mean()), 6), gate["m5_log_loss"]],
        "validation_m1_log_loss": [
            round(float(loss_v["m1"].mean()), 6),
            gate_m1["gate"]["m1_log_loss"],
        ],
        "validation_m5_minus_m1_ci_sd": round(
            _ci_sd(gate["log_loss_m5_minus_m1"], len(validation)), 6
        ),
        "test_m1_minus_elo_ci_sd": round(
            _ci_sd(gate_m1["test_vs_elo"]["log_loss_m1_minus_elo"], len(test)), 6
        ),
        "test_m1_minus_elo_mean": round(float((loss_t["m1"] - loss_t["elo"]).mean()), 6),
    }


def bootstrap_check(diff: np.ndarray) -> dict[str, Any]:
    """The vectorised bootstrap (used by the simulation) against the rule's own ``bootstrap_ci``."""
    _, hi = bootstrap_ci(diff)
    fast = bootstrap_upper(diff, bootstrap_indices(len(diff)))
    return {"bootstrap_ci_upper": round(hi, 8), "vectorised_upper": round(fast, 8), "n": len(diff)}


def analytic(
    competition: str, sd: float, sd_source: str, looks: Sequence[Look] | None = None
) -> dict[str, Any]:
    looks = looks or LOOKS[competition]
    rows = []
    for gap in TRUE_GAPS + REFERENCE_GAPS:
        cumulative = normal_cumulative_prob(gap, sd, looks)
        first = np.diff(np.concatenate([[0.0], cumulative]))
        rows.append(
            {
                "true_gap": gap,
                "marginal": [round(float(x), 4) for x in first],
                "cumulative": [round(x, 4) for x in cumulative],
            }
        )
    return {"sd": round(sd, 6), "sd_source": sd_source, "rows": rows}


def simulated(competition: str, gaps: np.ndarray, sd_source: str) -> dict[str, Any]:
    looks = LOOKS[competition]
    rows = []
    for gap in TRUE_GAPS + REFERENCE_GAPS:
        result = simulate_promotion(gaps, gap, looks, sims=SIMS, seed=SIM_SEED)
        rows.append(
            {
                "true_gap": gap,
                "marginal": [round(x, 4) for x in result.marginal],
                "cumulative": [round(x, 4) for x in result.cumulative],
            }
        )
    return {
        "gaps_source": sd_source,
        "n_historical_gaps": len(gaps),
        "sims": SIMS,
        "sim_seed": SIM_SEED,
        "rows": rows,
    }


def main() -> None:
    per_game = {c: _per_game(c) for c in FILES}
    report: dict[str, Any] = {
        "rule": {
            "source": "docs/models/m5.md and m1.md (PLAN 8.1 R1); eval/promotion.py",
            "promote_if": "two-sided 97.5% paired-bootstrap CI upper bound < 0 and mean <= min_gap",
            "ci_level": CI_LEVEL,
            "z_upper": round(Z_UPPER, 4),
            "min_gap": MIN_GAP,
            "resamples": RESAMPLES,
            "seed": SEED,
        },
        "looks": {
            c: [{"name": look.name, "n_games": look.n_games} for look in LOOKS[c]] for c in LOOKS
        },
        "gap_sd": gap_sd_table(per_game),
        "checks": {c: _checks(c, per_game[c]) for c in FILES},
        "analytic": {},
        "sensitivity_analytic": {},
        "simulation": {},
        "bootstrap_check": {},
    }
    for competition in LOOKS:
        m_a, m_b = PAIR[competition]
        frame = per_game[competition]
        losses = {
            split: _losses(frame[frame["split"] == split]) for split in ("validation", "test")
        }
        diffs = {s: losses[s][m_a] - losses[s][m_b] for s in losses}
        test_diff = diffs["test"]
        report["analytic"][competition] = analytic(
            competition, float(test_diff.std(ddof=1)), f"test split, {len(test_diff)} games"
        )
        for label, diff in (
            ("validation", diffs["validation"]),
            ("pooled", np.concatenate([diffs["validation"], test_diff])),
        ):
            report["sensitivity_analytic"][f"{competition}_{label}"] = analytic(
                competition, float(diff.std(ddof=1)), f"{label}, {len(diff)} games"
            )
        report["simulation"][competition] = simulated(
            competition, test_diff, f"test split, {len(test_diff)} games"
        )
        report["bootstrap_check"][competition] = bootstrap_check(test_diff)
        report.setdefault("shape", {})[competition] = {
            "skew": round(float(stats.skew(test_diff)), 4),
            "excess_kurtosis": round(float(stats.kurtosis(test_diff)), 4),
            "source": f"test split, {len(test_diff)} games",
        }
    write_json(OUT, report)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
