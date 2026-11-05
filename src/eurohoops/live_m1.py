"""Live M1 (E-g): append-only pre-tip-off log of the team model, next to (never in) the Elo log.

M1 goes live only for a competition whose M1 report says the validation gate passed. Its
parameters are the frozen ``tuned`` block of that report (as Elo reads its own report); MLflow
is never read here. Ratings come from the same walk-forward as the backtest, fitted on every
game with box lines from season ``replay_from`` (the live Elo's first warm-up season) that
tipped off before the game's round opened.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.eval.common import gate_passed
from eurohoops.models.elo import FloatArray
from eurohoops.models.team_eff import DecayParams, MarginModel, forecast, prepare_history
from eurohoops.shadow_log import append_shadow_log

M1_LOG_COLUMNS = (
    "game_id",
    "season",
    "round",
    "phase",
    "tipoff_utc",
    "home",
    "away",
    "p_home",
    "exp_margin",
    "exp_total",
    "margin_sigma",
    "margin_df",
    "total_sigma",
    "model",
    "model_version",
    "predicted_at_utc",
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveM1:
    rating: DecayParams
    pace: DecayParams
    margin: MarginModel
    totals_sigma: float
    version: str
    gate_passed: bool


def load_m1(report_path: Path) -> LiveM1 | None:
    """The frozen M1 parameters of a backtest report; None when there is no report."""
    if not report_path.exists():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    tuned, margin = report["tuned"], report["tuned"]["margin"]
    return LiveM1(
        rating=DecayParams(**tuned["rating"]),
        pace=DecayParams(**tuned["pace"]),
        margin=MarginModel(margin["variant"], margin["scale"], margin["df"], margin["ref_pace"]),
        totals_sigma=float(tuned["totals_sigma"]),
        version=str(report["model_version"]),
        gate_passed=gate_passed(report),
    )


@dataclass(frozen=True)
class M1Forecasts:
    games: pd.DataFrame  # the games forecast, tip-off order
    p_home: FloatArray
    margin: FloatArray
    total: FloatArray
    margin_sigma: FloatArray


def m1_forecasts(
    games: pd.DataFrame, team_games: pd.DataFrame, model: LiveM1, replay_from: int
) -> M1Forecasts:
    """Walk-forward M1 forecasts of every game from season ``replay_from`` (NaN: no data yet)."""
    frame = games[games["season"] >= replay_from].reset_index(drop=True)
    result = forecast(prepare_history(frame, team_games), model.rating, model.pace)
    return M1Forecasts(
        games=frame,
        p_home=model.margin.p_home(result.margin, result.pace),
        margin=result.margin,
        total=result.total,
        margin_sigma=model.margin.scales(result.pace),
    )


def forecast_strings(
    *,
    p_home: float,
    margin: float,
    total: float,
    margin_sigma: float,
    margin_df: float | None,
    total_sigma: float,
) -> dict[str, str]:
    """The forecast columns of an M1-shaped log row (M1, M5 and M5-INJ share them), as logged."""
    return {
        "p_home": f"{p_home:.4f}",
        "exp_margin": f"{margin:.2f}",
        "exp_total": f"{total:.2f}",
        "margin_sigma": f"{margin_sigma:.4f}",
        "margin_df": "" if margin_df is None or np.isnan(margin_df) else f"{margin_df:g}",
        "total_sigma": f"{total_sigma:.4f}",
    }


def predict_upcoming_m1(
    games: pd.DataFrame,
    team_games: pd.DataFrame,
    model: LiveM1,
    *,
    log_path: Path,
    season: int,
    replay_from: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
) -> int | None:
    """Like the Elo predictor: confirmed, unplayed ``season`` games of rounds starting within
    ``round_lead`` that are not logged at this model version yet; games without a forecast (no box
    lines) are skipped.
    """

    def forecast(due: pd.DataFrame) -> dict[str, dict[str, str]]:
        fc = m1_forecasts(games, team_games, model, replay_from)
        index = {str(g): i for i, g in enumerate(fc.games["game_id"])}
        wanted = [index[g] for g in due["game_id"].astype(str) if g in index]
        return {
            str(fc.games["game_id"].iloc[i]): forecast_strings(
                p_home=fc.p_home[i],
                margin=fc.margin[i],
                total=fc.total[i],
                margin_sigma=fc.margin_sigma[i],
                margin_df=model.margin.df,
                total_sigma=model.totals_sigma,
            )
            for i in wanted
            if not np.isnan(fc.margin[i])
        }

    return append_shadow_log(
        games,
        forecast,
        tag="m1",
        label="M1",
        version=model.version,
        columns=M1_LOG_COLUMNS,
        log_path=log_path,
        season=season,
        round_lead=round_lead,
        clock=clock,
        skip_reason=None if model.gate_passed else "M1 did not pass its gate: not logged",
    )
