"""Live ELOC (EuroLeague only): an append-only pre-tip-off shadow log of logistically recalibrated
Elo (docs/models/elo_calibrated.md), next to (never in) the Elo log.

ELOC is logged only when ``ELOC_LIVE_ENABLED`` is set in ``config.py`` (off by default) and the
one-shot CV report (``reports/eloc_cv.json``) says every shadow criterion passed. The ``(a, b)``
are that report's frozen ``live_fit``. Elo is replayed from the CV's first warm-up season with the
same fixed parameters, as the CV did. The shadow is not displayed on the site.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.config import ELOC_LIVE_ENABLED, Competition
from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.models import elo
from eurohoops.models.elo import EloParams
from eurohoops.models.elo_cal import Calibration, apply
from eurohoops.models.elor import margin_scales
from eurohoops.predict import LOG_COLUMNS, logged_keys, refuse_late, upcoming_games

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveEloc:
    calibration: Calibration  # the frozen live fit: a, b
    elo_params: EloParams
    first_season: int  # the Elo replay's first season (the CV's first warm-up season)
    version: str
    passed: bool  # every shadow criterion of the CV report


def eloc_logging_on(comp: Competition) -> bool:
    """The ELOC shadow log is written only when the owner has enabled it in ``config.py``."""
    return ELOC_LIVE_ENABLED and comp.eloc_prediction_log is not None


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
    digest = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()[:8]
    return LiveEloc(
        calibration=Calibration(
            float(live["a"]), float(live["b"]), int(live["games"]), int(live["iterations"])
        ),
        elo_params=EloParams(**report["elo_params"]),
        first_season=int(report["elo_warmup"][0]),
        version=f"{version('eurohoops')}+eloc.{digest}",
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
    window: timedelta,
    clock: Callable[[], datetime],
) -> int:
    """Log confirmed, unplayed ``season`` games within ``window`` that are not logged at this
    model version yet. Returns the rows added. Nothing is logged unless the CV passed."""
    if not model.passed:
        log.info("ELOC did not pass its shadow criteria: not logged")
        return 0
    now = clock()
    upcoming = upcoming_games(games, season, now, window)
    logged = logged_keys(log_path)
    fresh = np.array([(str(g), model.version) not in logged for g in games["game_id"]], dtype=bool)
    wanted = games[upcoming & fresh]
    if wanted.empty:
        return 0
    fc = {str(f["game_id"]): f for f in eloc_forecasts(games, model, season).to_dict("records")}
    rows_in = wanted.to_dict("records")
    ok = [
        (r, fc[str(r["game_id"])])
        for r in rows_in
        if str(r["game_id"]) in fc
        and np.isfinite(fc[str(r["game_id"])]["p_home"])
        and np.isfinite(fc[str(r["game_id"])]["exp_margin"])
    ]
    if len(ok) < len(rows_in):
        log.warning("ELOC: %d upcoming games have no forecast", len(rows_in) - len(ok))
    predicted_at = clock()
    refuse_late(predicted_at, [(r["game_id"], r["tipoff_utc"]) for r, _ in ok])
    rows = [
        {
            "game_id": r["game_id"],
            "season": r["season"],
            "round": r["round"],
            "phase": r["phase"],
            "tipoff_utc": r["tipoff_utc"].strftime(TIME_FORMAT),
            "home": r["home"],
            "away": r["away"],
            "p_home": f"{float(f['p_home']):.4f}",
            "exp_margin": f"{float(f['exp_margin']):.2f}",
            "model": "eloc",
            "model_version": model.version,
            "predicted_at_utc": predicted_at.strftime(TIME_FORMAT),
        }
        for r, f in ok
    ]
    append_rows(log_path, LOG_COLUMNS, rows)
    log.info("ELOC: %d rows appended to %s", len(rows), log_path)
    return len(rows)
