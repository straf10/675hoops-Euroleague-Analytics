"""POOL3 screen (experiments/pool3.md, IDEAS.md C2): are POOL's members near-duplicates?

ELOR is Elo plus a fading roster offset, so POOL's equal weights give Elo's information roughly
double weight. The screen measures how alike the four live members' logits are on the finished
2026-27 EuroLeague games. It is diagnostic: it reads the logs and the games mart and writes nothing
but its report. Only a Pearson correlation of the Elo and ELOR logits above RULE_THRESHOLD declares
POOL3 (the orchestrator decides on that).
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import LIVE_SEASON
from eurohoops.eval.metrics import per_game_log_loss
from eurohoops.eval.scorecard import latest_per_model_game, not_provable
from eurohoops.models.pool import COMPONENTS, PROB_CLIP, logit

SPEC_COMMITTED_AT = datetime(2026, 10, 28, 9, 49, 14, tzinfo=UTC)  # commit 82060b7, 12:49:14+03:00
RULE_THRESHOLD = 0.98  # the screen declares POOL3 when corr(logit Elo, logit ELOR) is above it
MEMBERS = COMPONENTS  # ("elo", "m1", "m5", "elor"): POOL's members, in POOL's column order


def member_rows(
    log: pd.DataFrame, version: str, manual_pushes: Sequence[datetime] = ()
) -> pd.DataFrame:
    """One member's forecast per game, chosen as the live scorecard's headline chooses it.

    Only the rows at the pinned ``version`` (the ones POOL reads) count. Among them the scorecard's
    rules apply: a row must be stamped strictly before tip-off and not hidden as public only after
    it (``not_provable``), and a game keeps its latest such row (``latest_per_model_game``).
    Returns ``game_id`` and ``p_home`` with one row per game.
    """
    rows = log[log["model_version"] == version]
    valid = rows[
        pd.to_datetime(rows["predicted_at_utc"], utc=True)
        < pd.to_datetime(rows["tipoff_utc"], utc=True)
    ]
    kept = valid[~not_provable(valid, manual_pushes)]
    latest = latest_per_model_game(kept).sort_values("predicted_at_utc", kind="stable")
    return latest.drop_duplicates("game_id", keep="first")[["game_id", "p_home"]].reset_index(
        drop=True
    )


def finished_games(games: pd.DataFrame, cutoff: datetime, season: int) -> pd.DataFrame:
    """Played, non-forfeit games of ``season`` that tipped off strictly before ``cutoff``."""
    tipoff = pd.to_datetime(games["tipoff_utc"], utc=True)
    keep = (
        games["played"]
        & ~games["forfeit"]
        & (games["season"] == season)
        & (tipoff < pd.Timestamp(cutoff))
    )
    return games.loc[keep, ["game_id", "tipoff_utc", "home_score", "away_score"]].reset_index(
        drop=True
    )


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson correlation; None when undefined (fewer than two games or a constant series)."""
    if len(a) < 2 or np.std(a) == 0.0 or np.std(b) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _matrix(columns: Mapping[str, np.ndarray]) -> dict[str, dict[str, float | None]]:
    return {a: {b: _pearson(columns[a], columns[b]) for b in columns} for a in columns}


def screen(
    members: Mapping[str, pd.DataFrame],
    games: pd.DataFrame,
    *,
    cutoff: datetime = SPEC_COMMITTED_AT,
    season: int = LIVE_SEASON,
) -> dict[str, Any]:
    """The POOL3 screen on the games every member logged, plus the Elo-ELOR pair on its own.

    ``members`` maps each name in ``MEMBERS`` to its ``member_rows`` frame; ``games`` is the games
    mart. The rule uses the games where all four members logged a forecast; the pair figures use
    the games where Elo and ELOR both did. Both sets are finished games that tipped off before
    ``cutoff``.
    """
    base = finished_games(games, cutoff, season)
    wide = base
    for name in MEMBERS:
        wide = wide.merge(
            members[name].rename(columns={"p_home": f"p_{name}"}), on="game_id", how="inner"
        )
    wide = wide.assign(home_won=(wide["home_score"] > wide["away_score"]).astype(np.float64))
    wide = wide.sort_values(["tipoff_utc", "game_id"], ignore_index=True)

    logits = {name: logit(wide[f"p_{name}"].to_numpy(np.float64)) for name in MEMBERS}
    losses: dict[str, np.ndarray] = {}
    for name in MEMBERS:
        p = np.clip(wide[f"p_{name}"].to_numpy(np.float64), PROB_CLIP, 1.0 - PROB_CLIP)
        losses[name] = per_game_log_loss(p, wide["home_won"].to_numpy(np.float64))

    rule_value = _pearson(logits["elo"], logits["elor"])
    pair = base.merge(members["elo"].rename(columns={"p_home": "p_elo"}), on="game_id").merge(
        members["elor"].rename(columns={"p_home": "p_elor"}), on="game_id"
    )
    pair_value = _pearson(
        logit(pair["p_elo"].to_numpy(np.float64)), logit(pair["p_elor"].to_numpy(np.float64))
    )

    return {
        "cutoff_utc": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season,
        "n_games": len(wide),
        "games": wide["game_id"].tolist(),
        "rule": {
            "metric": "pearson(logit p_home Elo, logit p_home ELOR)",
            "value": rule_value,
            "threshold": RULE_THRESHOLD,
            "declared": rule_value is not None and rule_value > RULE_THRESHOLD,
        },
        "pair_elo_elor": {"n_games": len(pair), "corr_logit": pair_value},
        "members": list(MEMBERS),
        "mean_log_loss": {name: float(losses[name].mean()) for name in MEMBERS}
        if len(wide)
        else {},
        "corr_logit": _matrix(logits),
        "corr_log_loss": _matrix(losses),
        "per_game": [
            {
                "game_id": str(row["game_id"]),
                "home_won": bool(row["home_won"]),
                "p_home": {name: float(row[f"p_{name}"]) for name in MEMBERS},
                "log_loss": {name: float(losses[name][i]) for name in MEMBERS},
            }
            for i, row in enumerate(wide.to_dict("records"))
        ],
    }
