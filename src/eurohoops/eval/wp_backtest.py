"""In-game WP backtest (docs/models/wp.md): data build, the two families, the isotonic calibration,
the validation choice, the one test read, the paired game bootstrap gate and the report.

Splits are by season (section 3): train 2007-2022, validation 2023, test 2024-2025. The validation
season picks the GBM setting (raw log loss) and the family (calibrated log loss). The test seasons
are scored once, after every choice is frozen. Pure fitting code is in ``eurohoops.models.wp``.
"""

import gzip
import json
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from eurohoops.models import wp as wpm
from eurohoops.models.elo import EloParams, fit_margin_scale, prepare, replay
from eurohoops.models.wp import Calibrated, Family, FloatArray
from eurohoops.parallel import map_ordered, record
from eurohoops.parse.wp_pbp import MARKERS, SCORING_CODES, parse_game

ELO = EloParams(k=20.0, hca=90.0, reversion=0.25)  # the live parameters (elo.replay)
FIRST_SEASON = 2007
LAST_SEASON = 2025  # 2026 is partial and unused (section 2)
TRAIN = tuple(range(2007, 2023))
OOF_SEASONS = tuple(range(2010, 2023))
VALIDATION = (2023,)
TEST = (2024, 2025)
EVAL = (*VALIDATION, *TEST)
BUCKETS = ("Q1", "Q2", "Q3", "Q4", "last_2_min", "OT")
GROUPS = ("all", *BUCKETS)
EXCLUSION_REASONS = ("not_played", "no_file", "code_mismatch", "bad_clock", "score_mismatch")
REG_CHECKPOINTS = np.arange(2340, -1, -60).astype(float)  # t = 2340 .. 0 (tip-off excluded)
OT_CHECKPOINTS = np.arange(300, -1, -60).astype(float)  # per OT period, t = 300 .. 0
PROB_BINS = 10
Progress = Callable[[str], None]


def _no_progress(_message: str) -> None:
    return None


def build_games(games: pd.DataFrame) -> pd.DataFrame:
    """Mart games 2007-2025 in tip-off order, with the Elo pre-game probability (section 4.1)."""
    g = games[games["season"].between(FIRST_SEASON, LAST_SEASON)]
    g = g.sort_values("tipoff_utc", kind="stable").reset_index(drop=True).copy()
    g["gid"] = np.arange(len(g))
    g["margin"] = (g["home_score"] - g["away_score"]).fillna(0).astype(int)
    g["y"] = (g["home_score"] > g["away_score"]).fillna(False).astype(int)  # unplayed: NA
    g["diff"] = replay(prepare(g), ELO)
    p_pre = np.clip(1.0 / (1.0 + 10.0 ** (-g["diff"] / 400.0)), wpm.PROB_CLIP, 1 - wpm.PROB_CLIP)
    g["p_pre"] = p_pre
    g["logit_pre"] = np.log(p_pre / (1.0 - p_pre))
    g["reason"] = None
    return g


def _game_file(raw_dir: Path, season: int, game_id: str) -> Path:
    return raw_dir / "playbyplay" / f"E{season}" / f"{str(game_id).split('_')[-1]}.json.gz"


def _events(rows: tuple[Any, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period": [r.period for r in rows],
            "ot": [r.ot for r in rows],
            "t": [r.t for r in rows],
            "elapsed": [r.elapsed for r in rows],
            "ptype": [r.ptype for r in rows],
            "m": [r.s_home - r.s_away for r in rows],
        }
    )


def checkpoint_states(ev: pd.DataFrame) -> pd.DataFrame:
    """The state at every checkpoint of one game (section 6): the last play at or before it."""
    overtime = ev.loc[(ev["ot"] == 1) & ~ev["ptype"].isin(MARKERS), "period"]
    n_ot = int(overtime.max() - 4) if len(overtime) else 0
    elapsed = ev["elapsed"].to_numpy(float)
    m_arr = ev["m"].to_numpy(float)
    run = np.maximum.accumulate(elapsed)
    t_parts = [REG_CHECKPOINTS]
    e_parts = [wpm.GAME_SECONDS - REG_CHECKPOINTS]
    ot_parts = [np.zeros(len(REG_CHECKPOINTS))]
    for k in range(1, n_ot + 1):
        t_parts.append(OT_CHECKPOINTS)
        e_parts.append(wpm.GAME_SECONDS + (k - 1) * 300.0 + (300.0 - OT_CHECKPOINTS))
        ot_parts.append(np.ones(len(OT_CHECKPOINTS)))
    t_all = np.concatenate(t_parts)
    e_all = np.concatenate(e_parts)
    idx = np.searchsorted(run, e_all, side="right") - 1
    m_all = np.where(idx >= 0, m_arr[np.clip(idx, 0, None)], 0.0)
    return pd.DataFrame({"t": t_all, "ot": np.concatenate(ot_parts), "m": m_all})


def _read_game(raw_dir: Path, row: Any) -> tuple[str | None, pd.DataFrame | None]:
    if not bool(row.played) or bool(row.forfeit):
        return "not_played", None
    path = _game_file(raw_dir, int(row.season), row.game_id)
    if not path.exists():
        return "no_file", None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        parsed = parse_game(json.load(fh), row.home, row.away)
    if not parsed.code_ok:
        return "code_mismatch", None
    if parsed.bad_clock_events:
        return "bad_clock", None
    if (parsed.final_home, parsed.final_away) != (int(row.home_score), int(row.away_score)):
        return "score_mismatch", None
    return None, _events(parsed.rows)


def _read_game_item(item: tuple[Path, SimpleNamespace]) -> tuple[str | None, pd.DataFrame | None]:
    """``_read_game`` for one (raw_dir, game) pair: a picklable item for worker processes."""
    raw_dir, row = item
    return _read_game(raw_dir, row)


def build(games: pd.DataFrame, raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Games with exclusion reasons, scoring-event training rows, and checkpoint rows."""
    g = build_games(games)
    scoring: list[pd.DataFrame] = []
    checks: list[pd.DataFrame] = []
    rows: list[Any] = list(g.itertuples(index=False))
    # the play-by-play of each game is read and parsed in a worker; results stay in game order
    read = map_ordered(
        _read_game_item,
        [(raw_dir, record(row)) for row in g.to_dict("records")],
    )
    for row, (reason, ev) in zip(rows, read, strict=True):
        g.loc[row.gid, "reason"] = reason
        if reason is not None or ev is None:
            continue
        base = {
            "gid": row.gid,
            "season": int(row.season),
            "phase": row.phase,
            "logit_pre": float(row.logit_pre),
            "neutral": float(bool(row.neutral)),
            "y": int(row.y),
            "diff": float(row.diff),
        }
        sc = ev[ev["ptype"].isin(SCORING_CODES)]
        scoring.append(
            pd.DataFrame(
                {
                    **base,
                    "gid": row.gid,
                    "t": sc["t"].to_numpy(float),
                    "ot": sc["ot"].to_numpy(float),
                    "m": sc["m"].to_numpy(float),
                }
            )
        )
        ck = checkpoint_states(ev)
        checks.append(pd.DataFrame({**base, **{c: ck[c].to_numpy(float) for c in ck.columns}}))
    training = pd.concat(scoring, ignore_index=True)
    states = pd.concat(checks, ignore_index=True)
    return g, training, states


def fold_scale(games: pd.DataFrame, season: int) -> float:
    """The Elo margin scale ``s`` for ``season``, fitted on included games of earlier seasons."""
    earlier = games[games["season"] < season]
    return fit_margin_scale(earlier["diff"].to_numpy(float), earlier["margin"].to_numpy(float))


def _state(df: pd.DataFrame) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    return (
        df["m"].to_numpy(float),
        df["t"].to_numpy(float),
        df["ot"].to_numpy(float),
        df["logit_pre"].to_numpy(float),
        df["neutral"].to_numpy(float),
    )


def _fit(name: str, setting: str | None, train: pd.DataFrame) -> Family:
    return wpm.fit_family(name, setting, _state(train), train["y"].to_numpy(float))


def _scored(ck: pd.DataFrame, p: FloatArray) -> pd.DataFrame:
    out = ck[["gid", "season", "phase", "t", "ot", "y"]].copy()
    out["p"] = p
    out["ll"] = wpm.log_loss(out["y"].to_numpy(float), p)
    out["brier"] = (p - out["y"].to_numpy(float)) ** 2
    return out


def _bootstrap(mat: FloatArray, seed: int, resamples: int) -> FloatArray:
    """Paired bootstrap over whole games: one resample index set shared by every column."""
    rng = np.random.default_rng(seed)
    n = mat.shape[0]
    out = np.empty((resamples, mat.shape[1]))
    for start in range(0, resamples, 500):
        size = min(500, resamples - start)
        idx = rng.integers(0, n, size=(size, n))
        out[start : start + size] = mat[idx].mean(axis=1)
    return out


def _ci(values: FloatArray) -> list[float]:
    lo, hi = np.percentile(values, [2.5, 97.5])
    return [float(lo), float(hi)]


def bucket_masks(ck: pd.DataFrame) -> dict[str, np.ndarray]:
    """Section 6 buckets; Q4 includes t = 600 and t = 0; the last 2 minutes is inside Q4."""
    ot = ck["ot"].to_numpy() == 1
    t = ck["t"].to_numpy(float)
    reg = ~ot
    return {
        "Q1": reg & (t > 1800),
        "Q2": reg & (t > 1200) & (t <= 1800),
        "Q3": reg & (t > 600) & (t <= 1200),
        "Q4": reg & (t <= 600),
        "last_2_min": reg & (t <= 120),
        "OT": ot,
    }


def calibration(scored: pd.DataFrame) -> dict[str, Any]:
    """Calibration by bucket, each game weighted equally (its checkpoints share weight 1)."""
    out: dict[str, Any] = {}
    masks = bucket_masks(scored)
    for name in BUCKETS:
        sub = scored[masks[name]]
        if sub.empty:
            out[name] = {"games": 0, "checkpoints": 0}
            continue
        w = 1.0 / sub.groupby("gid")["gid"].transform("size").to_numpy(float)
        p = sub["p"].to_numpy(float)
        y = sub["y"].to_numpy(float)
        total = w.sum()
        mean_p = float((w * p).sum() / total)
        observed = float((w * y).sum() / total)
        var = float((w * (p - mean_p) ** 2).sum() / total)
        cov = float((w * (p - mean_p) * (y - observed)).sum() / total)
        bin_of = np.minimum((p * PROB_BINS).astype(int), PROB_BINS - 1)
        bins = []
        for b in range(PROB_BINS):
            sel = bin_of == b
            wb = w[sel].sum()
            bins.append(
                {
                    "bin": b,
                    "weight_games": float(wb),
                    "mean_predicted": float((w[sel] * p[sel]).sum() / wb) if wb > 0 else None,
                    "observed": float((w[sel] * y[sel]).sum() / wb) if wb > 0 else None,
                }
            )
        out[name] = {
            "games": int(sub["gid"].nunique()),
            "checkpoints": len(sub),
            "mean_predicted": mean_p,
            "observed_home_win": observed,
            "gap": mean_p - observed,
            "within_tolerance": bool(abs(mean_p - observed) <= wpm.SPEC["tolerance"]),
            "slope": cov / var if var > 0 else None,
            "bins": bins,
        }
    return out


def summarise(scored: pd.DataFrame, base: pd.DataFrame, seed: int) -> dict[str, Any]:
    """Per-game log loss and Brier (checkpoint mean first, then games) for the model and baseline,
    with paired 95% bootstrap intervals over games (the same resample for every column)."""
    m_game = scored.groupby("gid")[["ll", "brier"]].mean().sort_index()
    b_game = base.groupby("gid")[["ll", "brier"]].mean().sort_index()
    mat = np.column_stack(
        [m_game["ll"], b_game["ll"], m_game["brier"], b_game["brier"], m_game["ll"] - b_game["ll"]]
    )
    boot = _bootstrap(mat, seed, wpm.GATE_RESAMPLES)
    means = mat.mean(axis=0)
    names = ("model_logloss", "baseline_logloss", "model_brier", "baseline_brier", "delta_logloss")
    cis = {n: _ci(boot[:, i]) for i, n in enumerate(names)}
    return {
        "games": int(mat.shape[0]),
        "checkpoints": len(scored),
        "model": {
            "logloss": float(means[0]),
            "logloss_ci95": cis["model_logloss"],
            "brier": float(means[2]),
            "brier_ci95": cis["model_brier"],
        },
        "baseline": {
            "logloss": float(means[1]),
            "logloss_ci95": cis["baseline_logloss"],
            "brier": float(means[3]),
            "brier_ci95": cis["baseline_brier"],
        },
        "delta_logloss": {"mean": float(means[4]), "ci95": cis["delta_logloss"]},
        "_delta_boot": boot[:, 4],
    }


def _strip(summary: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in summary.items() if not k.startswith("_")}


def _family_scores(
    ck: pd.DataFrame, fam_raw: Family, calibrated: Calibrated | None
) -> dict[str, Any]:
    raw = _scored(ck, fam_raw.predict_raw(*_state(ck)))
    out: dict[str, Any] = {
        "raw": {
            "logloss": float(raw.groupby("gid")["ll"].mean().mean()),
            "brier": float(raw.groupby("gid")["brier"].mean().mean()),
        },
    }
    if calibrated is not None:
        cal = _scored(ck, calibrated.predict(*_state(ck)))
        out["calibrated"] = {
            "logloss": float(cal.groupby("gid")["ll"].mean().mean()),
            "brier": float(cal.groupby("gid")["brier"].mean().mean()),
        }
    return out


def _gbm_grid(
    train: pd.DataFrame, val: pd.DataFrame
) -> tuple[str, dict[str, Family], list[dict[str, Any]]]:
    fams: dict[str, Family] = {}
    rows: list[dict[str, Any]] = []
    for setting, (n_est, depth, lr) in wpm.GBM_GRID.items():
        fam = _fit("gbm", setting, train)
        fams[setting] = fam
        raw = _scored(val, fam.predict_raw(*_state(val)))
        rows.append(
            {
                "setting": setting,
                "n_estimators": n_est,
                "max_depth": depth,
                "learning_rate": lr,
                "validation_logloss_raw": float(raw.groupby("gid")["ll"].mean().mean()),
            }
        )
    best = rows[0]
    for row in rows[1:]:
        if row["validation_logloss_raw"] < best["validation_logloss_raw"]:
            best = row
    return str(best["setting"]), fams, rows


def _oof_isotonic(s: pd.DataFrame, name: str, setting: str | None) -> IsotonicRegression:
    raw: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for season in OOF_SEASONS:
        fam = _fit(name, setting, s[s["season"] < season])
        rows = s[s["season"] == season]
        raw.append(fam.predict_raw(*_state(rows)))
        ys.append(rows["y"].to_numpy(float))
    return wpm.fit_isotonic(np.concatenate(raw), np.concatenate(ys))


def run(
    games: pd.DataFrame, raw_dir: Path, progress: Progress = _no_progress
) -> tuple[dict[str, Any], pd.DataFrame]:
    """The whole protocol: returns the report and the per-game, per-group CSV rows."""
    t0 = time.perf_counter()
    g, train_rows, states = build(games, raw_dir)
    progress(
        f"built {len(g)} games, {len(train_rows)} scoring rows in {time.perf_counter() - t0:.0f}s"
    )
    included = g[g["reason"].isna()]
    s_train = train_rows[train_rows["season"].isin(TRAIN)]
    ck_val = states[states["season"].isin(VALIDATION)]
    ck_test = states[states["season"].isin(TEST)]

    setting, fams, grid = _gbm_grid(s_train, ck_val)
    progress(f"GBM grid done, chosen {setting} in {time.perf_counter() - t0:.0f}s")
    logit = _fit("logit", None, s_train)
    gbm = fams[setting]
    progress(f"logit fitted in {time.perf_counter() - t0:.0f}s")

    iso_logit = _oof_isotonic(train_rows, "logit", None)
    iso_gbm = _oof_isotonic(train_rows, "gbm", setting)
    progress(f"out-of-fold isotonic done in {time.perf_counter() - t0:.0f}s")
    cal = {"logit": Calibrated(logit, iso_logit), "gbm": Calibrated(gbm, iso_gbm)}
    families = {
        "logit": _family_scores(ck_val, logit, cal["logit"]),
        "gbm": _family_scores(ck_val, gbm, cal["gbm"]),
    }
    # Section 5: the family with the lower calibrated validation log loss; ties go to the logit.
    gbm_ll = families["gbm"]["calibrated"]["logloss"]
    chosen = "gbm" if gbm_ll < families["logit"]["calibrated"]["logloss"] else "logit"
    model = cal[chosen]

    scales = {s: fold_scale(included, s) for s in EVAL}
    ck_val = _with_baseline_mu(ck_val, scales)
    ck_test = _with_baseline_mu(ck_test, scales)

    val_model, val_base = _scored_pair(model, ck_val)
    test_model, test_base = _scored_pair(model, ck_test)
    validation = summarise(val_model, val_base, wpm.GATE_SEED)
    validation["calibration"] = {"model": calibration(val_model), "baseline": calibration(val_base)}
    test = summarise(test_model, test_base, wpm.GATE_SEED)
    test["calibration"] = {"model": calibration(test_model), "baseline": calibration(test_base)}
    test["by_season"] = {
        str(season): _strip(
            summarise(
                test_model[test_model["season"] == season],
                test_base[test_base["season"] == season],
                wpm.GATE_SEED,
            )
        )
        for season in TEST
    }
    # Section 6 gate: 95% paired CI over games entirely below zero, and the mean negative.
    passes = bool(test["delta_logloss"]["ci95"][1] < 0 and test["delta_logloss"]["mean"] < 0)
    progress(f"test scored in {time.perf_counter() - t0:.0f}s")

    # Section 7: g = P_pre - WP_model(t = 2400, m = 0) for each test game, from the frozen model.
    tip = g[g["gid"].isin(ck_test["gid"].unique())]
    n = len(tip)
    tip_model = model.predict(
        np.zeros(n),
        np.full(n, wpm.GAME_SECONDS),
        np.zeros(n),
        tip["logit_pre"].to_numpy(float),
        tip["neutral"].to_numpy(float),
    )
    gaps = tip["p_pre"].to_numpy(float) - tip_model

    report = _report(
        g=g,
        included=included,
        train_rows=train_rows,
        grid=grid,
        families=families,
        chosen=chosen,
        setting=setting,
        validation=validation,
        test=test,
        passes=passes,
        scales=scales,
        gaps=gaps,
        seconds=time.perf_counter() - t0,
    )
    return report, _game_rows(test_model, test_base, g)


def _with_baseline_mu(ck: pd.DataFrame, scales: dict[int, float]) -> pd.DataFrame:
    """Adds ``mu`` = pre-game expected margin, Elo difference over the season's scale."""
    out = ck.copy()
    scale = np.asarray(out["season"].map(scales), dtype=np.float64)
    out["mu"] = wpm.baseline_mu(out["diff"].to_numpy(float), scale)
    return out


def _scored_pair(model: Calibrated, ck: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The chosen model's and the closed-form baseline's scored checkpoints."""
    p_model = model.predict(*_state(ck))
    p_base = wpm.baseline_wp(
        ck["m"].to_numpy(float), ck["t"].to_numpy(float), ck["mu"].to_numpy(float)
    )
    return _scored(ck, p_model), _scored(ck, p_base)


def _report(**kw: Any) -> dict[str, Any]:
    g: pd.DataFrame = kw["g"]
    included: pd.DataFrame = kw["included"]
    test: dict[str, Any] = kw["test"]
    validation: dict[str, Any] = kw["validation"]
    passes: bool = kw["passes"]
    gaps: FloatArray = kw["gaps"]
    excl = g["reason"].dropna().value_counts()
    by_season = {
        str(s): {r: int(((g["season"] == s) & (g["reason"] == r)).sum()) for r in EXCLUSION_REASONS}
        for s in range(FIRST_SEASON, LAST_SEASON + 1)
    }
    chosen_setting = kw["setting"] if kw["chosen"] == "gbm" else None
    return {
        "version": wpm.VERSION,
        "spec_sha256": wpm.SPEC_SHA256,
        "spec": wpm.SPEC,
        "protocol": "docs/models/wp.md",
        "scope": "EuroLeague play-by-play, seasons 2007-2025. The 2026 partial season is unused.",
        "counts": {
            "mart_games_2007_2025": len(g),
            "included_games": len(included),
            "excluded_games": int(g["reason"].notna().sum()),
            "exclusion_reasons": {r: int(excl.get(r, 0)) for r in EXCLUSION_REASONS},
            "exclusions_by_season": by_season,
            "train_games": int(included["season"].isin(TRAIN).sum()),
            "validation_games": int(included["season"].isin(VALIDATION).sum()),
            "test_games": int(included["season"].isin(TEST).sum()),
        },
        "gbm_grid": kw["grid"],
        "families": kw["families"],
        "chosen": {
            "family": kw["chosen"],
            "gbm_setting": chosen_setting,
            "random_state": wpm.GBM_RANDOM_STATE if kw["chosen"] == "gbm" else None,
        },
        "margin_scale_by_season": {str(k): float(v) for k, v in kw["scales"].items()},
        "validation": _strip(validation),
        "test": _strip(test),
        "gate": {
            "rule": "95% paired bootstrap CI over games of mean delta log loss lies below zero, "
            "and the mean delta is negative",
            "delta_logloss_mean": test["delta_logloss"]["mean"],
            "delta_logloss_ci95": test["delta_logloss"]["ci95"],
            "resamples": wpm.GATE_RESAMPLES,
            "seed": wpm.GATE_SEED,
            "passes": passes,
            "game_pages_use": "model" if passes else "baseline",
        },
        "tipoff_gap_test_games": {
            "mean": float(np.mean(gaps)),
            "mean_abs": float(np.mean(np.abs(gaps))),
            "p95_abs": float(np.percentile(np.abs(gaps), 95)),
        },
        "train_rows": {"scoring_rows": int(kw["train_rows"]["season"].isin(TRAIN).sum())},
        "runtime_seconds": round(kw["seconds"], 1),
    }


def _game_rows(model: pd.DataFrame, base: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """One row per test game and checkpoint group: the group's means and per-checkpoint losses."""
    m = model.assign(
        p_base=base["p"].to_numpy(float),
        ll_base=base["ll"].to_numpy(float),
        brier_base=base["brier"].to_numpy(float),
    )
    masks = bucket_masks(m)
    masks["all"] = np.ones(len(m), dtype=bool)
    ids = g.set_index("gid")
    frames = []
    for group in GROUPS:
        sub = m[masks[group]]
        agg = (
            sub.groupby("gid")
            .agg(
                season=("season", "first"),
                phase=("phase", "first"),
                home_won=("y", "first"),
                checkpoints=("y", "size"),
                mean_p_model=("p", "mean"),
                mean_p_baseline=("p_base", "mean"),
                logloss_model=("ll", "mean"),
                logloss_baseline=("ll_base", "mean"),
                brier_model=("brier", "mean"),
                brier_baseline=("brier_base", "mean"),
            )
            .reset_index()
        )
        agg.insert(0, "group", group)
        agg.insert(0, "game_id", ids.loc[agg["gid"], "game_id"].to_numpy())
        frames.append(agg.drop(columns="gid"))
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["season", "game_id", "group"], kind="stable").reset_index(drop=True)


def format_table(report: dict[str, Any]) -> str:
    test = report["test"]
    gate = report["gate"]
    lines = [
        f"version {report['version']}  chosen {report['chosen']['family']} "
        f"{report['chosen']['gbm_setting'] or ''}".rstrip(),
        f"test games {test['games']}  model LL {test['model']['logloss']:.4f}  "
        f"baseline LL {test['baseline']['logloss']:.4f}",
        f"delta LL {gate['delta_logloss_mean']:.4f}  CI95 "
        f"[{gate['delta_logloss_ci95'][0]:.4f}, {gate['delta_logloss_ci95'][1]:.4f}]",
        f"gate passes: {gate['passes']} (game pages use {gate['game_pages_use']})",
    ]
    return "\n".join(lines)
