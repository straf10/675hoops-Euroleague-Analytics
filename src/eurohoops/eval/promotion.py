"""Shadow promotion test (CLAUDE.md rule 4; PLAN §8.1 R1; rule text in ``docs/models/m5.md``).

At each look, every active shadow in the model catalog is tested against the published Elo log
on its own: a shadow replaces Elo if its mean per-game log loss is clearly lower on the live
games both models logged before tip-off: the two-sided 97.5% paired-bootstrap CI of the mean gap
(shadow - Elo) lies below 0 **and** the mean gap is -0.01 or lower.

``promotion_verdict`` is the pure statistic. ``checkpoint_status`` says whether a look's
checkpoint is complete, and ``pair_logs`` pairs one shadow's log with Elo's; the CLI refuses to
compute anything before the checkpoint is complete, because a statistic computed earlier is an
unplanned peek.

Reported next to each verdict, never in the decision: a round-clustered bootstrap of the same
gap (``sensitivity_round_clustered``). ``promote`` depends on the verdict's inputs alone.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval.forecasts import REGULAR_SEASON, finished_games
from eurohoops.eval.metrics import (
    paired_bootstrap_ci,
    paired_bootstrap_ci_clustered,
    per_game_log_loss,
)
from eurohoops.logs import read_log, scored_rows, write_json
from eurohoops.models.elo import FloatArray

RESAMPLES = 10_000
SEED = 20261009  # the date the rule was pre-registered
CI_LEVEL = 0.975  # two-sided; the 5% error rate is split over the two looks (Bonferroni)
MIN_GAP = -0.01  # the mean gap must be this or lower
LOOK_ROUNDS = {"euroleague": 19}  # look 1: after this regular-season round


@dataclass(frozen=True)
class Verdict:
    competition: str
    season: int
    look: int
    checkpoint: str
    shadow: str
    shadow_version: str
    elo_versions: list[str]
    first_round: int
    n_games: int
    shadow_log_loss: float
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
    tail = 100.0 * (1.0 - CI_LEVEL) / 2.0
    _, lo, hi = paired_bootstrap_ci(diff, resamples, seed, percentiles=(tail, 100.0 - tail))
    return lo, hi


class NotTestableError(ValueError):
    """A shadow has too few paired games for a verdict at this look."""


def promotion_verdict(
    shadow_loss: FloatArray,
    elo_loss: FloatArray,
    *,
    competition: str,
    season: int,
    look: int,
    checkpoint: str,
    shadow: str,
    shadow_version: str,
    elo_versions: Sequence[str],
    first_round: int,
) -> Verdict:
    """The verdict from paired per-game log losses (same games, same order)."""
    if len(shadow_loss) != len(elo_loss):
        raise ValueError("the two loss arrays must cover the same games")
    if len(shadow_loss) < 2:
        raise NotTestableError("a promotion test needs at least 2 paired games")
    diff = shadow_loss - elo_loss
    mean = float(diff.mean())
    lo, hi = bootstrap_ci(diff)
    below = hi < 0.0
    deep = mean <= MIN_GAP
    return Verdict(
        competition=competition,
        season=season,
        look=look,
        checkpoint=checkpoint,
        shadow=shadow,
        shadow_version=shadow_version,
        elo_versions=sorted(elo_versions),
        first_round=first_round,
        n_games=len(diff),
        shadow_log_loss=round(float(shadow_loss.mean()), 6),
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


def latest_version_rows(log: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """A shadow's log cut to its latest ``model_version`` (GLOSSARY: version restart).

    The latest version is the one of the row with the latest ``predicted_at_utc``, read as a UTC
    datetime (so ``...Z`` and ``...+00:00`` stamps compare as times, not as text).
    """
    stamps = pd.to_datetime(log["predicted_at_utc"], utc=True)
    latest = log.loc[stamps.sort_values(kind="stable").index[-1], "model_version"]
    return log[log["model_version"] == latest], str(latest)


def _capped_finished(games: pd.DataFrame, season: int, last_round: int | None) -> pd.DataFrame:
    """The season's finished games, capped at ``last_round`` (regular season) when given."""
    finished = finished_games(games, season)
    if last_round is not None:
        finished = finished[
            (finished["phase"] == REGULAR_SEASON) & (finished["round"] <= last_round)
        ]
    return finished


@dataclass(frozen=True)
class Pairing:
    """One shadow's look: the games it and Elo both logged provably before tip-off that have a
    result, in tip-off order, with each side's per-game log loss."""

    games: pd.DataFrame  # game_id, round, p_home_a (shadow), p_home_b and model_version (Elo)
    shadow_loss: FloatArray
    elo_loss: FloatArray
    first_round: int  # the shadow's first scored round (its latest version)
    version: str  # the shadow's latest version

    @property
    def elo_versions(self) -> list[str]:
        return sorted(set(self.games["model_version"].astype(str)))


def pair_logs(
    shadow_log: Path,
    elo_log: Path,
    games: pd.DataFrame,
    season: int,
    manual_pushes: Sequence[datetime],
    *,
    last_round: int | None,
) -> Pairing:
    """Pair a shadow's scored rows (its latest version only) with Elo's on the finished games.

    ``last_round`` caps the games at that regular-season round (look 1); ``None`` takes the
    whole season. Raises ``NotTestableError`` when there is no paired game.
    """
    log = read_log(shadow_log)
    log = log[log["season"] == season]
    if log.empty:
        raise NotTestableError("the shadow has no logged games this season")
    rows, version = latest_version_rows(log)
    shadow = scored_rows(rows, manual_pushes)
    elo_log_rows = read_log(elo_log)
    elo = scored_rows(elo_log_rows[elo_log_rows["season"] == season], manual_pushes)
    finished = _capped_finished(games, season, last_round)
    paired = (
        shadow[["game_id", "p_home", "round"]]
        .merge(elo[["game_id", "p_home", "model_version"]], on="game_id", suffixes=("_a", "_b"))
        .merge(finished[["game_id", "tipoff_utc", "home_score", "away_score"]], on="game_id")
        .sort_values(["tipoff_utc", "game_id"], ignore_index=True)
    )
    if paired.empty:
        raise NotTestableError("no game was logged by both models before tip-off and has a result")
    home_won = (paired["home_score"] > paired["away_score"]).to_numpy().astype(np.float64)
    return Pairing(
        games=paired,
        shadow_loss=per_game_log_loss(paired["p_home_a"].to_numpy(dtype=np.float64), home_won),
        elo_loss=per_game_log_loss(paired["p_home_b"].to_numpy(dtype=np.float64), home_won),
        first_round=int(shadow["round"].min()),
        version=version,
    )


def _round_clustered(paired: pd.DataFrame, season: int, diff: FloatArray) -> dict[str, Any]:
    """The look's gap with whole rounds resampled (same resamples and seed as R1). Reported only.

    Games of one round share a cluster, so the spread of the gap across rounds is what the CI
    reflects; the game-level CI in the verdict is unchanged.
    """
    labels = [f"{season}-R{r}" for r in paired["round"].to_numpy()]
    mean, low, high = paired_bootstrap_ci_clustered(diff, labels, RESAMPLES, SEED, level=CI_LEVEL)
    return {
        "cluster": "season-round",
        "n_games": len(diff),
        "n_clusters": len(set(labels)),
        "mean_diff": round(mean, 6),
        "ci_lo": round(low, 6),
        "ci_hi": round(high, 6),
        "ci_level": CI_LEVEL,
        "resamples": RESAMPLES,
        "seed": SEED,
    }


class LookNotDueError(RuntimeError):
    """A look was asked for before its checkpoint is complete, or a second time."""


@dataclass(frozen=True)
class LookResult:
    """One look: a verdict and its report per tested shadow, and why any shadow was not tested."""

    verdicts: dict[str, tuple[Verdict, Path]]  # shadow tag -> verdict, report path
    not_tested: dict[str, str]  # shadow tag -> reason (too few paired games)


def report_path(out_dir: Path, competition: str, season: int, tag: str, look: int) -> Path:
    """``promotion_<competition>_<season>_<tag>_look<look>.json``: one shadow's look report."""
    return out_dir / f"promotion_{competition}_{season}_{tag}_look{look}.json"


def run_look(  # noqa: PLR0917 -- one look's inputs
    competition: str,
    look: int,
    games: pd.DataFrame,
    season: int,
    shadows: Mapping[str, Path],
    elo_log: Path,
    manual_pushes: Sequence[datetime],
    out_dir: Path,
) -> LookResult:
    """Run one look for every shadow in ``shadows`` (tag -> log; the catalog's active shadows)
    and write one ``report_path`` file per tested shadow.

    The guard comes first: before the checkpoint is complete (or when any report of this look
    already exists) nothing is read from the logs or computed. Each shadow is paired, tested and
    reported on its own, with the same pairing, bootstrap and pass bar. A shadow with fewer than
    2 paired games gets no verdict and no file; its reason is in ``not_tested``. Each file holds
    the verdict's keys, then the reported-only block ``sensitivity_round_clustered``.
    """
    rnd = LOOK_ROUNDS[competition]
    due, why = checkpoint_status(games, season, look, rnd)
    if not due:
        raise LookNotDueError(f"look {look} is not due: {why}")
    done = sorted(out_dir.glob(report_path(Path(), competition, season, "*", look).name))
    if done:
        raise LookNotDueError(f"{done[0]} exists: a look is run once")
    last_round = rnd if look == 1 else None
    tested: dict[str, tuple[Verdict, dict[str, Any]]] = {}
    not_tested: dict[str, str] = {}
    for tag, log in shadows.items():  # every shadow is computed before any file is written
        try:
            pairing = pair_logs(log, elo_log, games, season, manual_pushes, last_round=last_round)
            verdict = promotion_verdict(
                pairing.shadow_loss,
                pairing.elo_loss,
                competition=competition,
                season=season,
                look=look,
                checkpoint=why,
                shadow=tag,
                shadow_version=pairing.version,
                elo_versions=pairing.elo_versions,
                first_round=pairing.first_round,
            )
        except NotTestableError as exc:
            not_tested[tag] = str(exc)
            continue
        payload = verdict.as_dict()
        payload["sensitivity_round_clustered"] = _round_clustered(
            pairing.games, season, pairing.shadow_loss - pairing.elo_loss
        )
        tested[tag] = (verdict, payload)
    verdicts: dict[str, tuple[Verdict, Path]] = {}
    for tag, (verdict, payload) in tested.items():
        out = report_path(out_dir, competition, season, tag, look)
        write_json(out, payload)
        verdicts[tag] = (verdict, out)
    return LookResult(verdicts, not_tested)
