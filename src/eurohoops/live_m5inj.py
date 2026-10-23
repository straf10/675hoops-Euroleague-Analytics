"""Live M5-INJ (EuroLeague only): an append-only pre-tip-off shadow log of M5 with the BasketNews
"Out" statuses applied to the projected minute shares (docs/models/m5_inj.md), next to (never in)
the M5 log.

It is M5 (``live_m5``: the same frozen choice, the same inputs and the same walk-forward) with one
step changed: the projected shares of the players whose latest status before the row's cutoff is
``Out`` are set to zero, and their team-side renormalised (``models.availability.apply_out``).
The cutoff is the instant the row is forecast and stamped, read before the injury log is used, so
only snapshots stamped strictly before it count. The shares change only for the games being logged
now; every other game of the frame keeps M5's shares.

Nothing is written while ``config.M5INJ_LIVE_ENABLED`` is False (checked by the CLI).
"""

import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.config import M5, M5Backtest
from eurohoops.eval.common import tagged_version
from eurohoops.eval.m5_backtest import predict_games
from eurohoops.live_m1 import M1_LOG_COLUMNS
from eurohoops.live_m5 import Build, LiveM5, live_spec
from eurohoops.logs import TIME_FORMAT, append_rows
from eurohoops.models.availability import RosterPlayer, apply_out, match_injuries, out_players
from eurohoops.models.elo import FloatArray
from eurohoops.predict import logged_keys, refuse_late, upcoming_games

M5INJ_LOG_COLUMNS = M1_LOG_COLUMNS  # the same shape as M5's
RULE_NAME = "out-v1"  # the declared availability rule (docs/models/m5_inj.md)

log = logging.getLogger(__name__)


def m5inj_version(m5_version: str) -> str:
    """M5-INJ's ``model_version``: the package version and a hash of M5's version and the rule."""
    return tagged_version("m5inj", f"{m5_version};{RULE_NAME}")


def predict_upcoming_m5inj(
    games: pd.DataFrame,
    model: LiveM5,
    build: Build,
    *,
    injuries: pd.DataFrame,
    roster: Sequence[RosterPlayer],
    log_path: Path,
    season: int,
    round_lead: timedelta,
    clock: Callable[[], datetime],
    spec: M5Backtest = M5,
) -> int:
    """Like ``live_m5.predict_upcoming_m5``: confirmed, unplayed ``season`` games of rounds starting
    within ``round_lead`` that are not logged at M5-INJ's version yet. ``injuries`` is the injury
    log and ``roster`` the season's roster names (both read from caches by the caller). ``build``
    is called only when there is something to log. Nothing is logged unless M5's gate passed."""
    if not model.gate_passed:
        log.info("M5-INJ: M5 did not pass its validation gate: not logged")
        return 0
    cutoff = clock().replace(microsecond=0)  # the logged stamp's precision, so replays agree
    upcoming = upcoming_games(games, season, cutoff, round_lead)
    version = m5inj_version(model.version)
    logged = logged_keys(log_path)
    fresh = np.array([(str(g), version) not in logged for g in games["game_id"]], dtype=bool)
    wanted = games[upcoming & fresh]
    if wanted.empty:
        return 0
    out = out_players(match_injuries(injuries, roster), cutoff)
    log.info("M5-INJ: %d players Out at the cutoff %s", len(out), cutoff)
    target_ids = set(wanted["game_id"].astype(str))
    inputs, player_part = build()

    def player_part_out(frame: pd.DataFrame, shares: pd.DataFrame) -> FloatArray:
        # M5's player part on the projected shares with the Out players zeroed (target games only)
        return player_part(frame, apply_out(shares, target_ids, out))

    fc = predict_games(
        inputs,
        spec=live_spec(spec, season),
        player_part=player_part_out,
        choice=model.choice,
    ).set_index("game_id")
    rows_in = wanted.to_dict("records")
    ok = [
        r
        for r in rows_in
        if str(r["game_id"]) in fc.index
        and np.isfinite(fc.loc[str(r["game_id"]), ["p_home", "exp_margin", "exp_total"]]).all()
    ]
    if len(ok) < len(rows_in):
        log.warning("M5-INJ: %d upcoming games have no forecast", len(rows_in) - len(ok))
    refuse_late(cutoff, [(r["game_id"], r["tipoff_utc"]) for r in ok])
    rows = []
    for r in ok:
        f = fc.loc[str(r["game_id"])]
        rows.append(
            {
                "game_id": r["game_id"],
                "season": r["season"],
                "round": r["round"],
                "phase": r["phase"],
                "tipoff_utc": r["tipoff_utc"].strftime(TIME_FORMAT),
                "home": r["home"],
                "away": r["away"],
                "p_home": f"{f['p_home']:.4f}",
                "exp_margin": f"{f['exp_margin']:.2f}",
                "exp_total": f"{f['exp_total']:.2f}",
                "margin_sigma": f"{f['margin_sigma']:.4f}",
                "margin_df": "" if np.isnan(f["margin_df"]) else f"{f['margin_df']:g}",
                "total_sigma": f"{f['total_sigma']:.4f}",
                "model": "m5inj",
                "model_version": version,
                "predicted_at_utc": cutoff.strftime(TIME_FORMAT),
            }
        )
    append_rows(log_path, M5INJ_LOG_COLUMNS, rows)
    log.info("M5-INJ: %d rows appended to %s", len(rows), log_path)
    return len(rows)
