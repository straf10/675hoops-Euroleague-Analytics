"""Live ELOC (EuroLeague only): an append-only pre-tip-off shadow log of logistically recalibrated
Elo (docs/models/elo_calibrated.md), next to (never in) the Elo log.

ELOC is logged only when ``ELOC_LIVE_ENABLED`` is set in ``config.py`` (off by default) and the
one-shot CV report (``reports/eloc_cv.json``) says every shadow criterion passed. The ``(a, b)``
are that report's frozen ``live_fit``. Elo is replayed from the CV's first warm-up season with the
same fixed parameters, as the CV did. The shadow is not displayed on the site.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.eval.common import tagged_version
from eurohoops.models import elo
from eurohoops.models.elo import EloParams
from eurohoops.models.elo_cal import Calibration, apply
from eurohoops.models.elor import margin_scales
from eurohoops.predict import LOG_COLUMNS
from eurohoops.shadow_log import append_shadow_log

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveEloc:
    calibration: Calibration  # the frozen live fit: a, b
    elo_params: EloParams
    first_season: int  # the Elo replay's first season (the CV's first warm-up season)
    version: str
    passed: bool  # every shadow criterion of the CV report


def load_eloc(report_path: Path) -> LiveEloc | None:
    """The frozen live fit of the CV report; None when there is no report."""
    if not report_path.exists():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    live = report["live_fit"]
    frozen = {
        "a": float(live["a"]),
        "b": float(live["b"]),
        "elo_params": report["elo_params"],
        "elo_warmup": report["elo_warmup"],
    }
    return LiveEloc(
        calibration=Calibration(
            float(live["a"]), float(live["b"]), int(live["games"]), int(live["iterations"])
        ),
        elo_params=EloParams(**report["elo_params"]),
        first_season=int(report["elo_warmup"][0]),
        version=tagged_version("eloc", json.dumps(frozen, sort_keys=True)),
        passed=report.get("shadow_criteria", {}).get("all") is True,
    )


def eloc_forecasts(games: pd.DataFrame, model: LiveEloc, season: int) -> pd.DataFrame:
    """ELOC's forecast of every ``season`` game: ``game_id``, ``p_home`` and ``exp_margin``.

    Elo's pre-game difference uses only games processed before each game. ``exp_margin`` is that
    difference over the margin scale fitted on earlier seasons (as ELOR's is); it is not scored.
    """
    part = games[games["season"].between(model.first_season, season)]
    part = part.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    diff = elo.replay(elo.prepare(part), model.elo_params)
    live = (part["season"] == season).to_numpy()
    scale = margin_scales(part, diff)[season]
    return pd.DataFrame(
        {
            "game_id": part.loc[live, "game_id"].astype(str).to_numpy(),
            "p_home": apply(model.calibration, diff[live]),
            "exp_margin": diff[live] / scale,
        }
    )


def predict_upcoming_eloc(
    games: pd.DataFrame,
    model: LiveEloc,
    *,
    log_path: Path,
    season: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
) -> int | None:
    """Log confirmed, unplayed ``season`` games of rounds starting within ``round_lead`` that are
    not logged at this model version yet. Returns the rows added. Nothing is logged unless the CV
    passed."""

    def forecast(due: pd.DataFrame) -> dict[str, dict[str, str]]:
        fc = eloc_forecasts(games, model, season).to_dict("records")
        by_game = {str(f["game_id"]): f for f in fc}
        wanted = (by_game.get(g) for g in due["game_id"].astype(str))
        return {
            str(f["game_id"]): {
                "p_home": f"{float(f['p_home']):.4f}",
                "exp_margin": f"{float(f['exp_margin']):.2f}",
            }
            for f in wanted
            if f is not None and np.isfinite(f["p_home"]) and np.isfinite(f["exp_margin"])
        }

    return append_shadow_log(
        games,
        forecast,
        tag="eloc",
        label="ELOC",
        version=model.version,
        columns=LOG_COLUMNS,
        log_path=log_path,
        season=season,
        round_lead=round_lead,
        clock=clock,
        skip_reason=None if model.passed else "ELOC did not pass its shadow criteria: not logged",
    )
