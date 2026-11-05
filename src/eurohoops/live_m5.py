"""Live M5 (EuroLeague only): an append-only pre-tip-off shadow log of the roster-aware predictor,
next to (never in) the Elo and M1 logs.

M5 goes live only if its committed report (``reports/backtest_m5.json``) says the validation gate
passed; its parameters are that report's frozen ``chosen.choice`` (MLflow is never read). The
forecast is the backtest's own: ``m5_backtest.predict_games`` over every game of the competition
with the live season appended to the frame, so each game is forecast with exactly the walk-forward
the backtest scores -- the player part from RAPM fitted on stints that ended before the game's round
opened, the team residual and the rest effect fitted on games that tipped off before it, and the
*projected* roster (the team's recent rotation, ``models.rotation``), never the game's own minutes.
The margin distribution and the totals sigma are fitted on the tuning seasons only, so appending
the live season moves none of them. The live season only enters the frame, not the report's splits.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.config import M5, M5Backtest
from eurohoops.eval.common import gate_passed
from eurohoops.eval.m5_backtest import Choice, M5Inputs, PlayerPartFn, predict_games
from eurohoops.live_m1 import M1_LOG_COLUMNS, forecast_strings
from eurohoops.shadow_log import append_shadow_log

M5_LOG_COLUMNS = M1_LOG_COLUMNS  # the same shape as M1's: M5 needs nothing more

log = logging.getLogger(__name__)

# What a run needs once there is something to forecast: the (heavy) marts, rosters and RAPM.
Build = Callable[[], tuple[M5Inputs, PlayerPartFn]]


@dataclass(frozen=True)
class LiveM5:
    choice: Choice
    version: str
    gate_passed: bool


def load_m5(report_path: Path) -> LiveM5 | None:
    """The frozen M5 choice of a backtest report; None when there is no report."""
    if not report_path.exists():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return LiveM5(
        choice=Choice(**report["chosen"]["choice"]),
        version=str(report["model_version"]),
        gate_passed=gate_passed(report),
    )


def live_spec(spec: M5Backtest, season: int) -> M5Backtest:
    """``spec`` with the live season appended to the test seasons, so the harness frame reaches it.
    The tuning seasons, which fit the margin distribution and the totals sigma, are unchanged."""
    return spec if season <= spec.test[-1] else replace(spec, test=(*spec.test, season))


def m5_forecasts(
    inputs: M5Inputs, model: LiveM5, player_part: PlayerPartFn, spec: M5Backtest, season: int
) -> pd.DataFrame:
    """M5's forecast of every game of the frame: ``predict_games`` under the frozen choice."""
    return predict_games(
        inputs, spec=live_spec(spec, season), player_part=player_part, choice=model.choice
    )


def m5_strings(fc: pd.DataFrame, due: pd.DataFrame) -> dict[str, dict[str, str]]:
    """The logged forecast columns of the ``due`` games found in ``fc`` (indexed by ``game_id``);
    a game without a finite forecast is left out."""
    by_game = fc.to_dict("index")
    out: dict[str, dict[str, str]] = {}
    for game_id in due["game_id"].astype(str):
        f = by_game.get(game_id)
        if f is None or not all(np.isfinite(f[c]) for c in ("p_home", "exp_margin", "exp_total")):
            continue
        out[game_id] = forecast_strings(
            p_home=float(f["p_home"]),
            margin=float(f["exp_margin"]),
            total=float(f["exp_total"]),
            margin_sigma=float(f["margin_sigma"]),
            margin_df=float(f["margin_df"]),
            total_sigma=float(f["total_sigma"]),
        )
    return out


def predict_upcoming_m5(
    games: pd.DataFrame,
    model: LiveM5,
    build: Build,
    *,
    log_path: Path,
    season: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
    spec: M5Backtest = M5,
) -> int | None:
    """Like the M1 predictor: confirmed, unplayed ``season`` games of rounds starting within
    ``round_lead`` that are not logged at this model version yet. ``games`` is the competition's
    games mart; ``build`` makes the harness inputs and the player part, and is called only when
    there is something to log.
    Games without a finite forecast are skipped with a warning."""

    def forecast(due: pd.DataFrame) -> dict[str, dict[str, str]]:
        inputs, player_part = build()
        fc = m5_forecasts(inputs, model, player_part, spec, season).set_index("game_id")
        return m5_strings(fc, due)

    return append_shadow_log(
        games,
        forecast,
        tag="m5",
        label="M5",
        version=model.version,
        columns=M5_LOG_COLUMNS,
        log_path=log_path,
        season=season,
        round_lead=round_lead,
        clock=clock,
        skip_reason=None if model.gate_passed else "M5 did not pass its gate: not logged",
    )
