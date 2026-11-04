"""Live M5-INJ (EuroLeague only): an append-only pre-tip-off shadow log of M5 with the BasketNews
"Out" statuses applied to the projected minute shares (docs/models/m5_inj.md), next to (never in)
the M5 log.

It is M5 (``live_m5``: the same frozen choice, the same inputs and the same walk-forward) with one
step changed: the projected shares of the players whose latest status before the row's cutoff is
``Out`` are set to zero, and their team-side renormalised (``models.availability.apply_out``).
The cutoff is the instant the row is forecast and stamped, read before the injury log is used, so
only snapshots stamped strictly before it count. The latest of them must be at most
``config.M5INJ_MAX_SNAPSHOT_AGE_HOURS`` old, else no row is written for the run (no fallback to M5).
The shares change only for the games being logged now; every other game of the frame keeps M5's
shares.

Nothing is written while ``config.M5INJ_LIVE_ENABLED`` is False (``shadow_log.is_active``, checked
by the CLI).
"""

import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from eurohoops.config import M5, M5INJ_MAX_SNAPSHOT_AGE_HOURS, M5Backtest
from eurohoops.eval.common import tagged_version
from eurohoops.eval.m5_backtest import predict_games
from eurohoops.live_m1 import M1_LOG_COLUMNS
from eurohoops.live_m5 import Build, LiveM5, live_spec, m5_strings
from eurohoops.logs import TIME_FORMAT
from eurohoops.models.availability import (
    RosterPlayer,
    apply_out,
    latest_snapshot,
    match_injuries,
    out_players,
)
from eurohoops.models.elo import FloatArray
from eurohoops.shadow_log import append_shadow_log

M5INJ_LOG_COLUMNS = M1_LOG_COLUMNS  # the same shape as M5's
# The declared availability rule (docs/models/m5_inj.md). v2 adds the snapshot maximum age.
RULE_NAME = f"out-v2-max-age-{M5INJ_MAX_SNAPSHOT_AGE_HOURS}h"

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
    version = m5inj_version(model.version)

    def forecast(due: pd.DataFrame) -> dict[str, dict[str, str]] | None:
        matched = match_injuries(injuries, roster)
        stamp = latest_snapshot(matched, cutoff)
        max_age = timedelta(hours=M5INJ_MAX_SNAPSHOT_AGE_HOURS)
        if stamp is None:
            log.warning("m5inj: no injury snapshot before %s; no M5-INJ rows written", cutoff)
            return None
        age = pd.Timestamp(cutoff) - stamp
        if age > max_age:
            log.warning(
                "m5inj: latest injury snapshot %s is %.1f h old (> %d h); no M5-INJ rows written",
                stamp.strftime(TIME_FORMAT),
                age.total_seconds() / 3600,
                M5INJ_MAX_SNAPSHOT_AGE_HOURS,
            )
            return None
        out = out_players(matched, cutoff)
        log.info("M5-INJ: %d players Out at the cutoff %s", len(out), cutoff)
        target_ids = set(due["game_id"].astype(str))
        inputs, player_part = build()

        def player_part_out(frame: pd.DataFrame, shares: pd.DataFrame) -> FloatArray:
            # M5's player part on the projected shares with the Out players zeroed (target games)
            return player_part(frame, apply_out(shares, target_ids, out))

        fc = predict_games(
            inputs,
            spec=live_spec(spec, season),
            player_part=player_part_out,
            choice=model.choice,
        ).set_index("game_id")
        return m5_strings(fc, due)

    return append_shadow_log(
        games,
        forecast,
        tag="m5inj",
        label="M5-INJ",
        version=version,
        columns=M5INJ_LOG_COLUMNS,
        log_path=log_path,
        season=season,
        round_lead=round_lead,
        clock=lambda: cutoff,  # one read: the stamp is the cutoff the injuries were read at
    )
