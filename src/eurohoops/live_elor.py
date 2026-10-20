"""Live ELOR (EuroLeague only): an append-only pre-tip-off shadow log of Elo with a fading roster
prior (docs/models/elo_roster_prior.md, "Live amendment"), next to (never in) the Elo log.

ELOR is logged only while its one-shot CV report (``reports/elor_cv.json``) says every shadow
criterion passed; the setting is that report's ``selected`` (``w0``, ``N``). The forecast is the
CV's own construction: Elo replayed from the first warm-up season with the fixed parameters, the
roster offsets at each game's round cutoff (roster list in force, M3 walk-forward ratings and
projected shares from box scores before the cutoff, the season's newcomer prior), the margin
scale fitted on earlier seasons only, faded by the game's round index. A game without a roster
prior (no M3 state, no possessions, a side with no rostered player) is logged as plain Elo.
"""

import hashlib
import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.eval.elor_cv import ElorInputs
from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.models import elo
from eurohoops.models.elor import (
    Appearances,
    ElorSetting,
    elor_diff,
    margin_scales,
    newcomer_priors,
    offsets,
    roster_strengths,
    round_index,
    season_starts,
    win_probabilities,
)
from eurohoops.models.roster import unmatched_clubs
from eurohoops.predict import LOG_COLUMNS, logged_keys, refuse_late, upcoming_games

ELOR_LOG_COLUMNS = LOG_COLUMNS  # the Elo log's shape: ELOR has no totals

log = logging.getLogger(__name__)

# What a run needs once there is something to forecast: marts, roster list and the M3 fit.
Build = Callable[[], ElorInputs]


@dataclass(frozen=True)
class LiveElor:
    setting: ElorSetting
    elo_params: elo.EloParams
    first_season: int  # the Elo replay's first season (the CV's first warm-up season)
    version: str
    passed: bool  # every shadow criterion of the CV report


def load_elor(report_path: Path) -> LiveElor | None:
    """The selected ELOR setting of the CV report; None when there is no report."""
    if not report_path.exists():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    chosen = report["selected"]
    frozen = {
        "selected": {"w0": float(chosen["w0"]), "n_rounds": int(chosen["n_rounds"])},
        "elo_params": report["elo_params"],
        "elo_warmup": report["elo_warmup"],
        "first_round_rule": report["first_round_rule"],
        "git_head": report["git_head"],
    }
    digest = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()[:8]
    return LiveElor(
        setting=ElorSetting(float(chosen["w0"]), int(chosen["n_rounds"])),
        elo_params=elo.EloParams(**report["elo_params"]),
        first_season=int(report["elo_warmup"][0]),
        version=f"{version('eurohoops')}+elor.{digest}",
        passed=report.get("shadow_criteria", {}).get("all") is True,
    )


def elor_forecasts(inputs: ElorInputs, model: LiveElor, season: int) -> pd.DataFrame:
    """ELOR's forecast of every ``season`` game: ``game_id``, ``p_home``, ``exp_margin`` and
    ``prior_available`` (False: the game is plain Elo)."""
    games = inputs.games[inputs.games["season"].between(model.first_season, season)]
    games = games.sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    live = (games["season"] == season).to_numpy()
    mismatch = unmatched_clubs(inputs.roster, games[live])
    if mismatch:
        raise ValueError(f"roster club codes do not match the games mart: {mismatch}")
    arrays = elo.prepare(games)
    elo_diff = elo.replay(arrays, model.elo_params)
    starts = season_starts(arrays, model.elo_params, [season])
    scales = margin_scales(games, elo_diff)
    appearances = Appearances(games, inputs.player_games)
    prior = newcomer_priors(appearances, inputs.season_end_rating, [season])[season]
    if math.isnan(prior.rating) or math.isnan(prior.share):
        raise ValueError(f"no newcomer history before season {season}")
    roster = inputs.roster[inputs.roster["season"] == season].reset_index(drop=True)
    strengths = roster_strengths(
        games[live].reset_index(drop=True),
        roster,
        appearances,
        inputs.rating,
        priors={season: prior},
        has_state=inputs.has_state,
    )
    offs = offsets(games, strengths, starts, scales, inputs.possessions)
    diff = elor_diff(elo_diff, round_index(games), offs, model.setting)
    return pd.DataFrame(
        {
            "game_id": games.loc[live, "game_id"].astype(str).to_numpy(),
            "p_home": win_probabilities(diff[live]),
            "exp_margin": diff[live] / scales[season],
            "prior_available": offs.available[live],
        }
    )


def predict_upcoming_elor(
    games: pd.DataFrame,
    model: LiveElor,
    build: Build,
    *,
    log_path: Path,
    season: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
) -> int:
    """Like the M5 predictor: confirmed, unplayed ``season`` games of rounds starting within
    ``round_lead`` that are not logged at this model version yet. ``build`` is called only when
    there is something to log."""
    if not model.passed:
        log.info("ELOR did not pass its shadow criteria: not logged")
        return 0
    now = clock()
    upcoming = upcoming_games(games, season, now, round_lead)
    logged = logged_keys(log_path)
    fresh = np.array([(str(g), model.version) not in logged for g in games["game_id"]], dtype=bool)
    wanted = games[upcoming & fresh]
    if wanted.empty:
        return 0
    fc = {str(f["game_id"]): f for f in elor_forecasts(build(), model, season).to_dict("records")}
    rows_in = wanted.to_dict("records")
    ok = [
        (r, fc[str(r["game_id"])])
        for r in rows_in
        if str(r["game_id"]) in fc
        and math.isfinite(fc[str(r["game_id"])]["p_home"])
        and math.isfinite(fc[str(r["game_id"])]["exp_margin"])
    ]
    if len(ok) < len(rows_in):
        log.warning("ELOR: %d upcoming games have no forecast", len(rows_in) - len(ok))
    plain = sum(not f["prior_available"] for _, f in ok)
    if plain:
        log.warning("ELOR: %d upcoming games have no roster prior (logged as plain Elo)", plain)
    predicted_at = clock()
    refuse_late(predicted_at, [(r["game_id"], r["tipoff_utc"]) for r, _ in ok])
    rows = []
    for r, f in ok:
        rows.append(
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
                "model": "elor",
                "model_version": model.version,
                "predicted_at_utc": predicted_at.strftime(TIME_FORMAT),
            }
        )
    append_rows(log_path, ELOR_LOG_COLUMNS, rows)
    log.info("ELOR: %d rows appended to %s", len(rows), log_path)
    return len(rows)
