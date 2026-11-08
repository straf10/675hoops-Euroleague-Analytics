"""Residual and reliability diagnostic for the EuroLeague forecasts (research only, read-only).

Question: do pre-game features that the models do not use explain their out-of-sample errors?

Models: Elo (live params k 20, hca 90, reversion 0.25, margin scale from ``reports/backtest_elo``)
and M5 (live variant ``proj_hc|core|d180|r40``, from ``reports/backtest_m5_games.csv``).

Scored games: 2015-2025, non-neutral, played, not forfeit. Ratings are replayed from the earliest
season in the mart so they are warm; every feature reads only games before the game it describes.

Tests per model and feature:
- encompassing: logit(p_model) offset plus the standardized feature, on home_won (pooled, and
  per season for the sign check). Holm across the model's features.
- margin: OLS of (actual margin - expected margin) on the standardized feature (reported only).
- flag "candidate evidence" when the Holm p < 0.05 and the pooled sign holds in at least 2/3 of
  the seasons that have the feature. Everything else: "no evidence".

Also: reliability by season and by home team (descriptive), binned residuals per feature, and the
live 2026 section (descriptive) from the published forecast logs.

Run: ``uv run python scripts/diag_residuals.py [--db PATH]``. Writes ``reports/diag_residuals.json``
and prints the tables. Opens the DuckDB file read-only and writes nothing else.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from eurohoops.api.read.forecasts import FORECAST_MODELS
from eurohoops.api.read.store import Store
from eurohoops.config import ELO_LIVE_PARAMS, EUROLEAGUE, LIVE_SEASON, SITE_FORECAST_MODEL
from eurohoops.eval.forecasts import _wilson, build_forecasts
from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.eval.residuals import (
    FEATURES,
    Fit,
    binned_residuals,
    elo_pregame,
    encompassing,
    holm,
    margin_residual_test,
    pregame_features,
    reliability,
)
from eurohoops.model_catalog import active_logs
from eurohoops.models.elo import FloatArray

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "data" / "marts" / "eurohoops.duckdb"
OUT_JSON = REPO / "reports" / "diag_residuals.json"
ELO_REPORT = REPO / "reports" / "backtest_elo.json"
M5_GAMES = REPO / "reports" / "backtest_m5_games.csv"
M5_VARIANT = "proj_hc|core|d180|r40"
SCORED_SEASONS = list(range(2015, 2026))
MIN_HOME_GAMES = 40
N_BINS = 10
HOLM_ALPHA = 0.05
SIGN_SHARE = 2 / 3
FLAG = "candidate evidence"
NO_FLAG = "no evidence"
M5_EXTRA = ("elo_diff",)
DESCRIPTIONS = {
    "home_rest": "home team's days since its previous game (cap 7)",
    "away_rest": "away team's days since its previous game (cap 7)",
    "rest_diff": "home rest minus away rest (days)",
    "home_short": "home team rested at most 2.5 days (0/1)",
    "away_short": "away team rested at most 2.5 days (0/1)",
    "home_last7": "home team games in the previous 7 days",
    "away_last7": "away team games in the previous 7 days",
    "round": "round number within the season",
    "is_playoff": "1 when the game is not regular season",
    "month_of_season": "calendar months since October (0 to 8)",
    "confidence": "|model P(home win) minus 0.5|",
    "prior_home_edge": "home team's previous-season home-win rate minus league rate",
    "elo_diff": "pre-game Elo rating difference, home-court advantage included (M5 only)",
}


def load_games(db: Path) -> pd.DataFrame:
    con = duckdb.connect(str(db), read_only=True)
    try:
        df = con.sql(
            """
            select game_id, season, round, phase, tipoff_utc, home, away, home_score, away_score,
                   played, forfeit, neutral
            from games
            where competition = 'euroleague'
            order by tipoff_utc, game_id
            """
        ).df()
    finally:
        con.close()
    return df


def _r(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _fit_dict(fit: Fit) -> dict[str, Any]:
    return {"coef": _r(fit.coef), "se": _r(fit.se), "z": _r(fit.z), "p": _r(fit.p), "n": fit.n}


def load_m5(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """The live-variant M5 rows, indexed by game_id, and split counts over all rows read."""
    raw = pd.read_csv(path)
    rows = raw[(raw["model"] == "m5") & (raw["variant"] == M5_VARIANT)]
    counts = {str(k): int(v) for k, v in rows["split"].value_counts().sort_index().items()}
    return rows.set_index("game_id"), {"variant": M5_VARIANT, "rows_by_split": counts}


def scored_games(games: pd.DataFrame, feats: pd.DataFrame, elo: pd.DataFrame) -> pd.DataFrame:
    mask = (
        games["played"].astype(bool)
        & ~games["forfeit"].astype(bool)
        & ~games["neutral"].astype(bool)
        & games["season"].isin(SCORED_SEASONS)
    )
    s = games[mask].set_index("game_id").drop(columns="round")  # round comes from feats
    s = s.join(feats).join(elo)
    s["home_won"] = (s["home_score"] > s["away_score"]).astype(np.float64)
    s["margin"] = (s["home_score"] - s["away_score"]).astype(np.float64)
    return s


def model_frame(
    scored: pd.DataFrame, model: str, margin_scale: float, m5: pd.DataFrame | None
) -> pd.DataFrame:
    """One row per scored game with the model's P(home win), expected margin and features."""
    if model == "elo":
        df = scored.assign(p=scored["elo_p_home"], exp_margin=scored["elo_diff"] / margin_scale)
    else:
        assert m5 is not None
        df = scored.join(m5[["p_home", "exp_margin"]], how="inner").rename(columns={"p_home": "p"})
    df = df.assign(confidence=(df["p"] - 0.5).abs())
    return df


def _features_for(model: str) -> list[str]:
    return list(FEATURES) + ([] if model == "elo" else list(M5_EXTRA))


def feature_tests(df: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    """Pooled and per-season tests of every feature for one model, with Holm and the pass bar."""
    y = df["home_won"].to_numpy(dtype=np.float64)
    p = df["p"].to_numpy(dtype=np.float64)
    resid = (df["margin"] - df["exp_margin"]).to_numpy(dtype=np.float64)
    seasons = df["season"].to_numpy()
    pooled: dict[str, dict[str, Any]] = {}
    for f in features:
        x = df[f].to_numpy(dtype=np.float64)
        ok = ~np.isnan(x)
        win = encompassing(p[ok], y[ok], x[ok])
        margin_ok = ok & ~np.isnan(resid)
        margin = margin_residual_test(resid[margin_ok], x[margin_ok])
        per_season = []
        for s in sorted(set(seasons[ok].tolist())):
            m = ok & (seasons == s)
            if np.unique(x[m]).size < 2:  # a feature constant within the season has no sign
                continue
            fit = encompassing(p[m], y[m], x[m])
            per_season.append({"season": int(s), "coef": _r(fit.coef), "p": _r(fit.p), "n": fit.n})
        pooled[f] = {"win": win, "margin": margin, "per_season": per_season}
    names = list(pooled)
    holm_win = holm([pooled[f]["win"].p for f in names])
    holm_margin = holm([pooled[f]["margin"].p for f in names])
    out: dict[str, Any] = {}
    for f, hw, hm in zip(names, holm_win, holm_margin, strict=True):
        block = pooled[f]
        coef = block["win"].coef
        seasons_with = block["per_season"]
        agree = sum(1 for row in seasons_with if np.sign(row["coef"]) == np.sign(coef))
        sign_ok = agree * 3 >= 2 * len(seasons_with)
        flag = FLAG if hw < HOLM_ALPHA and sign_ok else NO_FLAG
        out[f] = {
            "description": DESCRIPTIONS[f],
            "win": {**_fit_dict(block["win"]), "p_holm": _r(hw)},
            "margin": {**_fit_dict(block["margin"]), "p_holm": _r(hm)},
            "per_season": seasons_with,
            "seasons_with_feature": len(seasons_with),
            "seasons_same_sign": agree,
            "flag": flag,
        }
    return out


def reliability_tables(df: pd.DataFrame) -> dict[str, Any]:
    y = df["home_won"].to_numpy(dtype=np.float64)
    p = df["p"].to_numpy(dtype=np.float64)
    by_season = []
    for s, sub in df.groupby("season"):
        ps = sub["p"].to_numpy(dtype=np.float64)
        ys = sub["home_won"].to_numpy(dtype=np.float64)
        by_season.append(_summary(int(s), ps, ys, reliability(ps, ys)))
    by_team = []
    for team, sub in df.groupby("home"):
        if len(sub) < MIN_HOME_GAMES:
            continue
        ps = sub["p"].to_numpy(dtype=np.float64)
        ys = sub["home_won"].to_numpy(dtype=np.float64)
        low, high = _wilson(int(ys.sum()), len(ys))
        row = _summary(str(team), ps, ys, [])
        row.update({"observed_low": low, "observed_high": high})
        by_team.append(row)
    pooled = _summary("pooled", p, y, reliability(p, y))
    return {"pooled": pooled, "by_season": by_season, "by_home_team": by_team}


def _summary(key: int | str, p: FloatArray, y: FloatArray, bins: list[dict[str, Any]]) -> dict:
    n = len(y)
    mean_p = float(p.mean())
    actual = float(y.mean())
    return {
        "key": key,
        "n": n,
        "mean_p_home": _r(mean_p),
        "actual_home_win": _r(actual),
        "gap_p_minus_actual": _r(mean_p - actual),
        "log_loss": _r(float(per_game_log_loss(p, y).mean())),
        "bins": bins,
    }


def binned_block(df: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    y = df["home_won"].to_numpy(dtype=np.float64)
    p = df["p"].to_numpy(dtype=np.float64)
    resid_margin = (df["margin"] - df["exp_margin"]).to_numpy(dtype=np.float64)
    out: dict[str, Any] = {}
    for f in features:
        x = df[f].to_numpy(dtype=np.float64)
        ok = ~np.isnan(x)
        m_ok = ok & ~np.isnan(resid_margin)
        out[f] = {
            "win": _binned(binned_residuals(x[ok], y[ok] - p[ok], N_BINS)),
            "margin": _binned(binned_residuals(x[m_ok], resid_margin[m_ok], N_BINS)),
        }
    return out


def _binned(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: _r(v) if isinstance(v, float) else v for k, v in row.items()} for row in rows]


def live_section(store: Store, feats: pd.DataFrame) -> dict[str, Any]:
    """Descriptive: 2026 published forecasts per model, through ``build_forecasts``."""
    comp = EUROLEAGUE
    games = store.games(comp)
    logs = {tag: store.path(p) for tag, p in active_logs(comp, shown=True).items()}
    odds = store.path(comp.odds_log) if comp.odds_log is not None else None
    forecasts = build_forecasts(
        logs,
        FORECAST_MODELS,
        games,
        LIVE_SEASON,
        comp.manual_pushes,
        odds_log=odds,
        published=SITE_FORECAST_MODEL,
    )
    rows: list[dict[str, Any]] = []
    for g in forecasts["games"]:
        for model, v in g["models"].items():
            rows.append(
                {
                    "model": model,
                    "game_id": g["game_id"],
                    "p": v["p_home"],
                    "exp_margin": v["exp_margin"],
                    "home_won": float(g["home_score"] > g["away_score"]),
                    "margin": float(g["home_score"] - g["away_score"]),
                }
            )
    frame = pd.DataFrame(rows)
    rest = feats.loc[feats.index.isin(frame["game_id"]), "rest_diff"]
    out: dict[str, Any] = {"games_by_model": {}, "models": {}}
    for model, group in frame.groupby("model"):
        sub = group.set_index("game_id").join(rest)
        p = sub["p"].to_numpy(dtype=np.float64)
        y = sub["home_won"].to_numpy(dtype=np.float64)
        out["games_by_model"][str(model)] = len(sub)
        block = _summary(str(model), p, y, reliability(p, y))
        has_margin = sub["exp_margin"].notna() & sub["rest_diff"].notna()
        if has_margin.any():
            resid = (sub["margin"] - sub["exp_margin"])[has_margin].to_numpy(dtype=np.float64)
            block["margin_residual_by_rest_diff"] = _binned(
                binned_residuals(
                    sub.loc[has_margin, "rest_diff"].to_numpy(dtype=np.float64), resid, N_BINS
                )
            )
        out["models"][str(model)] = block
    out["n_games"] = len(forecasts["games"])
    out["published"] = forecasts["published"]
    return out


def _print_tests(model: str, tests: dict[str, Any]) -> None:
    print(f"\n{model}: per feature (win = encompassing, margin = OLS)")
    print(
        f"{'feature':>16} {'coef':>10} {'ci95':>22} {'p':>9} {'p_holm':>9} "
        f"{'sign':>6} {'margin_p_holm':>13}  flag"
    )
    for f, t in tests.items():
        w = t["win"]
        lo, hi = w["coef"] - 1.959964 * w["se"], w["coef"] + 1.959964 * w["se"]
        sign = f"{t['seasons_same_sign']}/{t['seasons_with_feature']}"
        print(
            f"{f:>16} {w['coef']:>+10.4f} [{lo:>+9.4f},{hi:>+9.4f}] {w['p']:>9.4f} "
            f"{w['p_holm']:>9.4f} {sign:>6} {t['margin']['p_holm']:>13.4f}  {t['flag']}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    games = load_games(args.db)
    feats = pregame_features(games)
    elo = elo_pregame(games, ELO_LIVE_PARAMS)
    margin_scale = float(
        json.loads(ELO_REPORT.read_text(encoding="utf-8"))["tuned"]["margin_scale"]
    )
    scored = scored_games(games, feats, elo)

    m5_rows, m5_meta = load_m5(M5_GAMES)
    m5_scored_frame = scored.join(m5_rows[["split", "actual_margin"]], how="inner")
    mismatch = int((m5_scored_frame["actual_margin"] != m5_scored_frame["margin"]).sum())
    m5_meta["rows_scored"] = len(m5_scored_frame)
    m5_meta["rows_scored_by_split"] = {
        str(k): int(v) for k, v in m5_scored_frame["split"].value_counts().sort_index().items()
    }
    m5_meta["actual_margin_mismatches_vs_mart"] = mismatch

    frames = {
        "elo": model_frame(scored, "elo", margin_scale, None),
        "m5": model_frame(scored, "m5", margin_scale, m5_rows),
    }
    models_out: dict[str, Any] = {}
    print(f"Elo margin scale (reports/backtest_elo.json tuned): {margin_scale:.5f}")
    print(f"M5 mismatches between CSV actual margin and mart margin: {mismatch}")
    for name, df in frames.items():
        features = _features_for(name)
        tests = feature_tests(df, features)
        _print_tests(name, tests)
        y = df["home_won"].to_numpy(dtype=np.float64)
        p = df["p"].to_numpy(dtype=np.float64)
        ll = float(per_game_log_loss(p, y).mean())
        print(
            f"{name}: scored games {len(df)}, pooled log loss {ll:.6f}, "
            f"home-win rate {y.mean():.4f}, mean p {p.mean():.4f}"
        )
        models_out[name] = {
            "games": len(df),
            "features": features,
            "log_loss_pooled": _r(ll),
            "tests": tests,
            "reliability": reliability_tables(df),
            "binned": binned_block(df, features),
        }
        rel = models_out[name]["reliability"]
        print(f"{name} by season (n, mean p, actual, gap):")
        for row in rel["by_season"]:
            print(
                f"  {row['key']} {row['n']:>4} {row['mean_p_home']:.4f} "
                f"{row['actual_home_win']:.4f} {row['gap_p_minus_actual']:+.4f}"
            )

    flagged = [
        f"{m}:{f}"
        for m, block in models_out.items()
        for f, t in block["tests"].items()
        if t["flag"] == FLAG
    ]
    print(f"\nflagged candidate evidence: {flagged or 'none'}")

    live = live_section(Store(root=REPO), feats)
    print(f"\nLive {LIVE_SEASON} (descriptive): {live['n_games']} games")
    for m, block in live["models"].items():
        print(
            f"  {m}: n {block['n']} mean p {block['mean_p_home']:.4f} "
            f"actual {block['actual_home_win']:.4f}"
        )

    out = {
        "question": "Do pre-game features the models do not use explain their errors?",
        "db": str(args.db),
        "scored_seasons": SCORED_SEASONS,
        "scoring_rule": "played, not forfeit, not neutral; ratings replayed over all played games "
        "from the earliest season in the mart",
        "elo_live_params": {
            "k": ELO_LIVE_PARAMS.k,
            "hca": ELO_LIVE_PARAMS.hca,
            "reversion": ELO_LIVE_PARAMS.reversion,
        },
        "elo_margin_scale": margin_scale,
        "elo_margin_scale_source": "reports/backtest_elo.json tuned.margin_scale",
        "m5": m5_meta,
        "descriptions": DESCRIPTIONS,
        "flagged": flagged,
        "models": models_out,
        "live": live,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(_clean(out), indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT_JSON}")


def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return _r(float(obj))
    if isinstance(obj, np.ndarray):
        return [_clean(v) for v in obj.tolist()]
    return obj


if __name__ == "__main__":
    main()
