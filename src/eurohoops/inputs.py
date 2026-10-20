"""Model-input snapshots for the Elo log: what the model saw before each logged prediction.

``predict.predict_upcoming`` writes one snapshot row per Elo row it appends (``source=logged``).
``backfill_rows`` reconstructs snapshots for Elo rows logged before the snapshots existed, by
replaying Elo over the games known at each row's ``predicted_at_utc``; a snapshot is written only
when its recomputed ``p_home`` and ``exp_margin`` equal the logged strings exactly.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from eurohoops.eval.backtest import TunedModel
from eurohoops.models.elo import prepare, replay_with_ratings, win_probability

INPUT_COLUMNS = (
    "game_id",
    "season",
    "round",
    "phase",
    "tipoff_utc",
    "home",
    "away",
    "home_rating",
    "away_rating",
    "hca",
    "neutral",
    "diff",
    "margin_scale",
    "p_home",
    "exp_margin",
    "model",
    "model_version",
    "predicted_at_utc",
    "source",
)

SOURCE_LOGGED = "logged"
SOURCE_REPLAYED = "replayed"

log = logging.getLogger(__name__)


def elo_strings(diff: float, margin_scale: float) -> tuple[str, str]:
    """The ``p_home`` and ``exp_margin`` strings the Elo log stores for a rating difference."""
    return f"{win_probability(diff):.4f}", f"{diff / margin_scale:.2f}"


def input_row(
    *,
    game: Mapping[Any, Any],
    tipoff_utc: str,
    home_rating: float,
    away_rating: float,
    hca: float,
    neutral: bool,
    diff: float,
    margin_scale: float,
    p_home: str,
    exp_margin: str,
    model_version: str,
    predicted_at_utc: str,
    source: str,
) -> dict[str, str]:
    """One snapshot row; ``game`` supplies game_id, season, round, phase, home and away."""
    return {
        "game_id": str(game["game_id"]),
        "season": str(game["season"]),
        "round": str(game["round"]),
        "phase": str(game["phase"]),
        "tipoff_utc": tipoff_utc,
        "home": str(game["home"]),
        "away": str(game["away"]),
        "home_rating": f"{home_rating:.1f}",
        "away_rating": f"{away_rating:.1f}",
        "hca": f"{hca:.1f}",
        "neutral": "true" if neutral else "false",
        "diff": f"{diff:.1f}",
        "margin_scale": f"{margin_scale:.4f}",
        "p_home": p_home,
        "exp_margin": exp_margin,
        "model": "elo",
        "model_version": model_version,
        "predicted_at_utc": predicted_at_utc,
        "source": source,
    }


@dataclass
class BackfillReport:
    matched: int = 0  # snapshot rows to append
    already: int = 0  # (game, version) already in the inputs log
    skipped: list[str] = field(default_factory=list)  # one reason per skipped Elo row


def backfill_rows(
    games: pd.DataFrame,
    elo_rows: Sequence[Mapping[str, str]],
    existing: set[tuple[str, str]],
    model: TunedModel,
    replay_from: int,
) -> tuple[list[dict[str, str]], BackfillReport]:
    """Replayed snapshot rows for the Elo rows that have none, in Elo-log order.

    ``games`` is the competition's games mart, tipoff-sorted. Elo is replayed from ``replay_from``
    exactly as ``predict_upcoming`` does, but for each distinct ``predicted_at_utc`` every game
    tipping off at or after it is treated as unplayed, so the ratings are those known then.
    ``existing`` holds the (game_id, model_version) keys already in the inputs log.
    """
    report = BackfillReport()
    version = model.version()
    games = games[games["season"] >= replay_from].reset_index(drop=True)
    position = {game_id: i for i, game_id in enumerate(games["game_id"])}
    todo: dict[str, list[tuple[int, Mapping[str, str]]]] = {}
    for n, row in enumerate(elo_rows):
        key = (row["game_id"], row["model_version"])
        if key in existing:
            report.already += 1
        elif row["model_version"] != version:
            report.skipped.append(
                f"{row['game_id']}: logged model_version {row['model_version']} != {version}"
            )
        elif row["game_id"] not in position:
            report.skipped.append(f"{row['game_id']}: not in the games mart from {replay_from}")
        else:
            todo.setdefault(row["predicted_at_utc"], []).append((n, row))

    found: dict[int, dict[str, str]] = {}
    tipoff = games["tipoff_utc"]
    for predicted_at, pending in todo.items():
        at = pd.Timestamp(predicted_at)
        known = games.assign(played=games["played"].astype(bool) & (tipoff < at))
        diffs, home_ratings, away_ratings = replay_with_ratings(prepare(known), model.params)
        for n, row in pending:
            i = position[row["game_id"]]
            game = games.iloc[i]
            neutral = bool(game["neutral"])
            hca = 0.0 if neutral else model.params.hca
            diff = float(diffs[i])
            p_home, exp_margin = elo_strings(diff, model.margin_scale)
            if (p_home, exp_margin) != (row["p_home"], row["exp_margin"]):
                report.skipped.append(
                    f"{row['game_id']}: replayed p_home {p_home} / exp_margin {exp_margin} "
                    f"!= logged {row['p_home']} / {row['exp_margin']}"
                )
                continue
            found[n] = input_row(
                game=row,
                tipoff_utc=row["tipoff_utc"],
                home_rating=float(home_ratings[i]),
                away_rating=float(away_ratings[i]),
                hca=hca,
                neutral=neutral,
                diff=diff,
                margin_scale=model.margin_scale,
                p_home=p_home,
                exp_margin=exp_margin,
                model_version=version,
                predicted_at_utc=predicted_at,
                source=SOURCE_REPLAYED,
            )
    rows = [found[n] for n in sorted(found)]
    report.matched = len(rows)
    for reason in report.skipped:
        log.warning("backfill-inputs skipped %s", reason)
    return rows, report
