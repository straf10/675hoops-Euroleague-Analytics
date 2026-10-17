"""POOL evaluation (docs/models/pool.md): the read-only overlap audit.

The historical overlap audit reads only committed reports (no marts, no raw data) and states which
games are out of sample for every component. The protocol chose a live-only evaluation, so the
audit is the evidence for that choice. The live pool-minus-Elo block is the look report's
``reported_only.pool_vs_elo`` (``eval/promotion.py``), with the look's own CI.
"""

import json
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd

from eurohoops.config import ELOR_CV, M5
from eurohoops.models.pool import COMPONENTS

# Model variants in the committed game-level reports (the live or chosen setting of each model).
M5_VARIANT = "proj_hc|core|d180|r40"
M1_VARIANT = "student_t_const"

# Seasons each component was tuned, selected, gated or scored on (docs/models/pool.md, audit).
SEEN_SEASONS: dict[str, tuple[int, ...]] = {
    "elo": tuple(range(2015, 2026)),  # history run tuned 2015-2023, scored 2024-25; live 2024
    "m1": tuple(range(2015, 2026)),  # tuning 2015-2022, validation 2023, test 2024-25
    "m5": tuple(range(2015, 2026)),  # as M1, plus the retune selection over 2015-2023
    "elor": tuple(range(2015, 2024)),  # the CV that chose its live setting
}


def load_components(m5_games: Path, elor_games: Path, elor_key: str) -> pd.DataFrame:
    """One row per game with each component's P(home) (NaN where absent), its season and result.

    ``elor_key`` is the ELOR setting's key in its CV games file (``p_<key>``), the one the live
    log uses. Missing files give an empty frame: the audit reports zero games, it does not fail.
    """
    columns = ["game_id", "season", "home_won", *(f"p_{name}" for name in COMPONENTS)]
    if not m5_games.exists() or not elor_games.exists():
        return pd.DataFrame(columns=columns)
    games = pd.read_csv(m5_games, dtype={"game_id": str})
    picks = {
        "elo": games[games["model"] == "elo"].set_index("game_id")["p_home"],
        "m1": games[(games["model"] == "m1") & (games["variant"] == M1_VARIANT)].set_index(
            "game_id"
        )["p_home"],
        "m5": games[(games["model"] == "m5") & (games["variant"] == M5_VARIANT)].set_index(
            "game_id"
        )["p_home"],
    }
    base = games.drop_duplicates("game_id").set_index("game_id")
    wide = pd.DataFrame({"season": base["season"], "home_won": (base["actual_margin"] > 0)})
    for name, series in picks.items():
        wide[f"p_{name}"] = series.reindex(wide.index)
    cv = pd.read_csv(elor_games, dtype={"game_id": str}).set_index("game_id")
    wide["p_elor"] = cv[f"p_{elor_key}"].reindex(wide.index)
    return wide.reset_index()[columns]


def _present(frame: pd.DataFrame, names: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for name in names:
        mask &= frame[f"p_{name}"].notna()
    return mask


def overlap_report(frame: pd.DataFrame) -> dict[str, Any]:
    """Game counts per component pair, the common set, and the clean out-of-sample set.

    A game is clean when all four components have a prediction for it and no component was tuned,
    selected, gated or scored on its season. The clean set is what a historical evaluation would
    need; the protocol's audit finds it empty.
    """
    pairs: dict[str, Any] = {}
    for a, b in combinations(COMPONENTS, 2):
        mask = _present(frame, (a, b))
        seasons = frame.loc[mask, "season"].value_counts().sort_index()
        pairs[f"{a}+{b}"] = {
            "games": int(mask.sum()),
            "seasons": {str(int(s)): int(n) for s, n in seasons.items()},
        }
    common = _present(frame, COMPONENTS)
    seen = pd.Series(False, index=frame.index)
    for name in COMPONENTS:
        seen |= frame["season"].isin(SEEN_SEASONS[name])
    clean = common & ~seen
    return {
        "pairs": pairs,
        "all_four": {
            "games": int(common.sum()),
            "seasons": sorted({int(s) for s in frame.loc[common, "season"]}),
        },
        "clean_games": int(clean.sum()),
        "clean_seasons": sorted({int(s) for s in frame.loc[clean, "season"]}),
        "seen_seasons": {name: list(SEEN_SEASONS[name]) for name in COMPONENTS},
    }


def format_overlap(report: dict[str, Any]) -> str:
    """The overlap report as a console table."""
    lines = [f"{'pair':<14}{'games':>7}  seasons (games)"]
    for pair, info in report["pairs"].items():
        seasons = " ".join(f"{s}:{n}" for s, n in info["seasons"].items())
        lines.append(f"{pair:<14}{info['games']:>7}  {seasons}")
    all_four = report["all_four"]
    span = (
        "none" if not all_four["seasons"] else f"{all_four['seasons'][0]}-{all_four['seasons'][-1]}"
    )
    lines.append(f"{'all four':<14}{all_four['games']:>7}  {span}")
    lines.append(
        f"clean out-of-sample common games: {report['clean_games']}"
        + (f" (seasons {report['clean_seasons']})" if report["clean_games"] else " (none)")
    )
    return "\n".join(lines)


def elor_selected_key(report_path: Path = ELOR_CV.report) -> str:
    """The live ELOR setting's key (``w0.5|n24``) from the CV report."""
    return str(json.loads(report_path.read_text(encoding="utf-8"))["selected"]["key"])


def default_overlap() -> dict[str, Any]:
    """The overlap audit on the committed reports (read-only)."""
    frame = load_components(M5.games_report, ELOR_CV.games_report, elor_selected_key())
    return overlap_report(frame)
