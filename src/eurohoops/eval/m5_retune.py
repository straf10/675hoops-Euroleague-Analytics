"""M5 retune protocol v1 (docs/models/m5.md): nine rolling-origin folds, 12 settings, run once."""

from __future__ import annotations

import math
import subprocess
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import M5Backtest, M5Grid, M5Retune
from eurohoops.eval.common import round_finite
from eurohoops.eval.m5_backtest import (
    M5Inputs,
    PlayerPartFn,
    _Option,
    prepare_context,
    projected_for_option,
)
from eurohoops.eval.m7_backtest import cluster_bootstrap_ci
from eurohoops.eval.metrics import crps_normal, per_game_log_loss
from eurohoops.models.m5 import fit_residual
from eurohoops.models.team_eff import fit_margin_model
from eurohoops.models.turnover import mixed_team_adjustment, roster_continuity


@dataclass(frozen=True)
class RetuneSetting:
    shares: str
    half_life_games: float | None
    turnover: bool
    residual_half_life_days: float

    def key(self) -> str:
        shares = (
            self.shares
            if self.half_life_games is None
            else f"{self.shares}@{self.half_life_games:g}"
        )
        base = f"{shares}|core|d{self.residual_half_life_days:g}|r40"
        return base if not self.turnover else f"{base}|T"


def retune_backtest_spec(retune: M5Retune) -> M5Backtest:
    return M5Backtest(
        retune.report,
        retune.games_report,
        warmup=retune.warmup,
        tuning=retune.folds,
        validation=(),
        test=(retune.folds[-1],),  # frame end season; retune scores via folds, not this split
        grid=M5Grid(
            half_life_games=(retune.avail_half_life_games,),
            residual_half_life_days=retune.residual_half_life_days,
            residual_ridge=(retune.residual_ridge,),
            rest_ridge=(),
        ),
        margin_variant=retune.margin_variant,
        bootstrap_resamples=retune.bootstrap_resamples,
        bootstrap_seed=retune.bootstrap_seed,
    )


def grid_settings(retune: M5Retune) -> list[RetuneSetting]:
    out: list[RetuneSetting] = []
    for h in retune.residual_half_life_days:
        for turnover in (False, True):
            out.append(RetuneSetting("proj_hc", None, turnover, h))
            out.append(RetuneSetting("proj_avail", retune.avail_half_life_games, turnover, h))
    return out


def _margin_for_setting(
    ctx: Any,
    spec: M5Backtest,
    player_part: np.ndarray,
    setting: RetuneSetting,
    continuity: pd.DataFrame,
) -> np.ndarray:
    ridge = spec.grid.residual_ridge[0]
    target = np.where(ctx.rated, ctx.margin - player_part, np.nan)
    half_life = setting.residual_half_life_days
    full = fit_residual(
        ctx.frame,
        target,
        None,
        half_life_days=half_life,
        residual_ridge=ridge,
        rest_ridge=0.0,
    )
    if not setting.turnover:
        margin: np.ndarray = player_part + full.adjustment
        return margin
    season = fit_residual(
        ctx.frame,
        target,
        None,
        half_life_days=half_life,
        residual_ridge=ridge,
        rest_ridge=0.0,
        season_only=True,
    )
    home_flag = np.where(ctx.frame["neutral"].to_numpy(dtype=bool), 0.0, 1.0)
    c_home = continuity["c_home"].to_numpy(dtype=np.float64)
    c_away = continuity["c_away"].to_numpy(dtype=np.float64)
    adj = mixed_team_adjustment(full, season, c_home, c_away, home_flag)
    out: np.ndarray = player_part + adj
    return out


def _scored_mask(ctx: Any, margins: dict[str, np.ndarray], seasons: tuple[int, ...]) -> np.ndarray:
    season = ctx.season
    base = ctx.rated & np.isin(season, seasons) & ctx.comparison_ok
    for margin in margins.values():
        base = base & np.isfinite(margin)
    scored: np.ndarray = base
    return scored


def _p_home_by_fold(
    ctx: Any,
    spec: M5Backtest,
    margin: np.ndarray,
    seasons: tuple[int, ...],
) -> np.ndarray:
    """Walk-forward margin model: season t uses rated games in seasons < t."""
    p_home = np.full(len(margin), np.nan)
    for season in seasons:
        train = ctx.rated & (ctx.season < season) & np.isfinite(margin)
        score = ctx.rated & (ctx.season == season) & np.isfinite(margin)
        if not train.any() or not score.any():
            continue
        model = fit_margin_model(
            spec.margin_variant,
            margin[train],
            np.ones(int(train.sum())),
            ctx.margin[train],
        )
        p_home[score] = model.p_home(margin[score], np.ones(int(score.sum())))
    return p_home


def _simplicity(setting: RetuneSetting) -> tuple[int, float]:
    additions = int(setting.turnover) + int(setting.shares == "proj_avail")
    return additions, abs(setting.residual_half_life_days - 180.0)


def _season_mean_log_loss(p_home: np.ndarray, home_won: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return math.nan
    return float(per_game_log_loss(p_home[mask], home_won[mask]).mean())


def _gap_seasons(
    ctx: Any,
    scored: np.ndarray,
    p_a: np.ndarray,
    p_b: np.ndarray,
    seasons: tuple[int, ...],
) -> list[float]:
    return [
        _season_mean_log_loss(p_a, ctx.home_won, scored & (ctx.season == season))
        - _season_mean_log_loss(p_b, ctx.home_won, scored & (ctx.season == season))
        for season in seasons
    ]


def _bootstrap_se(values: list[float], resamples: int, seed: int) -> float:
    finite = [v for v in values if math.isfinite(v)]
    if len(finite) < 2:
        return 0.0
    arr = np.asarray(finite, dtype=np.float64)
    cluster = np.arange(len(arr), dtype=np.int64)
    _, low, high = cluster_bootstrap_ci(arr, cluster, resamples, seed)
    return float((high - low) / 3.92)


def _select_setting(
    table: list[tuple[RetuneSetting, float]], se_by_key: dict[str, float]
) -> RetuneSetting:
    finite = [(s, loss) for s, loss in table if math.isfinite(loss)]
    if not finite:
        raise ValueError("no setting has a finite pooled log loss")
    losses = {s.key(): loss for s, loss in finite}
    best = min(losses.values())
    within = [s for s, loss in finite if loss - best <= se_by_key[s.key()] + 1e-15]
    return min(within, key=lambda s: (*_simplicity(s), losses[s.key()]))


def run_retune(
    inputs: M5Inputs,
    *,
    retune: M5Retune,
    player_part: PlayerPartFn,
    git_head: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    spec = retune_backtest_spec(retune)
    games = inputs.games[inputs.games["season"] <= retune.folds[-1]].copy()
    trimmed = M5Inputs(
        games=games,
        team_games=inputs.team_games,
        player_games=inputs.player_games,
        tuned_m1=inputs.tuned_m1,
        elo=inputs.elo,
    )
    ctx = prepare_context(trimmed, spec)
    continuity = roster_continuity(ctx.frame, trimmed.player_games).set_index("game_id")
    continuity = continuity.reindex(ctx.frame["game_id"].astype(str))

    options = {
        "proj_hc": _Option("proj_hc", None),
        "proj_avail": _Option("proj_avail", retune.avail_half_life_games),
    }
    parts = {
        name: player_part(
            ctx.frame,
            projected_for_option(opt, ctx.frame, trimmed.player_games, spec),
        )
        for name, opt in options.items()
    }

    settings = grid_settings(retune)
    margins: dict[str, np.ndarray] = {}
    for setting in settings:
        part = parts[setting.shares]
        margins[setting.key()] = _margin_for_setting(ctx, spec, part, setting, continuity)

    scored = _scored_mask(ctx, margins, retune.folds)
    p_home_by: dict[str, np.ndarray] = {
        key: _p_home_by_fold(ctx, spec, margin, retune.folds) for key, margin in margins.items()
    }

    rows: list[dict[str, Any]] = []
    per_setting_loss: dict[str, float] = {}
    for setting in settings:
        key = setting.key()
        mask = scored & np.isfinite(p_home_by[key])
        loss = float(per_game_log_loss(p_home_by[key][mask], ctx.home_won[mask]).mean())
        per_setting_loss[key] = loss
        for season in retune.folds:
            sm = mask & (ctx.season == season)
            if not sm.any():
                continue
            rows.append(
                {
                    "season": int(season),
                    "setting": key,
                    "games": int(sm.sum()),
                    "log_loss": float(
                        per_game_log_loss(p_home_by[key][sm], ctx.home_won[sm]).mean()
                    ),
                }
            )

    table = [(s, per_setting_loss[s.key()]) for s in settings]
    best_key = min(table, key=lambda x: x[1])[0].key()
    se_by_key: dict[str, float] = {}
    for setting in settings:
        key = setting.key()
        gaps = _gap_seasons(ctx, scored, p_home_by[key], p_home_by[best_key], retune.folds)
        se_by_key[key] = _bootstrap_se(gaps, retune.bootstrap_resamples, retune.bootstrap_seed)

    baseline = RetuneSetting("proj_hc", None, False, 180.0)
    selected = _select_setting(table, se_by_key)
    sel_loss = per_setting_loss[selected.key()]
    base_loss = per_setting_loss[baseline.key()]
    both = scored & np.isfinite(p_home_by[selected.key()]) & np.isfinite(p_home_by[baseline.key()])
    per_game_gap = per_game_log_loss(
        p_home_by[selected.key()][both], ctx.home_won[both]
    ) - per_game_log_loss(p_home_by[baseline.key()][both], ctx.home_won[both])
    cluster = pd.factorize(ctx.season[both])[0].astype(np.int64)
    gap_mean, gap_low, gap_high = cluster_bootstrap_ci(
        per_game_gap, cluster, retune.bootstrap_resamples, retune.bootstrap_seed
    )

    totals_crps = float(
        crps_normal(
            ctx.m1.total[scored],
            ctx.m1_total_sigma,
            ctx.total[scored],
        ).mean()
    )

    report: dict[str, Any] = {
        "model": "m5",
        "protocol": "retune_v1",
        "git_head": git_head,
        "addendum": retune.addendum,
        "folds": list(retune.folds),
        "scored_games": int(scored.sum()),
        "settings": {s.key(): round_finite(per_setting_loss[s.key()]) for s in settings},
        "se_log_loss_gap_to_best": {k: round_finite(v) for k, v in se_by_key.items()},
        "baseline": asdict(baseline),
        "selected": asdict(selected),
        "baseline_stands": selected.key() == baseline.key(),
        "pooled_log_loss": {
            "baseline": round_finite(base_loss),
            "selected": round_finite(sel_loss),
        },
        "selected_minus_baseline": {
            "mean": round_finite(gap_mean),
            "ci95": [round_finite(gap_low), round_finite(gap_high)],
        },
        "shadow_criteria": {
            "not_baseline": selected.key() != baseline.key(),
            "non_inferior": bool(gap_high < retune.shadow_log_loss_margin),
            "worth_it": bool(gap_mean <= -retune.shadow_log_loss_margin),
        },
        "totals_crps_m1_rest": round_finite(totals_crps),
    }
    detail = pd.DataFrame(rows)
    return report, detail


def retune_check(
    inputs: M5Inputs,
    *,
    retune: M5Retune,
    player_part: PlayerPartFn,
    baseline_games: pd.DataFrame,
) -> dict[str, Any]:
    spec = retune_backtest_spec(retune)
    games = inputs.games[inputs.games["season"] <= retune.folds[-1]].copy()
    trimmed = M5Inputs(
        games=games,
        team_games=inputs.team_games,
        player_games=inputs.player_games,
        tuned_m1=inputs.tuned_m1,
        elo=inputs.elo,
    )
    ctx = prepare_context(trimmed, spec)
    continuity = roster_continuity(ctx.frame, trimmed.player_games).set_index("game_id")
    continuity = continuity.reindex(ctx.frame["game_id"].astype(str))
    opt = _Option("proj_hc", None)
    part = player_part(
        ctx.frame,
        projected_for_option(opt, ctx.frame, trimmed.player_games, spec),
    )
    setting = RetuneSetting("proj_hc", None, False, 180.0)
    margin = _margin_for_setting(ctx, spec, part, setting, continuity)
    scored = ctx.rated & np.isin(ctx.season, retune.folds) & ctx.comparison_ok & np.isfinite(margin)
    ref = baseline_games[
        (baseline_games["model"] == "m5") & baseline_games["season"].isin(retune.folds)
    ][["game_id", "exp_margin"]]
    frame = pd.DataFrame(
        {"game_id": ctx.frame["game_id"].astype(str), "exp_margin": margin, "scored": scored}
    )
    ours = frame[frame["scored"]][["game_id", "exp_margin"]]
    merged = ours.merge(ref, on="game_id", suffixes=("_retune", "_backtest"))
    diff = np.abs(merged["exp_margin_retune"] - merged["exp_margin_backtest"].astype(float))
    per_fold = {str(int(s)): int((ctx.season[scored] == s).sum()) for s in retune.folds}
    return {
        "scored_games": int(scored.sum()),
        "per_fold_games": per_fold,
        "max_margin_abs_diff": float(diff.max()) if len(diff) else math.nan,
        "aligned_games": len(merged),
    }


def git_head_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def is_clean_tree() -> bool:
    out = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    return not out.strip()
