"""Home-court diagnostic for the frozen EuroLeague Elo (research only, read-only).

Three questions, all on the live Elo parameters except the one being varied:

1. Per season (2015-2026): games, actual home-win rate, mean Elo p_home, and the gap.
2. Calibration-in-the-large: for hca in a grid (k and reversion held live), log loss and Brier
   on 2024-25 pooled, on 2025 alone (the clean test season) and on 2026 so far.
3. Paired bootstrap (10,000 resamples, seed 20261015) of the 2025 log-loss gap between the best
   hca on 2025 and the live hca 90.

Ratings are replayed from the earliest season in the mart so they are warm. Every played game
(forfeits excluded) updates ratings; only non-neutral played games are scored.

Run: ``uv run python scripts/diag_home_court.py [--db PATH]``. Writes
``reports/diag_home_court.json`` and prints the tables. Opens the DuckDB file read-only and
writes nothing else.
"""

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import numpy.typing as npt
import pandas as pd

from eurohoops.models.elo import EloParams, prepare, replay, win_probability

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "data" / "marts" / "eurohoops.duckdb"
OUT_JSON = REPO / "reports" / "diag_home_court.json"

LIVE = EloParams(k=20.0, hca=90.0, reversion=0.25)
SEASONS = list(range(2015, 2027))
HCA_GRID = [50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0]
SEED = 20261015
N_BOOT = 10_000


def load_games(db: Path) -> pd.DataFrame:
    con = duckdb.connect(str(db), read_only=True)
    try:
        df = con.sql(
            """
            select season, game_id, tipoff_utc, home, away, home_score, away_score,
                   played, forfeit, neutral
            from games
            where competition = 'euroleague'
            order by tipoff_utc, game_id
            """
        ).df()
    finally:
        con.close()
    return df


def p_home_for(df: pd.DataFrame, hca: float) -> npt.NDArray[np.float64]:
    """Pre-game P(home win) for every row under EloParams(k=20, hca, reversion=0.25)."""
    params = EloParams(k=LIVE.k, hca=hca, reversion=LIVE.reversion)
    diffs = replay(prepare(df), params)
    return np.array([win_probability(d) for d in diffs], dtype=np.float64)


def log_loss(p: npt.NDArray[np.float64], y: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Per-game log loss."""
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def _bootstrap_2025(
    per_hca_losses: dict[float, npt.NDArray[np.float64]],
) -> dict[str, object]:
    """Section 3: paired bootstrap of the 2025 log-loss gap, best hca (on 2025) minus hca 90."""
    ll25 = {h: float(v.mean()) for h, v in per_hca_losses.items()}
    best_h = min(ll25, key=lambda h: (ll25[h], h))
    diff = per_hca_losses[best_h] - per_hca_losses[90.0]
    n = diff.shape[0]
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boot = diff[idx].mean(axis=1)
    ci_lo, ci_hi = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
    observed = float(diff.mean())
    boot_out: dict[str, object] = {
        "comparison": f"2025 log loss: hca {best_h:.0f} (best on 2025) minus hca 90 (live)",
        "best_hca_on_2025": best_h,
        "n_games_2025": int(n),
        "resamples": N_BOOT,
        "seed": SEED,
        "observed_mean_difference": observed,
        "ci95": [ci_lo, ci_hi],
        "ci_includes_zero": bool(ci_lo <= 0.0 <= ci_hi),
    }
    print("\nSection 3: paired bootstrap, 2025 games")
    print(f"best hca on 2025: {best_h:.0f}; n={n}")
    print(f"observed mean log-loss difference (best - 90): {observed:+.6f}")
    print(f"95% CI: [{ci_lo:+.6f}, {ci_hi:+.6f}]  includes 0: {boot_out['ci_includes_zero']}")
    return boot_out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    df = load_games(args.db)
    df["scored"] = (
        df["played"].astype(bool)
        & ~df["forfeit"].astype(bool)
        & ~df["neutral"].astype(bool)
        & df["season"].isin(SEASONS)
    )
    # Outcomes for played games only; unplayed rows have NaN scores and are never scored.
    df["home_won"] = (df["home_score"] > df["away_score"]).astype(float)
    y_all = df["home_won"].to_numpy()
    scored = df["scored"].to_numpy()

    # Section 1: live params, per season.
    p_live = p_home_for(df, LIVE.hca)
    seasons_out = []
    print("Section 1: per season, live Elo (k=20, hca=90, rev=0.25)")
    print(f"{'season':>6} {'games':>6} {'home_win':>9} {'mean_p':>8} {'gap':>8}")
    for s in SEASONS:
        m = scored & (df["season"].to_numpy() == s)
        n = int(m.sum())
        if n == 0:
            continue
        actual = float(y_all[m].mean())
        mean_p = float(p_live[m].mean())
        gap = mean_p - actual
        seasons_out.append(
            {
                "season": s,
                "games": n,
                "actual_home_win_rate": actual,
                "mean_p_home": mean_p,
                "gap_mean_p_minus_actual": gap,
            }
        )
        print(f"{s:>6} {n:>6} {actual:>9.4f} {mean_p:>8.4f} {gap:>+8.4f}")

    # Section 2: hca grid, calibration on 2024-25 pooled, 2025 and 2026.
    periods = {"2024_25_pooled": [2024, 2025], "2025": [2025], "2026_so_far": [2026]}
    season_arr = df["season"].to_numpy()
    grid_out = []
    per_hca_losses: dict[float, npt.NDArray[np.float64]] = {}
    print("\nSection 2: hca grid (k=20, rev=0.25 held)")
    print(
        f"{'hca':>5} {'period':>16} {'n':>5} {'logloss':>9} "
        f"{'brier':>9} {'mean_p':>8} {'home_win':>9}"
    )
    for h in HCA_GRID:
        p = p_home_for(df, h)
        row: dict[str, object] = {"hca": h, "periods": {}}
        for name, seasons in periods.items():
            m = scored & np.isin(season_arr, seasons)
            pm, ym = p[m], y_all[m]
            ll = float(log_loss(pm, ym).mean())
            br = float(((pm - ym) ** 2).mean())
            row["periods"][name] = {  # type: ignore[index]
                "games": int(m.sum()),
                "log_loss": ll,
                "brier": br,
                "mean_p_home": float(pm.mean()),
                "actual_home_win_rate": float(ym.mean()),
            }
            print(
                f"{h:>5.0f} {name:>16} {int(m.sum()):>5} {ll:>9.6f} {br:>9.6f} "
                f"{float(pm.mean()):>8.4f} {float(ym.mean()):>9.4f}"
            )
        grid_out.append(row)
        m25 = scored & (season_arr == 2025)
        per_hca_losses[h] = log_loss(p[m25], y_all[m25])

    boot_out = _bootstrap_2025(per_hca_losses)

    out = {
        "question": "Is the frozen EuroLeague home-court advantage (hca=90) shown to be wrong?",
        "db": str(args.db),
        "live_params": {"k": LIVE.k, "hca": LIVE.hca, "reversion": LIVE.reversion},
        "scoring_rule": "played, not forfeit, not neutral; ratings replayed over all played games "
        "from the earliest season in the mart",
        "per_season": seasons_out,
        "hca_grid": grid_out,
        "bootstrap_2025": boot_out,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
