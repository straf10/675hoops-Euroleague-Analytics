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
import json
from collections.abc import Mapping, Sequence
from dataclasses import astuple, dataclass
from pathlib import Path
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


def fit_frozen(
    games: pd.DataFrame, raw_dir: Path, report: Mapping[str, Any]
) -> tuple[Calibrated, pd.DataFrame]:
    """The gate's chosen model, refitted with the gate's code on the training seasons only.

    Returns the model and the games table of the backtest (``p_pre`` is the walk-forward Elo of
    section 4.1 for 2007-2025). Raises if the validation log loss does not reproduce the report.
    """
    chosen = str(report["chosen"]["family"])
    setting = report["chosen"]["gbm_setting"]
    g, train_rows, states = build(games, raw_dir)
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


def wp_lines(
    games: pd.DataFrame, raw_dir: Path, report: Mapping[str, Any], pre_2026: Mapping[str, float]
) -> WpLines:
    """Every game with a usable play-by-play: the historic games with the backtest's walk-forward
    Elo P(home), the live season's games with their logged pre-game P(home)."""
    model, g = fit_frozen(games, raw_dir, report)
    out: dict[str, dict[str, Any]] = {}

    def add(row: Any, pre: float) -> None:
        parsed = _parsed(raw_dir, row)
        if parsed is None:
            return
        home_won = bool(row.home_score > row.away_score)
        line = game_line(parsed, pre, bool(row.neutral), model, home_won)
        if line is not None:
            out[str(row.game_id)] = line

    pres = g["p_pre"].to_numpy(float)
    for pre, row in zip(pres, g.itertuples(index=False), strict=True):
        add(row, float(pre))
    live = games[(games["season"] > LAST_SEASON) & games["played"].astype(bool)]
    for row in live.itertuples(index=False):
        gid = str(row.game_id)
        if gid in pre_2026:
            add(row, pre_2026[gid])
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
