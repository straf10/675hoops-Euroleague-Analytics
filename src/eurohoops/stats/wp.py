"""In-game win probability for the game pages: the frozen v1 model's line, swings, control parts.

The model is the one the gate reported (docs/models/wp.md, protocol v1;
``reports/backtest_wp.json``). Nothing is refitted to a new choice. The chosen family and GBM
setting come from the report. The fit is the gate's own code (train seasons 2007-2022, the isotonic
map from out-of-fold predictions), and the validation log loss must reproduce the report's value
before any line is written. The fitted model is not saved anywhere, so this is the only way to get
it back.

Per game: the line in home win probability (basis points) from the published pre-game P(home) at
tip-off to the result at the final buzzer, the five biggest swings, and the five game-control parts
of each team (``models/wp_control.py``). Read only: nothing is written under ``data/``.
"""

import gzip
import hashlib
import json
import pickle
from collections.abc import Mapping, Sequence
from dataclasses import astuple, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval.wp_backtest import (
    LAST_SEASON,
    TRAIN,
    VALIDATION,
    _fit,
    _game_file,
    _oof_isotonic,
    _scored,
    _state,
    build,
    checkpoint_states,
)
from eurohoops.models import wp as wpm
from eurohoops.models.wp import Calibrated
from eurohoops.models.wp_control import game_parts, team_view
from eurohoops.parallel import map_ordered, record
from eurohoops.parse.wp_pbp import ParsedGame, parse_game

GRID_SECONDS = 30  # a line point every 30 s of game time, plus every scoring change
TOP_SWINGS = 5
BP = 10_000  # probabilities are stored as basis points
POINT_FIELDS = ("elapsed", "home", "away", "wp")
SWING_FIELDS = ("elapsed", "period", "clock", "home_scored", "code", "home", "away", "delta")
CONTROL_FIELDS = ("dominance", "control", "drama", "comeback", "crunch")
PREDICTED_MODEL = "elo"  # the logged pre-game forecast the chain starts from (wp.md section 7)


@dataclass(frozen=True)
class WpLines:
    version: str  # the frozen model's version string (wp_card.md)
    family: str  # the chosen family, ``logit`` for v1
    games: Mapping[str, Mapping[str, Any]]  # game id -> line, swings and control parts


WP_BUILD_VERSION = "1"  # bump with any change to the build's code (``eval.wp_backtest.build``)
WP_BUILD_CACHE = Path("data/cache/wp_build")


def build_key(games: pd.DataFrame, raw_dir: Path) -> str:
    """Digest of everything ``build`` reads: the code version, the games table and every cached
    play-by-play file (path and bytes), so a new game or a changed file gives a new key."""
    digest = hashlib.sha256(WP_BUILD_VERSION.encode())
    digest.update(repr(list(games.columns)).encode())
    digest.update(pd.util.hash_pandas_object(games, index=True).to_numpy().tobytes())
    for path in sorted((raw_dir / "playbyplay").glob("E*/*.json.gz")):
        digest.update(path.relative_to(raw_dir).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def build_cached(
    games: pd.DataFrame, raw_dir: Path, cache_dir: Path = WP_BUILD_CACHE
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """``eval.wp_backtest.build``, read from ``cache_dir`` when its key matches (see ``build_key``).

    The cache is a local file under ``data/cache``; the build is a pure function of the key's
    inputs, so a hit returns the same frames the build would.
    """
    path = cache_dir / f"{build_key(games, raw_dir)}.pkl"
    if path.exists():
        with path.open("rb") as fh:
            cached: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] = pickle.load(fh)
        return cached
    built = build(games, raw_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as fh:
        pickle.dump(built, fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    return built


def fit_frozen(
    games: pd.DataFrame, raw_dir: Path, report: Mapping[str, Any], cache_dir: Path = WP_BUILD_CACHE
) -> tuple[Calibrated, pd.DataFrame]:
    """The gate's chosen model, refitted with the gate's code on the training seasons only.

    Returns the model and the games table of the backtest (``p_pre`` is the walk-forward Elo of
    section 4.1 for 2007-2025). Raises if the validation log loss does not reproduce the report.
    """
    chosen = str(report["chosen"]["family"])
    setting = report["chosen"]["gbm_setting"]
    g, train_rows, states = build_cached(games, raw_dir, cache_dir)
    s_train = train_rows[train_rows["season"].isin(TRAIN)]
    model = Calibrated(_fit(chosen, setting, s_train), _oof_isotonic(train_rows, chosen, setting))
    ck_val = states[states["season"].isin(VALIDATION)]
    scored = _scored(ck_val, model.predict(*_state(ck_val)))
    got = float(scored.groupby("gid")["ll"].mean().mean())
    expected = float(report["families"][chosen]["calibrated"]["logloss"])
    if abs(got - expected) > 1e-9:
        raise RuntimeError(
            f"frozen WP model does not reproduce the report: validation log loss {got!r}, "
            f"report {expected!r}"
        )
    return model, g


def logged_pre(path: Path) -> dict[str, float]:
    """Game id -> the logged Elo P(home) in force at tip-off (the latest row logged before it)."""
    if not path.exists():
        return {}
    rows = pd.read_csv(path, dtype={"game_id": str})
    rows = rows[
        (rows["model"] == PREDICTED_MODEL) & (rows["predicted_at_utc"] < rows["tipoff_utc"])
    ]
    rows = rows.sort_values("predicted_at_utc", kind="stable")
    pairs = zip(rows["game_id"], rows["p_home"].astype(float), strict=True)
    return {str(gid): float(p) for gid, p in pairs}


def _parsed(raw_dir: Path, row: Any) -> ParsedGame | None:
    """The parsed play-by-play of a game that passes the gate's exclusions (wp.md section 2)."""
    if not bool(row.played) or bool(row.forfeit):
        return None
    path = _game_file(raw_dir, int(row.season), row.game_id)
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        parsed = parse_game(json.load(fh), row.home, row.away)
    if not parsed.code_ok or parsed.bad_clock_events:
        return None
    if (parsed.final_home, parsed.final_away) != (int(row.home_score), int(row.away_score)):
        return None
    return parsed


def _bp(p: float) -> int:
    return round(min(max(p, 0.0), 1.0) * BP)


def game_line(
    parsed: ParsedGame, pre: float, neutral: bool, model: Calibrated, home_won: bool
) -> dict[str, Any] | None:
    """One game's line, swings and control parts (wp.md sections 7 and 8)."""
    rows = parsed.rows
    if not rows:
        return None
    period = np.array([r.period for r in rows], dtype=np.int64)
    ot = np.array([r.ot for r in rows], dtype=np.float64)
    t = np.array([r.t for r in rows], dtype=np.float64)
    clock = np.array([r.clock for r in rows], dtype=np.float64)
    elapsed = np.maximum.accumulate(np.array([r.elapsed for r in rows], dtype=np.float64))
    s_home = np.array([r.s_home for r in rows], dtype=np.int64)
    s_away = np.array([r.s_away for r in rows], dtype=np.int64)
    codes = [r.ptype for r in rows]
    m = (s_home - s_away).astype(np.float64)

    pre = min(max(pre, wpm.PROB_CLIP), 1.0 - wpm.PROB_CLIP)
    logit_pre = float(np.log(pre / (1.0 - pre)))
    neutral_f = float(neutral)

    def model_value(mm: np.ndarray, tt: np.ndarray, oo: np.ndarray) -> np.ndarray:
        k = len(mm)
        raw = model.predict(mm, tt, oo, np.full(k, logit_pre), np.full(k, neutral_f))
        return raw

    tip = float(model_value(np.zeros(1), np.full(1, wpm.GAME_SECONDS), np.zeros(1))[0])
    gap = wpm.tipoff_gap(pre, tip)

    def line(mm: np.ndarray, tt: np.ndarray, oo: np.ndarray) -> np.ndarray:
        return wpm.displayed_wp(model_value(mm, tt, oo), gap, tt, oo)

    wp = line(m, t, ot)
    prev_m = np.concatenate([[0.0], m[:-1]])
    prev_home = np.concatenate([[0], s_home[:-1]])
    prev_away = np.concatenate([[0], s_away[:-1]])
    scored = (s_home != prev_home) | (s_away != prev_away)
    # Section 8: both terms at the play's own clock, so a play with no score change is exactly 0.
    delta = wp - line(prev_m, t, ot)

    # Line: tip-off, every scoring change, a point every GRID_SECONDS, and the result at the end.
    last = float(elapsed[-1])
    grid = np.arange(GRID_SECONDS, last, GRID_SECONDS)
    grid_idx = np.searchsorted(elapsed, grid, side="right") - 1
    keep = set(np.flatnonzero(scored).tolist()) | set(grid_idx.tolist())
    points: list[list[int]] = [[0, 0, 0, _bp(pre)]]
    for i in sorted(keep):
        if i >= 0 and 0 < elapsed[i] < last:
            points.append([int(elapsed[i]), int(s_home[i]), int(s_away[i]), _bp(float(wp[i]))])
    points.append([int(last), int(s_home[-1]), int(s_away[-1]), BP if home_won else 0])

    order = sorted(np.flatnonzero(scored).tolist(), key=lambda i: (-abs(delta[i]), i))
    swings = [
        [
            int(elapsed[i]),
            int(period[i]),
            round(clock[i]),
            int(s_home[i] != prev_home[i]),
            codes[i],
            int(s_home[i]),
            int(s_away[i]),
            round(float(delta[i]) * BP),
        ]
        for i in order[:TOP_SWINGS]
    ]

    ev = pd.DataFrame(
        {
            "period": period,
            "ot": ot.astype(np.int64),
            "t": t,
            "elapsed": elapsed,
            "ptype": codes,
            "m": m,
        }
    )
    ck = checkpoint_states(ev)
    wp_ck = line(ck["m"].to_numpy(float), ck["t"].to_numpy(float), ck["ot"].to_numpy(float))
    regulation = ot == 0
    control = {
        side: [
            round(float(x), 4)
            for x in astuple(game_parts(team_view(wp_ck, side == "home"), delta, t, regulation))
        ]
        for side in ("home", "away")
    }
    overtime_periods = max(int(period.max()) - 4, 0)
    return {
        "pre": _bp(pre),
        "ot": overtime_periods,
        "line": points,
        "swings": swings,
        "control": control,
    }


_MODEL: Calibrated | None = None  # the worker's copy of the fitted model (``_set_model``)


def _set_model(model: Calibrated) -> None:
    """Pool initializer: each worker process keeps the fitted model once, not once per game."""
    global _MODEL  # noqa: PLW0603
    _MODEL = model


def _line_for(item: tuple[Path, SimpleNamespace, float]) -> tuple[str, dict[str, Any] | None]:
    """One game's line (None without a usable play-by-play), for a worker process."""
    raw_dir, row, pre = item
    if _MODEL is None:
        raise RuntimeError("_line_for needs _set_model first")
    parsed = _parsed(raw_dir, row)
    if parsed is None:
        return str(row.game_id), None
    home_won = bool(row.home_score > row.away_score)
    return str(row.game_id), game_line(parsed, pre, bool(row.neutral), _MODEL, home_won)


def wp_lines(
    games: pd.DataFrame, raw_dir: Path, report: Mapping[str, Any], pre_2026: Mapping[str, float]
) -> WpLines:
    """Every game with a usable play-by-play: the historic games with the backtest's walk-forward
    Elo P(home), the live season's games with their logged pre-game P(home)."""
    model, g = fit_frozen(games, raw_dir, report)
    pres = g["p_pre"].to_numpy(float)
    items: list[tuple[Path, SimpleNamespace, float]] = [
        (raw_dir, record(row), float(pre))
        for pre, row in zip(pres, g.to_dict("records"), strict=True)
    ]
    live = games[(games["season"] > LAST_SEASON) & games["played"].astype(bool)]
    items += [
        (raw_dir, record(row), pre_2026[str(row["game_id"])])
        for row in live.to_dict("records")
        if str(row["game_id"]) in pre_2026
    ]
    # the per-game lines are computed in worker processes; results keep the order of ``items``
    lines = map_ordered(_line_for, items, initializer=_set_model, initargs=(model,))
    out = {gid: line for gid, line in lines if line is not None}
    return WpLines(
        version=str(report["version"]), family=str(report["chosen"]["family"]), games=out
    )


def wp_payload(season: int, game_ids: Sequence[str], lines: WpLines) -> dict[str, Any]:
    """``seasons/{season}/wp.json``: the played games of ``game_ids`` with a line, in id order."""
    return {
        "season": season,
        "version": lines.version,
        "model": lines.family,
        "units": "basis points of home win probability (10000 = 100%); elapsed in game seconds",
        "grid_seconds": GRID_SECONDS,
        "point_fields": list(POINT_FIELDS),
        "swing_fields": list(SWING_FIELDS),
        "control_fields": list(CONTROL_FIELDS),
        "games": {gid: lines.games[gid] for gid in sorted(game_ids) if gid in lines.games},
    }
