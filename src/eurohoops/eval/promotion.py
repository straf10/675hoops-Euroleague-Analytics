"""Flagship promotion test (PLAN §8.1 R1; rule text in ``docs/models/m5.md`` and ``m1.md``).

The flagship (M5 in the EuroLeague, M1 in the GBL) replaces Elo as the published forecast at
one of two pre-registered looks if its mean per-game log loss is clearly lower on the live games
both models logged before tip-off: the two-sided 97.5% paired-bootstrap CI of the mean gap
(flagship - Elo) lies below 0 **and** the mean gap is -0.01 or lower.

``promotion_verdict`` is the pure statistic. ``checkpoint_status`` says whether a look's
checkpoint is complete, and ``paired_log_losses`` pairs the two logs; the CLI refuses to
compute anything before the checkpoint is complete, because a statistic computed earlier is an
unplanned peek.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval.forecasts import REGULAR_SEASON, _finished, _provable
from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.eval.scorecard import read_log
from eurohoops.logs import write_json
from eurohoops.models.elo import FloatArray

RESAMPLES = 10_000
SEED = 20261009  # the date the rule was pre-registered
CI_LEVEL = 0.975  # two-sided; the 5% error rate is split over the two looks (Bonferroni)
MIN_GAP = -0.01  # the mean gap must be this or lower
LOOK_ROUNDS = {"euroleague": 19, "gbl": 13}  # look 1: after this regular-season round
FLAGSHIPS = {"euroleague": "M5", "gbl": "M1"}


@dataclass(frozen=True)
class Verdict:
    competition: str
    season: int
    look: int
    checkpoint: str
    flagship: str
    flagship_version: str
    elo_versions: list[str]
    first_round: int
    n_games: int
    flagship_log_loss: float
    elo_log_loss: float
    mean_diff: float
    ci_lo: float
    ci_hi: float
    ci_level: float
    resamples: int
    seed: int
    min_gap: float
    ci_upper_below_zero: bool
    mean_at_most_min_gap: bool
    promote: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def bootstrap_ci(
    diff: FloatArray, resamples: int = RESAMPLES, seed: int = SEED
) -> tuple[float, float]:
    """Paired bootstrap over games: the two-sided ``CI_LEVEL`` interval of the mean of ``diff``."""
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    for i in range(resamples):
        means[i] = diff[rng.integers(0, len(diff), len(diff))].mean()
    tail = 100.0 * (1.0 - CI_LEVEL) / 2.0
    lo, hi = np.percentile(means, [tail, 100.0 - tail])
    return float(lo), float(hi)


def promotion_verdict(
    flagship_loss: FloatArray,
    elo_loss: FloatArray,
    *,
    competition: str,
    season: int,
    look: int,
    checkpoint: str,
    flagship_version: str,
    elo_versions: Sequence[str],
    first_round: int,
) -> Verdict:
    """The verdict from paired per-game log losses (same games, same order)."""
    if len(flagship_loss) != len(elo_loss):
        raise ValueError("the two loss arrays must cover the same games")
    if len(flagship_loss) < 2:
        raise ValueError("a promotion test needs at least 2 paired games")
    diff = flagship_loss - elo_loss
    mean = float(diff.mean())
    lo, hi = bootstrap_ci(diff)
    below = hi < 0.0
    deep = mean <= MIN_GAP
    return Verdict(
        competition=competition,
        season=season,
        look=look,
        checkpoint=checkpoint,
        flagship=FLAGSHIPS[competition],
        flagship_version=flagship_version,
        elo_versions=sorted(elo_versions),
        first_round=first_round,
        n_games=len(diff),
        flagship_log_loss=round(float(flagship_loss.mean()), 6),
        elo_log_loss=round(float(elo_loss.mean()), 6),
        mean_diff=round(mean, 6),
        ci_lo=round(lo, 6),
        ci_hi=round(hi, 6),
        ci_level=CI_LEVEL,
        resamples=RESAMPLES,
        seed=SEED,
        min_gap=MIN_GAP,
        ci_upper_below_zero=bool(below),
        mean_at_most_min_gap=bool(deep),
        promote=bool(below and deep),
    )


def checkpoint_status(games: pd.DataFrame, season: int, look: int, rnd: int) -> tuple[bool, str]:
    """Whether look ``look`` may be computed, and why not if it may not.

    Look 1: round ``rnd`` of the regular season exists and every regular-season game of rounds
    up to it is played (a forfeit counts as played; a postponed game keeps it open). Look 2: the
    season has games and every scheduled game of every phase is played.
    """
    season_games = games[games["season"] == season]
    if look == 1:
        regular = season_games[season_games["phase"] == REGULAR_SEASON]
        if not (regular["round"] == rnd).any():
            return False, f"round {rnd} is not in the schedule"
        open_games = regular[(regular["round"] <= rnd) & ~regular["played"]]
        if len(open_games):
            return False, f"{len(open_games)} game(s) of rounds 1-{rnd} are not played yet"
        return True, f"regular-season round {rnd} complete"
    if look == 2:
        if season_games.empty:
            return False, "no games in the season"
        open_games = season_games[~season_games["played"]]
        if len(open_games):
            return False, f"{len(open_games)} scheduled game(s) of the season are not played yet"
        return True, "season complete"
    raise ValueError("look must be 1 or 2")


def _flagship_rows(log: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """The flagship's log cut to its latest ``model_version`` (a new one restarts the count)."""
    latest = log.sort_values("predicted_at_utc").iloc[-1]["model_version"]
    return log[log["model_version"] == latest], str(latest)


def paired_log_losses(
    flagship_log: Path,
    elo_log: Path,
    games: pd.DataFrame,
    season: int,
    manual_pushes: Sequence[datetime],
    *,
    last_round: int | None,
) -> tuple[FloatArray, FloatArray, int, str, list[str]]:
    """Paired per-game log losses (flagship, Elo), tip-off order, on the games both logged.

    ``last_round`` caps the games at that regular-season round (look 1); ``None`` takes the
    whole season. Returns the two arrays, the flagship's first round, its version and the Elo
    versions of the paired games.
    """
    flagship_all = read_log(flagship_log)
    flagship_all = flagship_all[flagship_all["season"] == season]
    if flagship_all.empty:
        raise ValueError("the flagship has no logged games this season")
    flagship_rows, version = _flagship_rows(flagship_all)
    flagship = _provable(flagship_rows, manual_pushes)
    elo = _provable(read_log(elo_log), manual_pushes)
    elo = elo[elo["season"] == season]
    finished = _finished(games, season)
    if last_round is not None:
        finished = finished[
            (finished["phase"] == REGULAR_SEASON) & (finished["round"] <= last_round)
        ]
    paired = (
        flagship[["game_id", "p_home", "round"]]
        .merge(elo[["game_id", "p_home", "model_version"]], on="game_id", suffixes=("_f", "_e"))
        .merge(finished[["game_id", "tipoff_utc", "home_score", "away_score"]], on="game_id")
        .sort_values(["tipoff_utc", "game_id"], ignore_index=True)
    )
    if paired.empty:
        raise ValueError("no game was logged by both models before tip-off and has a result")
    home_won = (paired["home_score"] > paired["away_score"]).to_numpy().astype(np.float64)
    return (
        per_game_log_loss(paired["p_home_f"].to_numpy(dtype=np.float64), home_won),
        per_game_log_loss(paired["p_home_e"].to_numpy(dtype=np.float64), home_won),
        int(flagship["round"].min()),
        version,
        sorted(set(paired["model_version"].astype(str))),
    )


class LookNotDueError(RuntimeError):
    """A look was asked for before its checkpoint is complete, or a second time."""


def run_look(  # noqa: PLR0917 -- one look's inputs
    competition: str,
    look: int,
    games: pd.DataFrame,
    season: int,
    flagship_log: Path,
    elo_log: Path,
    manual_pushes: Sequence[datetime],
    out_dir: Path,
) -> tuple[Verdict, Path]:
    """Run one look and write ``promotion_<competition>_<season>_look<look>.json`` to ``out_dir``.

    The guard comes first: before the checkpoint is complete (or when the look's file already
    exists) nothing is read from the logs or computed.
    """
    rnd = LOOK_ROUNDS[competition]
    due, why = checkpoint_status(games, season, look, rnd)
    if not due:
        raise LookNotDueError(f"look {look} is not due: {why}")
    out = out_dir / f"promotion_{competition}_{season}_look{look}.json"
    if out.exists():
        raise LookNotDueError(f"{out} exists: a look is run once")
    flagship, elo, first_round, version, elo_versions = paired_log_losses(
        flagship_log, elo_log, games, season, manual_pushes, last_round=rnd if look == 1 else None
    )
    verdict = promotion_verdict(
        flagship,
        elo,
        competition=competition,
        season=season,
        look=look,
        checkpoint=why,
        flagship_version=version,
        elo_versions=elo_versions,
        first_round=first_round,
    )
    write_json(out, verdict.as_dict())
    return verdict, out
