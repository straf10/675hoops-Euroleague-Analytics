"""Early-season totals diagnostic (B2): the market total and M1's total against the actual total,
by EuroLeague round bucket. Read-only. Rule and declaration: docs/models/diag_early_totals.md.

Per game: ``line - actual`` and ``M1 total - actual``. Per bucket: the mean of each with a paired
percentile bootstrap CI (games resampled within the bucket, one seed, 95%).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval.scorecard import latest_per_model_game, not_provable

SEASON_PHASE = "RS"
BUCKETS = (("1-5", 1, 5), ("6-10", 6, 10), ("11+", 11, None))  # label, first round, last round
SEED = 20261022
N_BOOT = 10_000
CI_PERCENTILES = (2.5, 97.5)
_ROUND = 6


def bucket_of(rnd: int) -> str | None:
    """The bucket label of a regular-season round (``None`` below round 1)."""
    for label, first, last in BUCKETS:
        if rnd >= first and (last is None or rnd <= last):
            return label
    return None


def line_by_game(odds: pd.DataFrame, games: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Per game, the market total of the latest odds snapshot fetched strictly before tip-off.

    The snapshot must carry a total: a latest pre-tip snapshot without one leaves the game with
    no line (no fallback to an earlier snapshot). Snapshots fetched at or after tip-off are
    ignored. Returns the lines and the number of snapshots ignored for being post-tip-off.
    """
    tip = games[["game_id", "tipoff_utc"]].rename(columns={"tipoff_utc": "_tip"})
    merged = odds.astype({"game_id": str}).merge(tip, on="game_id")
    fetched = pd.to_datetime(merged["fetched_at_utc"], utc=True)
    tipoff = pd.to_datetime(merged["_tip"], utc=True)
    late = int((fetched >= tipoff).sum())
    before = merged[fetched < tipoff].assign(_fetched=fetched[fetched < tipoff])
    latest = before.sort_values("_fetched", kind="stable").drop_duplicates("game_id", keep="last")
    lines = latest[latest["total"].notna()][["game_id", "total"]]
    return lines.astype({"total": "float64"}), late


def m1_total_by_game(log: pd.DataFrame, manual_pushes: Sequence[datetime] = ()) -> pd.DataFrame:
    """Per game, the scored M1 total: the same row the forecast record scores.

    That is the latest row stamped before tip-off, of the earliest model version that logged the
    game, excluding rows that only became public at or after tip-off (``not_provable``).
    """
    log = log.astype({"game_id": str})
    valid = log[
        pd.to_datetime(log["predicted_at_utc"], utc=True)
        < pd.to_datetime(log["tipoff_utc"], utc=True)
    ]
    kept = valid[~not_provable(valid, manual_pushes)]
    latest = latest_per_model_game(kept)
    first = latest.sort_values("predicted_at_utc").drop_duplicates("game_id", keep="first")
    return first[["game_id", "exp_total"]].rename(columns={"exp_total": "m1_total"})


def _ci(values: np.ndarray, idx: np.ndarray) -> list[float]:
    means = values[idx].mean(axis=1)
    lo, hi = np.percentile(means, CI_PERCENTILES)
    return [round(float(lo), _ROUND), round(float(hi), _ROUND)]


def excludes_zero(ci: list[float] | None) -> bool:
    return ci is not None and (ci[0] > 0 or ci[1] < 0)


def _bucket_summary(line_gap: np.ndarray, m1_gap: np.ndarray) -> dict[str, Any]:
    """Means and paired bootstrap CIs (the same resamples for both metrics) of one bucket."""
    n = len(line_gap)
    if n == 0:
        return {"n": 0, "line": {"mean": None, "ci95": None}, "m1": {"mean": None, "ci95": None}}
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(N_BOOT, n))
    return {
        "n": n,
        "line": {
            "mean": round(float(line_gap.mean()), _ROUND),
            "ci95": _ci(line_gap, idx),
        },
        "m1": {"mean": round(float(m1_gap.mean()), _ROUND), "ci95": _ci(m1_gap, idx)},
    }


def build_report(
    games: pd.DataFrame,
    odds: pd.DataFrame,
    m1_log: pd.DataFrame,
    season: int,
    manual_pushes: Sequence[datetime] = (),
) -> dict[str, Any]:
    """The diagnostic for one EuroLeague season: coverage counts, the three buckets, the verdicts.

    ``games`` needs game_id, season, round, phase, tipoff_utc, played, forfeit, home_score,
    away_score. Only regular-season, played, non-forfeit games with a result are scored.
    """
    scope = games[
        (games["season"] == season)
        & (games["phase"] == SEASON_PHASE)
        & games["played"].astype(bool)
        & ~games["forfeit"].astype(bool)
    ].copy()
    scope["game_id"] = scope["game_id"].astype(str)
    scope["actual"] = (scope["home_score"] + scope["away_score"]).astype("float64")
    lines, late = line_by_game(odds[odds["season"] == season], scope)
    m1 = m1_total_by_game(m1_log, manual_pushes)
    joined = scope.merge(lines, on="game_id", how="left").merge(m1, on="game_id", how="left")
    joined["bucket"] = joined["round"].astype(int).map(bucket_of)
    joined = joined[joined["bucket"].notna()]
    buckets: dict[str, Any] = {}
    for label, _, _ in BUCKETS:
        part = joined[joined["bucket"] == label]
        has_line = part["total"].notna()
        has_m1 = part["m1_total"].notna()
        both = part[has_line & has_m1]
        summary = _bucket_summary(
            (both["total"] - both["actual"]).to_numpy(dtype="float64"),
            (both["m1_total"] - both["actual"]).to_numpy(dtype="float64"),
        )
        buckets[label] = {
            "games": len(part),
            "with_line": int(has_line.sum()),
            "with_m1": int(has_m1.sum()),
            **summary,
        }
    return {
        "season": season,
        "games": {
            "scored": len(joined),
            "no_line": int(joined["total"].isna().sum()),
            "no_m1": int(joined["m1_total"].isna().sum()),
            "odds_snapshots_after_tipoff_ignored": late,
        },
        "buckets": buckets,
        "verdict": {
            "line": _verdict(buckets, "line"),
            "m1": _verdict(buckets, "m1"),
        },
    }


def _verdict(buckets: dict[str, Any], metric: str) -> dict[str, Any]:
    """Owner decision 2026-10-23: the rounds 1-5 CI must lie entirely above 0 and the rounds 11+
    CI must not exclude 0. A rounds 1-5 CI entirely below 0 is descriptive only."""
    early = buckets["1-5"][metric]["ci95"] if buckets["1-5"]["n"] else None
    late = buckets["11+"][metric]["ci95"] if buckets["11+"]["n"] else None
    early_above = early is not None and early[0] > 0
    early_below = early is not None and early[1] < 0
    late_clear = late is not None and not excludes_zero(late)
    return {
        "early_bias_present": early_above and late_clear,
        "early_shift_opposite": early_below,
    }
