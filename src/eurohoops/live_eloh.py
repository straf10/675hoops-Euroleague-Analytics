"""Live ELOH (EuroLeague only): an append-only pre-tip-off shadow log of Elo with a per-team home
advantage (experiments/eloh.md), next to (never in) the Elo log.

The forecast is live Elo's (same parameters, same margin scale, same replay start) with the
home-court advantage of a game set to ``hca + delta[home team]``. The deltas are the frozen fit in
``reports/eloh_fit.json``; nothing here refits them. The shadow is not displayed on the site.

It is logged only when ``ELOH_LIVE_ENABLED`` is set in ``config.py`` (off by default).
"""

import hashlib
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.eval.backtest import TunedModel
from eurohoops.inputs import elo_strings
from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.models import elo
from eurohoops.models.elo import EloParams
from eurohoops.models.eloh import load_deltas
from eurohoops.predict import LOG_COLUMNS, logged_keys, refuse_late, upcoming_games

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveEloh:
    params: EloParams  # live Elo's parameters; its hca is the base each team's delta adds to
    margin_scale: float  # live Elo's margin scale, unchanged
    deltas: Mapping[str, float]  # δ per source team code, Elo points; a missing team is 0
    first_season: int  # the Elo replay's first season (live Elo's first warm-up season)
    version: str


def load_eloh(fit_path: Path, tuned: TunedModel, first_season: int) -> LiveEloh | None:
    """The frozen fit with live Elo's settings; None when there is no fit file yet."""
    if not fit_path.exists():
        return None
    digest = hashlib.sha256(fit_path.read_bytes()).hexdigest()[:8]
    return LiveEloh(
        params=tuned.params,
        margin_scale=tuned.margin_scale,
        deltas=load_deltas(fit_path),
        first_season=first_season,
        version=f"{version('eurohoops')}+eloh.{digest}",
    )


def eloh_hca(games: pd.DataFrame, model: LiveEloh) -> np.ndarray:
    """Each game's home-court advantage: ``hca`` plus the home team's delta (neutral games get 0
    from ``replay``, as in Elo)."""
    shift = games["home"].astype(str).map(model.deltas).fillna(0.0).to_numpy(dtype=np.float64)
    return model.params.hca + shift


def eloh_forecasts(games: pd.DataFrame, model: LiveEloh, season: int) -> pd.DataFrame:
    """ELOH's forecast of every ``season`` game: ``game_id``, ``p_home`` and ``exp_margin`` as the
    Elo log formats them.

    Ratings use only games processed before each game (``replay``), so a forecast cannot see its
    own result or anything later.
    """
    part = games[games["season"].between(model.first_season, season)]
    part = part.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    diff = elo.replay(elo.prepare(part), model.params, eloh_hca(part, model))
    live = (part["season"] == season).to_numpy()
    strings = [elo_strings(float(d), model.margin_scale) for d in diff[live]]
    return pd.DataFrame(
        {
            "game_id": part.loc[live, "game_id"].astype(str).to_numpy(),
            "p_home": [p for p, _ in strings],
            "exp_margin": [m for _, m in strings],
        }
    )


def predict_upcoming_eloh(
    games: pd.DataFrame,
    model: LiveEloh,
    *,
    log_path: Path,
    season: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
) -> int:
    """Log confirmed, unplayed ``season`` games of rounds starting within ``round_lead`` that are
    not logged at this model version yet. Returns the rows added."""
    now = clock()
    upcoming = upcoming_games(games, season, now, round_lead)
    logged = logged_keys(log_path)
    fresh = np.array([(str(g), model.version) not in logged for g in games["game_id"]], dtype=bool)
    wanted = games[upcoming & fresh]
    if wanted.empty:
        return 0
    fc = {str(f["game_id"]): f for f in eloh_forecasts(games, model, season).to_dict("records")}
    ok = [(r, fc[str(r["game_id"])]) for r in wanted.to_dict("records") if str(r["game_id"]) in fc]
    if len(ok) < len(wanted):
        log.warning("ELOH: %d upcoming games have no forecast", len(wanted) - len(ok))
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
            "p_home": f["p_home"],
            "exp_margin": f["exp_margin"],
            "model": "eloh",
            "model_version": model.version,
            "predicted_at_utc": predicted_at.strftime(TIME_FORMAT),
        }
        for r, f in ok
    ]
    append_rows(log_path, LOG_COLUMNS, rows)
    log.info("ELOH: %d rows appended to %s", len(rows), log_path)
    return len(rows)
