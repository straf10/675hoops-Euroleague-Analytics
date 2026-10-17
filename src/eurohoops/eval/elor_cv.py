"""ELOR protocol v1 (docs/models/elo_roster_prior.md): nine rolling-origin folds, 12 settings,
live Elo as the reference, run once.

Every fold season t is scored with ratings replayed from the first warm-up season (2007), the
margin scale fitted on seasons before t, and M3 ratings walk-forward (state before each round).
Scored games: fold seasons, played, not forfeit, not neutral. Pooled metrics and every season
bootstrap are game-weighted over the resampled seasons (``m7_backtest.cluster_bootstrap_ci``'s
draw). One-SE rule: a setting is within one SE iff its pooled log-loss gap to the best is at most
the standard deviation (ddof 1) of that paired gap over the 10,000 whole-season resamples.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import ElorCv
from eurohoops.eval.common import round6
from eurohoops.eval.m7_backtest import cluster_bootstrap_ci
from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.models import elo
from eurohoops.models.elor import (
    Appearances,
    ElorSetting,
    NewcomerPrior,
    Offsets,
    RatingFn,
    SeasonEndRating,
    elor_diff,
    margin_scales,
    newcomer_priors,
    offsets,
    roster_strengths,
    round_index,
    season_starts,
    win_probabilities,
)
from eurohoops.models.minutes import round_cutoffs
from eurohoops.models.roster import (
    FIRST_ROUND_RULE,
    season_rounds,
    start_date_counts,
    unmatched_clubs,
)


@dataclass(frozen=True)
class ElorInputs:
    games: pd.DataFrame  # every EuroLeague game, any order (trimmed to the folds here)
    player_games: pd.DataFrame  # box rows: game_id, team, player_id, sec
    roster: pd.DataFrame  # models.roster.ROSTER_SCHEMA rows
    rating: RatingFn
    has_state: Callable[[int, float], bool]
    season_end_rating: SeasonEndRating  # the fit at a season's last round cutoff
    possessions: pd.Series  # expected possessions per game_id (M5's)


@dataclass(frozen=True)
class ElorContext:
    games: pd.DataFrame  # tip-off order, warm-up start to last fold
    season: np.ndarray
    rounds: np.ndarray
    elo_diff: np.ndarray
    offsets: Offsets
    strengths: pd.DataFrame
    scored: np.ndarray
    home_won: np.ndarray
    appearances: Appearances
    scales: dict[int, float]
    priors: dict[int, NewcomerPrior]


def grid_settings(spec: ElorCv) -> list[ElorSetting]:
    """The 12 settings in simplicity order (smaller ``w0`` first, then smaller ``n_rounds``)."""
    return [ElorSetting(w0, n) for w0 in sorted(spec.w0) for n in sorted(spec.n_rounds)]


def _simplicity(setting: ElorSetting) -> tuple[float, int]:
    return setting.w0, setting.n_rounds


def build_context(inputs: ElorInputs, spec: ElorCv) -> ElorContext:
    first, last = spec.elo_warmup[0], spec.folds[-1]
    games = inputs.games[inputs.games["season"].between(first, last)]
    games = games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    mismatch = unmatched_clubs(inputs.roster, games)
    if mismatch:
        raise ValueError(f"roster club codes do not match the games mart: {mismatch}")
    arrays = elo.prepare(games)
    elo_diff = elo.replay(arrays, spec.elo_params)
    seasons = sorted({int(s) for s in games["season"]})
    starts = season_starts(arrays, spec.elo_params, seasons)
    scales = margin_scales(games, elo_diff)
    appearances = Appearances(games, inputs.player_games)
    priors = newcomer_priors(appearances, inputs.season_end_rating, list(spec.folds))
    missing = [s for s, p in priors.items() if math.isnan(p.rating) or math.isnan(p.share)]
    if missing:
        raise ValueError(f"no newcomer history before seasons {missing}")
    roster = inputs.roster[inputs.roster["season"].isin(spec.folds)].reset_index(drop=True)
    in_folds = games["season"].isin(spec.folds).to_numpy()
    strengths = roster_strengths(
        games[in_folds].reset_index(drop=True),
        roster,
        appearances,
        inputs.rating,
        priors=priors,
        has_state=inputs.has_state,
    )
    offs = offsets(games, strengths, starts, scales, inputs.possessions)
    season = games["season"].astype(int).to_numpy()
    scored = (
        in_folds
        & games["played"].to_numpy(dtype=bool)
        & ~games["forfeit"].to_numpy(dtype=bool)
        & ~games["neutral"].to_numpy(dtype=bool)
    )
    margin = (games["home_score"] - games["away_score"]).fillna(0).to_numpy(dtype=np.float64)
    return ElorContext(
        games=games,
        season=season,
        rounds=round_index(games),
        elo_diff=elo_diff,
        offsets=offs,
        strengths=strengths,
        scored=scored,
        home_won=(margin > 0).astype(np.float64),
        appearances=appearances,
        scales=scales,
        priors=priors,
    )


def _brier(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    out: np.ndarray = (p - y) ** 2
    return out


def _metrics(p: np.ndarray, ctx: ElorContext, folds: tuple[int, ...]) -> dict[str, Any]:
    mask = ctx.scored
    loss = per_game_log_loss(p[mask], ctx.home_won[mask])
    brier = _brier(p[mask], ctx.home_won[mask])
    season = ctx.season[mask]
    per_season = {
        str(s): {
            "games": int((season == s).sum()),
            "log_loss": round6(loss[season == s].mean()),
            "brier": round6(brier[season == s].mean()),
        }
        for s in folds
        if (season == s).any()
    }
    return {
        "log_loss": round6(loss.mean()),
        "brier": round6(brier.mean()),
        "per_season": per_season,
    }


def season_draws(n_seasons: int, resamples: int, seed: int) -> np.ndarray:
    """The whole-season resamples (``cluster_bootstrap_ci``'s draw for the same seed)."""
    draw: np.ndarray = np.random.default_rng(seed).integers(
        0, n_seasons, size=(resamples, n_seasons)
    )
    return draw


def bootstrap_gap_sd(gap: np.ndarray, cluster: np.ndarray, draw: np.ndarray) -> float:
    """SD (ddof 1) of the game-weighted pooled mean of ``gap`` over the season resamples."""
    sums = np.bincount(cluster, weights=gap)
    counts = np.bincount(cluster).astype(np.float64)
    means = sums[draw].sum(axis=1) / counts[draw].sum(axis=1)
    return float(np.std(means, ddof=1))


def select(
    losses: dict[str, float], se: dict[str, float], settings: list[ElorSetting]
) -> ElorSetting:
    """One-SE rule: the simplest setting whose gap to the best is at most its own SE."""
    best = min(losses.values())
    within = [s for s in settings if losses[s.key()] - best <= se[s.key()] + 1e-15]
    return min(within, key=lambda s: (*_simplicity(s), losses[s.key()]))


def run_cv(
    inputs: ElorInputs, *, spec: ElorCv, git_head: str
) -> tuple[dict[str, Any], pd.DataFrame]:
    ctx = build_context(inputs, spec)
    settings = grid_settings(spec)
    p_elo = win_probabilities(ctx.elo_diff)
    probs = {
        s.key(): win_probabilities(elor_diff(ctx.elo_diff, ctx.rounds, ctx.offsets, s))
        for s in settings
    }
    mask = ctx.scored
    y = ctx.home_won[mask]
    cluster = pd.factorize(ctx.season[mask], sort=True)[0].astype(np.int64)
    draw = season_draws(int(cluster.max()) + 1, spec.bootstrap_resamples, spec.bootstrap_seed)
    loss = {k: per_game_log_loss(p[mask], y) for k, p in probs.items()}
    pooled = {k: float(v.mean()) for k, v in loss.items()}
    best_key = min(pooled, key=lambda k: pooled[k])
    se = {k: bootstrap_gap_sd(loss[k] - loss[best_key], cluster, draw) for k in loss}
    selected = select(pooled, se, settings)
    within = [
        s.key() for s in settings if pooled[s.key()] - pooled[best_key] <= se[s.key()] + 1e-15
    ]
    elo_loss = per_game_log_loss(p_elo[mask], y)
    gap = loss[selected.key()] - elo_loss
    mean, low, high = cluster_bootstrap_ci(
        gap, cluster, spec.bootstrap_resamples, spec.bootstrap_seed
    )
    margin = spec.shadow_log_loss_margin
    criteria = {
        "below_elo": bool(pooled[selected.key()] < float(elo_loss.mean())),
        "non_inferior": bool(high < margin),
        "worth_a_version": bool(mean <= -margin),
    }
    report: dict[str, Any] = {
        "model": "elor",
        "protocol": spec.protocol,
        "git_head": git_head,
        "first_round_rule": FIRST_ROUND_RULE,
        "newcomer_priors": priors_report(ctx.priors),
        "elo_params": asdict(spec.elo_params),
        "folds": list(spec.folds),
        "elo_warmup": list(spec.elo_warmup),
        "simplicity_order": [s.key() for s in settings],
        "bootstrap": {"resamples": spec.bootstrap_resamples, "seed": spec.bootstrap_seed},
        "scored_games": int(mask.sum()),
        "per_fold_games": per_fold_games(ctx, spec),
        "prior_available_games": int((mask & ctx.offsets.available).sum()),
        "elo": _metrics(p_elo, ctx, spec.folds),
        "settings": {s.key(): _metrics(probs[s.key()], ctx, spec.folds) for s in settings},
        "best": best_key,
        "se_log_loss_gap_to_best": {k: round6(v) for k, v in se.items()},
        "log_loss_gap_to_best": {k: round6(pooled[k] - pooled[best_key]) for k in pooled},
        "within_one_se": within,
        "settings_within_one_se": len(within),
        "selected": {**asdict(selected), "key": selected.key()},
        "one_se_band": {
            "best_log_loss": round6(pooled[best_key]),
            "selected_log_loss": round6(pooled[selected.key()]),
            "selected_gap_to_best": round6(pooled[selected.key()] - pooled[best_key]),
            "selected_se": round6(se[selected.key()]),
        },
        "selected_minus_elo": {
            "mean": round6(mean),
            "ci95": [round6(low), round6(high)],
            "superior": bool(high < 0.0),
        },
        "shadow_criteria": {**criteria, "all": all(criteria.values())},
    }
    detail = ctx.games.loc[mask, ["game_id", "season", "home", "away"]].copy()
    detail["round_index"] = ctx.rounds[mask]
    detail["home_won"] = y.astype(int)
    detail["prior_available"] = ctx.offsets.available[mask]
    detail["p_elo"] = np.round(p_elo[mask], 6)
    for key, p in probs.items():
        detail[f"p_{key}"] = np.round(p[mask], 6)
    return report, detail.reset_index(drop=True)


def per_fold_games(ctx: ElorContext, spec: ElorCv) -> dict[str, int]:
    return {str(s): int((ctx.scored & (ctx.season == s)).sum()) for s in spec.folds}


def roster_coverage(ctx: ElorContext, spec: ElorCv) -> dict[str, Any]:
    """Scored games where both sides have at least ``spec.min_rostered`` rostered players, and
    the share of rostered player slots (both sides of scored games) without a projected share
    or without an M3 rating."""
    cutoffs = round_cutoffs(ctx.games).to_numpy(dtype=np.float64)
    table = {
        (int(s), float(c), str(t)): (int(k), int(w), int(u))
        for s, c, t, k, w, u in zip(
            ctx.strengths["season"],
            ctx.strengths["cutoff"],
            ctx.strengths["club"],
            ctx.strengths["rostered"],
            ctx.strengths["share_prior"],
            ctx.strengths["rating_prior"],
            strict=True,
        )
    }
    both = 0
    slots = share_prior = rating_prior = 0
    idx = np.flatnonzero(ctx.scored)
    homes = ctx.games["home"].astype(str).to_numpy()
    aways = ctx.games["away"].astype(str).to_numpy()
    for i in idx:
        key = (int(ctx.season[i]), float(cutoffs[i]))
        sides = [table.get((*key, team)) for team in (homes[i], aways[i])]
        if all(v is not None and v[0] >= spec.min_rostered for v in sides):
            both += 1
        for v in sides:
            if v is not None:
                slots += v[0]
                share_prior += v[1]
                rating_prior += v[2]
    n = len(idx)
    return {
        "scored_games": n,
        "min_rostered": spec.min_rostered,
        "both_sides_min_rostered": both,
        "both_sides_min_rostered_share": round6(both / n) if n else math.nan,
        "rostered_slots": slots,
        "share_prior_slots": share_prior,
        "share_prior_slots_share": round6(share_prior / slots) if slots else math.nan,
        "rating_prior_slots": rating_prior,
        "rating_prior_slots_share": round6(rating_prior / slots) if slots else math.nan,
        "prior_available_games": int((ctx.scored & ctx.offsets.available).sum()),
    }


def _played_before(rows: pd.DataFrame, season: int, appearances: Appearances) -> int:
    """Roster rows whose player already had seconds for that club that season before his stamp."""
    count = 0
    for club, player, start in zip(rows["club"], rows["player_id"], rows["start"], strict=True):
        found = appearances.player.get(str(player))
        if found is None:
            continue
        times, teams, seas = found
        hit = (times < start) & (np.asarray(teams) == club) & (seas == season)
        count += int(hit.any())
    return count


def first_round_stamps(
    roster: pd.DataFrame, games: pd.DataFrame, appearances: Appearances, seasons: tuple[int, ...]
) -> dict[str, dict[str, int]]:
    """``roster.start_date_counts`` per season, plus how many stamped rows (during round 1, and
    after it) belong to a player who had already played for that club that season before his
    stamp (a stamp lagging the real signing)."""
    counts = start_date_counts(roster[roster["season"].isin(seasons)], games)
    rounds = season_rounds(games)
    for season in seasons:
        key = str(season)
        if key not in counts:
            continue
        part = roster[roster["season"] == season]
        first, second = rounds.first[season], rounds.second[season]
        during = part[(part["start"] >= first) & (part["start"] < second)]
        after = part[part["start"] >= second]
        counts[key]["start_during_round1_played_before_stamp"] = _played_before(
            during, season, appearances
        )
        counts[key]["start_after_round1_played_before_stamp"] = _played_before(
            after, season, appearances
        )
    return counts


def prior_summary(ctx: ElorContext, spec: ElorCv) -> dict[str, Any]:
    """Outcome-free sanity numbers: each fold's margin scale (Elo points per point of margin,
    fitted on earlier seasons) and the spread of the round-1 roster offsets ``off_t``."""
    first = ctx.scored & (ctx.rounds == 1) & ctx.offsets.available
    offs = np.concatenate([ctx.offsets.home[first], ctx.offsets.away[first]])
    return {
        "margin_scale": {str(s): round6(ctx.scales[s]) for s in spec.folds if s in ctx.scales},
        "round1_offset_sd": round6(float(np.std(offs))) if len(offs) else math.nan,
        "round1_offset_abs_max": round6(float(np.abs(offs).max())) if len(offs) else math.nan,
    }


def priors_report(priors: dict[int, NewcomerPrior]) -> dict[str, dict[str, Any]]:
    return {
        str(s): {
            "rating": round6(p.rating),
            "anchor": round6(p.anchor),
            "gap": round6(p.gap),
            "all_mean": {str(k): round6(v) for k, v in sorted(p.all_mean.items())},
            "share": round6(p.share),
            "rating_players": p.rating_players,
            "rating_seconds": round6(p.rating_seconds),
            "share_player_games": p.share_player_games,
            "history": [p.history[0], p.history[-1]] if p.history else [],
        }
        for s, p in sorted(priors.items())
    }


def cv_check(
    inputs: ElorInputs,
    *,
    spec: ElorCv,
    live_priors: dict[int, NewcomerPrior] | None = None,
) -> dict[str, Any]:
    """Read-only inputs check: game counts per fold, roster coverage and the start-date counts
    the protocol asks for before any fold is scored. Scores nothing."""
    ctx = build_context(inputs, spec)
    in_folds = ctx.games[ctx.games["season"].isin(spec.folds)]
    return {
        "first_round_rule": FIRST_ROUND_RULE,
        "newcomer_priors": priors_report(ctx.priors),
        "newcomer_priors_live": priors_report(live_priors or {}),
        "scored_games": int(ctx.scored.sum()),
        "per_fold_games": per_fold_games(ctx, spec),
        "roster_coverage": roster_coverage(ctx, spec),
        "prior": prior_summary(ctx, spec),
        "start_dates": first_round_stamps(inputs.roster, in_folds, ctx.appearances, spec.folds),
    }
