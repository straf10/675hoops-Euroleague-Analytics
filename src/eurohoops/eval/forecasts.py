"""Season forecast record: every model's provable calls, scored per model, per round and per game.

The site's Forecasts view reads this. A model's calls are the earliest row per game that was
stamped before tip-off and public before it (the scorecard's own ``not_provable`` rule), joined
with the game's result. There is no backfill: a model has entries only for the games it logged,
so it is compared on its own games, and again on the games every compared model logged.
Codes here are the source's; the site shows display codes (``publish.py``).
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval.backtest import TunedModel
from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.eval.scorecard import latest_per_model_game, not_provable, read_log
from eurohoops.logs import TIME_FORMAT

REGULAR_SEASON = "RS"
WITHIN_POINTS = (5, 10)  # margin error bands, in points
MARKET_LABEL = "Bookmakers"
_NUMERIC = ("p_home", "exp_margin", "exp_total")


def _provable(log: pd.DataFrame, manual_pushes: Sequence[datetime]) -> pd.DataFrame:
    """The pre-registered row per game: the latest provable row stamped before its tip-off, of the
    earliest model version that logged the game (``latest_per_model_game``)."""
    valid = log[
        pd.to_datetime(log["predicted_at_utc"], utc=True)
        < pd.to_datetime(log["tipoff_utc"], utc=True)
    ]
    kept = valid[~not_provable(valid, manual_pushes)]
    latest = latest_per_model_game(kept)
    return latest.sort_values("predicted_at_utc").drop_duplicates("game_id", keep="first")


def _finished(games: pd.DataFrame, season: int) -> pd.DataFrame:
    return games.loc[
        games["played"] & ~games["forfeit"] & (games["season"] == season),
        [
            "game_id",
            "round",
            "phase",
            "tipoff_utc",
            "home",
            "away",
            "home_score",
            "away_score",
            "neutral",
        ],
    ]


def _calls(
    log_path: Path, games: pd.DataFrame, season: int, manual_pushes: Sequence[datetime]
) -> tuple[pd.DataFrame, int | None]:
    """A model's scored games (with the model's columns) and its first logged round."""
    log = read_log(log_path)
    if "exp_total" not in log.columns:
        log = log.assign(exp_total=np.nan)
    rows = _provable(log, manual_pushes)
    rows = rows[rows["season"] == season]
    first_round = int(rows["round"].min()) if len(rows) else None
    finished = _finished(games, season)
    scored = rows[["game_id", *_NUMERIC]].astype(dict.fromkeys(_NUMERIC, "float64"))
    scored = scored.merge(finished, on="game_id")
    scored = scored.assign(margin=(scored["home_score"] - scored["away_score"]).astype("float64"))
    return scored.sort_values(["tipoff_utc", "game_id"], ignore_index=True), first_round


def _market_calls(odds_path: Path, games: pd.DataFrame, season: int) -> pd.DataFrame:
    """The bookmakers' closing line per finished game: the last fetch stamped before tip-off.

    ``p_home`` is the median de-vigged probability of the books (``odds.py``). A game with no
    fetch before tip-off, or no odds row at all, has no call. ``exp_margin`` is not a market
    quantity and stays NaN.
    """
    if not odds_path.exists():
        return _market_empty()
    odds = pd.read_csv(odds_path, dtype={"game_id": str})
    odds = odds[(odds["season"] == season) & odds["p_home"].notna()]
    before = pd.to_datetime(odds["fetched_at_utc"], utc=True) < pd.to_datetime(
        odds["tipoff_utc"], utc=True
    )
    closing = (
        odds[before]
        .sort_values("fetched_at_utc")
        .drop_duplicates("game_id", keep="last")[["game_id", "p_home"]]
    )
    scored = closing.astype({"p_home": "float64"}).merge(_finished(games, season), on="game_id")
    scored = scored.assign(
        margin=(scored["home_score"] - scored["away_score"]).astype("float64"),
        exp_margin=np.nan,
        exp_total=np.nan,
    )
    return scored.sort_values(["tipoff_utc", "game_id"], ignore_index=True)


def _market_empty() -> pd.DataFrame:
    cols = ["game_id", "p_home", "exp_margin", "exp_total", "margin", "round", "phase"]
    return pd.DataFrame(columns=[*cols, "tipoff_utc", "home_score", "away_score"])


def _pick_right(p_home: pd.Series, margin: pd.Series) -> pd.Series:
    """True/False for a pick; None where p_home is 0.5 (no pick)."""
    right = pd.Series(np.where(p_home > 0.5, margin > 0, margin < 0), index=p_home.index)
    return right.astype(object).where(p_home != 0.5, None)


def _round(x: float, digits: int = 6) -> float:
    return round(float(x), digits)


def metrics(calls: pd.DataFrame) -> dict[str, Any]:
    """The season-scorecard metrics of one model's scored games."""
    n = len(calls)
    out: dict[str, Any] = {
        "n": n,
        "picks": 0,
        "right": 0,
        "right_pct": None,
        "log_loss": None,
        "brier": None,
        "margin_mae": None,
        "within": {str(w): None for w in WITHIN_POINTS},
        "totals_mae": None,
    }
    if not n:
        return out
    p = calls["p_home"].to_numpy(dtype=np.float64)
    margin = calls["margin"].to_numpy(dtype=np.float64)
    home_won = (margin > 0).astype(np.float64)
    picked = p != 0.5
    right = int((((p > 0.5) == (margin > 0)) & picked).sum())
    error = np.abs(calls["exp_margin"].to_numpy(dtype=np.float64) - margin)
    out |= {
        "picks": int(picked.sum()),
        "right": right,
        "right_pct": _round(right / picked.sum()) if picked.any() else None,
        "log_loss": _round(per_game_log_loss(p, home_won).mean()),
        "brier": _round(np.mean((p - home_won) ** 2)),
        "margin_mae": _round(error.mean()),
        "within": {str(w): _round((error <= w).mean()) for w in WITHIN_POINTS},
    }
    if calls["exp_total"].notna().any():
        total = (calls["home_score"] + calls["away_score"]).to_numpy(dtype=np.float64)
        out["totals_mae"] = _round(
            np.abs(calls["exp_total"].to_numpy(dtype=np.float64) - total).mean()
        )
    return out


def _headline(calls: pd.DataFrame) -> dict[str, Any]:
    """Hit rate, Brier and log loss of the calls: what the page compares with the bookmakers."""
    m = metrics(calls.assign(exp_margin=0.0))
    return {k: m[k] for k in ("n", "picks", "right", "right_pct", "brier", "log_loss")}


def _accuracy(model: pd.DataFrame, market: pd.DataFrame) -> list[dict[str, Any]]:
    """Per round, the published model and the bookmakers on the games both called.

    ``to_date`` is the same pair over every group up to and including this one. Regular-season
    games group by round, each postseason phase is one group, in order of first tip-off.
    """
    both = model.merge(market[["game_id", "p_home"]], on="game_id", suffixes=("", "_market"))
    if both.empty:
        return []
    ours = both.drop(columns="p_home_market")
    theirs = both.assign(p_home=both["p_home_market"]).drop(columns="p_home_market")
    keys = [_group_key(p, int(r)) for p, r in zip(both["phase"], both["round"], strict=True)]
    both = both.assign(group=pd.Series(keys, index=both.index, dtype=object))
    order = list(both.groupby("group")["tipoff_utc"].min().sort_values().index)
    out = []
    for i, group in enumerate(order):
        here = (both["group"] == group).to_numpy()
        so_far = both["group"].isin(order[: i + 1]).to_numpy()
        out.append(
            {
                "phase": group[0],
                "round": group[1],
                "games": int(here.sum()),
                "model": _headline(ours[here]),
                "market": _headline(theirs[here]),
                "to_date": {
                    "model": _headline(ours[so_far]),
                    "market": _headline(theirs[so_far]),
                    "games": int(so_far.sum()),
                },
            }
        )
    return out


def _group_key(phase: str, rnd: int) -> tuple[str, int | None]:
    """Regular-season games group by round number; each postseason phase is one group."""
    return (phase, rnd) if phase == REGULAR_SEASON else (phase, None)


def _rounds(
    per_model: Mapping[str, pd.DataFrame], labels: Mapping[str, str]
) -> list[dict[str, Any]]:
    frames = [c.assign(model=key) for key, c in per_model.items() if len(c)]
    if not frames:
        return []
    allc = pd.concat(frames, ignore_index=True)
    allc["group"] = [
        _group_key(p, int(r)) for p, r in zip(allc["phase"], allc["round"], strict=True)
    ]
    first_tip = allc.groupby("group")["tipoff_utc"].min().sort_values()
    out = []
    for group in first_tip.index:
        phase, rnd = group
        rows = allc[allc["group"] == group]
        out.append(
            {
                "phase": phase,
                "round": rnd,
                "games": int(rows["game_id"].nunique()),
                "models": {
                    key: metrics(rows[rows["model"] == key])
                    for key in labels
                    if (rows["model"] == key).any()
                },
            }
        )
    return out


def _games_list(per_model: Mapping[str, pd.DataFrame]) -> list[dict[str, Any]]:
    frames = []
    for key, calls in per_model.items():
        if len(calls):
            frames.append(
                calls.assign(model=key, right=_pick_right(calls["p_home"], calls["margin"]))
            )
    if not frames:
        return []
    allc = pd.concat(frames, ignore_index=True)
    out = []
    for game_id, rows in allc.groupby("game_id", sort=False):
        g = rows.iloc[0]
        out.append(
            {
                "game_id": str(game_id),
                "round": int(g["round"]),
                "phase": str(g["phase"]),
                "tipoff_utc": g["tipoff_utc"].strftime(TIME_FORMAT),
                "home": str(g["home"]),
                "away": str(g["away"]),
                "home_score": int(g["home_score"]),
                "away_score": int(g["away_score"]),
                "models": {
                    str(r["model"]): {
                        "p_home": float(r["p_home"]),
                        "exp_margin": float(r["exp_margin"]),
                        "right": None if r["right"] is None else bool(r["right"]),
                    }
                    for r in rows.to_dict("records")
                },
            }
        )
    out.sort(key=lambda g: (g["tipoff_utc"], g["game_id"]), reverse=True)
    return out


CALIBRATION_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)  # five equal-width bins; the last one closed
WILSON_Z = 1.959963984540054  # 95% interval


def _wilson(k: int, n: int) -> tuple[float, float]:
    """The Wilson score interval of ``k`` home wins in ``n`` games, at 95%."""
    p = k / n
    z2 = WILSON_Z**2
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = WILSON_Z * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return _round(max(0.0, centre - half)), _round(min(1.0, centre + half))


def calibration(calls: pd.DataFrame) -> dict[str, Any]:
    """Reliability of the model's P(home win): observed home-win rate per bin of predicted P.

    Bins are half-open ``[lo, hi)`` except the last, which takes 1.0. Empty bins are dropped.
    """
    p = calls["p_home"].to_numpy(dtype=np.float64)
    home_won = (calls["margin"].to_numpy(dtype=np.float64) > 0).astype(np.float64)
    which = np.searchsorted(np.asarray(CALIBRATION_EDGES[1:-1]), p, side="right")
    bins = []
    for k in range(len(CALIBRATION_EDGES) - 1):
        here = which == k
        n = int(here.sum())
        if not n:
            continue
        low, high = _wilson(int(home_won[here].sum()), n)
        bins.append(
            {
                "lo": CALIBRATION_EDGES[k],
                "hi": CALIBRATION_EDGES[k + 1],
                "n": n,
                "predicted": _round(p[here].mean(), 4),
                "observed": _round(home_won[here].mean(), 4),
                "low": low,
                "high": high,
            }
        )
    return {"games": len(calls), "bins": bins}


def _group_done(games: pd.DataFrame, season: int, key: tuple[str, int | None]) -> bool:
    """Every game of the round or phase is played or forfeited (none still to play)."""
    phase, rnd = key
    rows = games[(games["season"] == season) & (games["phase"] == phase)]
    if rnd is not None:
        rows = rows[rows["round"] == rnd]
    return bool(len(rows)) and bool((rows["played"] | rows["forfeit"]).all())


def round_headline(
    calls: pd.DataFrame, games: pd.DataFrame, season: int, baseline: TunedModel
) -> dict[str, Any] | None:
    """The latest completed round (or phase) of the published model, against the home-win baseline.

    ``called`` counts the games whose side with P > 0.5 won; a game at exactly 0.5 is not called
    but stays in ``games``. ``baseline_brier`` is B0 (the constant home-win rate) on the same games.
    ``biggest_miss`` is the winner the model gave the lowest pre-game probability.
    """
    if calls.empty:
        return None
    keys = [_group_key(p, int(r)) for p, r in zip(calls["phase"], calls["round"], strict=True)]
    # Calls are in tip-off order, so the order of first appearance is the order of the groups.
    done = [key for key in dict.fromkeys(keys) if _group_done(games, season, key)]
    if not done:
        return None
    group = done[-1]
    rows = calls[[key == group for key in keys]]
    p = rows["p_home"].to_numpy(dtype=np.float64)
    home_won = (rows["margin"].to_numpy(dtype=np.float64) > 0).astype(np.float64)
    p_b0, _ = baseline.b0(rows["neutral"].to_numpy(dtype=np.float64))
    p_win = np.where(home_won == 1.0, p, 1.0 - p)
    miss = int(np.argmin(p_win))
    home_side = bool(home_won[miss])
    winner, loser = (rows.iloc[miss]["home"], rows.iloc[miss]["away"])
    if not home_side:
        winner, loser = loser, winner
    called = int((((p > 0.5) & (home_won == 1.0)) | ((p < 0.5) & (home_won == 0.0))).sum())
    return {
        "phase": group[0],
        "round": group[1],
        "games": len(rows),
        "called": called,
        "brier": _round(np.mean((p - home_won) ** 2)),
        "baseline_brier": _round(np.mean((p_b0 - home_won) ** 2)),
        "biggest_miss": {
            "winner": str(winner),
            "loser": str(loser),
            "p_winner": _round(p_win[miss], 4),
        },
    }


def build_forecasts(
    logs: Mapping[str, Path | None],
    labels: Mapping[str, str],
    games: pd.DataFrame,
    season: int,
    manual_pushes: Sequence[datetime] = (),
    *,
    odds_log: Path | None = None,
    published: str | None = None,
    baseline: TunedModel | None = None,
) -> dict[str, Any]:
    """The season record of the models in ``logs`` (key -> log path; ``None`` skips a model).

    ``labels`` fixes the models' order and names. Games are newest first; ``shared`` scores
    the models that have scored games on the games all of them logged. ``published`` is the key
    of the model the site leads with (default: the first); ``odds_log`` is the bookmaker log,
    whose closing line is scored beside the published model on the games both called.
    """
    per_model: dict[str, pd.DataFrame] = {}
    first_round: dict[str, int | None] = {}
    for key in labels:
        path = logs.get(key)
        if path is not None:
            per_model[key], first_round[key] = _calls(path, games, season, manual_pushes)
    used = {k: labels[k] for k in per_model}
    active = [k for k, calls in per_model.items() if len(calls)]
    compared = active if len(active) > 1 else []
    shared_ids = (
        set.intersection(*(set(per_model[k]["game_id"]) for k in compared)) if compared else set()
    )
    lead = published if published in per_model else next(iter(per_model), None)
    market_calls = _market_calls(odds_log, games, season) if odds_log else _market_empty()
    market = (
        {"label": MARKET_LABEL, "season": _headline(market_calls)} if len(market_calls) else None
    )
    shown = per_model[lead] if lead else market_calls.iloc[0:0]
    return {
        "published": lead,
        "market": market,
        "accuracy": _accuracy(shown, market_calls) if market else [],
        "models": [{"key": k, "label": v, "first_round": first_round[k]} for k, v in used.items()],
        "season": [{"model": k, **metrics(per_model[k])} for k in used],
        "shared": {
            "n": len(shared_ids),
            "rows": [
                {"model": k, **metrics(per_model[k][per_model[k]["game_id"].isin(shared_ids)])}
                for k in compared
            ],
        },
        "rounds": _rounds(per_model, used),
        "games": _games_list(per_model),
        "trend": _trend(shown, baseline) if baseline is not None else [],
        "headline": (
            round_headline(shown, games, season, baseline) if baseline is not None else None
        ),
        "calibration": calibration(shown),
    }


def _trend(calls: pd.DataFrame, baseline: TunedModel) -> list[dict[str, Any]]:
    """Per game in tip-off order, the published model's running log-loss edge over the baseline
    (B0: the home-win rate). The edge is the baseline's loss minus the model's, summed, so positive
    means the model is better. The points comparison is read from the games themselves.
    """
    if calls.empty:
        return []
    p_b0, _ = baseline.b0(calls["neutral"].to_numpy(dtype=np.float64))
    margin = calls["margin"].to_numpy(dtype=np.float64)
    home_won = (margin > 0).astype(np.float64)
    loss_model = per_game_log_loss(calls["p_home"].to_numpy(dtype=np.float64), home_won)
    loss_base = per_game_log_loss(p_b0, home_won)
    edge = np.cumsum(loss_base - loss_model)
    labels = (
        calls["home"].astype(str)
        + " "
        + calls["home_score"].astype(int).astype(str)
        + "-"
        + calls["away_score"].astype(int).astype(str)
        + " "
        + calls["away"].astype(str)
    )
    return [
        {"n": i + 1, "label": label, "logloss": {"baseline": round(float(e), 3)}}
        for i, (label, e) in enumerate(zip(labels, edge, strict=True))
    ]
