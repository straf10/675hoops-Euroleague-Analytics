"""Live M6 (weeks 16-18 L9): the 2026-27 player projections, the over/under board and the
"plays like" lists.

Projections. The verdict's cell (``reports/backtest_m6.json`` ``chosen``) projects every player
with a group-stage line in the live season, through the harness's own inputs
(``m6_backtest.live_inputs``: the same history, impact rows, drift and noise as a test target).
The checkpoint is the largest declared one whose rounds are complete (D22): 0 (next-season,
from every season before the live one) until k = floor(0.25 R) rounds are played, then 0.25,
0.5, 0.75, so a projection changes four times a season and a day without a newly completed
checkpoint leaves it unchanged. The intervals carry the D19 variance scale frozen at the verdict
for that checkpoint. Ages are not read: the chosen variant does not age (a variant that did
would fit the curve from ``ages``, in memory only).

Board (D23) and similarity: the newest complete season (``board_season``: the last season with a
BRAPM snapshot and M2 xPTS), stabilities from the M6 tuning seasons; the "plays like" pool is
every complete season with ``min_poss`` possessions, and a live player's query is his newest
such season. Neither moves during the live season.

No output carries a birth date or an age (``bios.py`` rule).
"""

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from eurohoops.eval.common import round_finite
from eurohoops.eval.m6_backtest import (
    M6Inputs,
    TargetInputs,
    World,
    live_inputs,
    project_cell,
    scale_intervals,
)
from eurohoops.live_sim import completed_rounds
from eurohoops.models.player_seasons import PROJECTED_STATS, person_ids
from eurohoops.models.similarity import BOX_FEATURES, SHOT_FEATURES
from eurohoops.stats.export import display_name

AGE_KEYS = re.compile(r"(^age$|_age$|^age_|birth|born|dob)", re.IGNORECASE)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DIGITS = 4


def person_names(el_players: pd.DataFrame, xwalk: pd.DataFrame) -> dict[str, str]:
    """Person id -> display name: the EuroLeague box-score spelling (``stats.box`` lines, the
    last line of each id)."""
    names: dict[str, str] = {}
    if not el_players.empty:
        last_line = el_players.drop_duplicates("player_id", keep="last")
        ids = person_ids(last_line["player_id"], "euroleague", xwalk)["person_id"]
        names.update(
            {pid: display_name(str(n)) for pid, n in zip(ids, last_line["player"], strict=True)}
        )
    return names


def personal_fields(node: Any, path: str = "$") -> list[str]:
    """Every key of ``node`` (a JSON payload) that names an age or a birth date, and every string
    value that is an ISO date alone (the shape of a birth date; a time stamp with a time is a
    tip-off or a cutoff): a report must have none (``bios.py`` rule, L-e)."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if AGE_KEYS.search(str(key)):
                found.append(f"{path}.{key}")
            found += personal_fields(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += personal_fields(value, f"{path}[{i}]")
    elif isinstance(node, str) and ISO_DATE.match(node):
        found.append(f"{path} = {node}")
    return found


def live_checkpoint(regular: pd.DataFrame, rounds: int, checkpoints: Sequence[float]) -> float:
    """The largest of 0 and ``checkpoints`` whose k = floor(f R) regular-season rounds are all
    played (D22). ``regular``: the live season's regular-season games with ``round`` and
    ``played``."""
    done = completed_rounds(regular)
    return max(f for f in (0.0, *checkpoints) if math.floor(f * rounds) <= done)


def live_people(complete: pd.DataFrame, competition: str, season: int) -> list[str]:
    """Persons with a group-stage line with seconds in ``competition``'s live season."""
    rows = complete[
        (complete["competition"] == competition)
        & (complete["season"] == season)
        & (complete["games"] > 0)
    ]
    return sorted(rows["person_id"].unique())


def live_projections(
    inputs: M6Inputs,
    competition: str,
    season: int,
    checkpoint: float,
    people: Sequence[str],
    *,
    chosen: Mapping[str, Any],
    scale: Mapping[str, float],
    spec: Any,
    rounds: int,
    world: World,
) -> tuple[pd.DataFrame, TargetInputs]:
    """The chosen cell's projections (long, ``PROJECTIONS_SCHEMA``) of ``people`` with the
    frozen D19 ``scale`` applied to their intervals, and the block's inputs."""
    ti = live_inputs(
        inputs,
        competition,
        season,
        checkpoint,
        people,
        spec=spec,
        rounds=lambda _c, _s: rounds,
        world=world,
        with_curve=False,
    )
    rows = project_cell(ti, str(chosen["variant"]), float(chosen["half_life"]))
    return scale_intervals(rows, scale, spec.interval), ti


def inputs_digest(blocks: Sequence[TargetInputs]) -> str:
    """sha256 of what the projections are a function of: each block's history, targets, impact
    rows and drift (not the schedule: a newly scheduled game moves nothing)."""
    h = hashlib.sha256()
    for ti in blocks:
        for frame in (ti.history, ti.targets, ti.impact):
            if frame is not None:
                h.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
        extra = {"drift": sorted(ti.drift.items())}
        h.update(json.dumps(extra, sort_keys=True).encode())
    return h.hexdigest()


def player_rows(
    projections: pd.DataFrame,
    seasons: pd.DataFrame,
    names: Mapping[str, str],
) -> list[dict[str, Any]]:
    """One report row per projected person: team and debut from the live season's I1 rows
    (``seasons``), each stat's mean and 80% interval (a stat without a mean is left out),
    the decayed possessions and seasons behind the points projection, the flags."""
    meta = {(str(r["person_id"]), str(r["competition"])): r for r in seasons.to_dict("records")}
    grouped: dict[tuple[str, str], list[dict[Any, Any]]] = {}
    for r in projections.to_dict("records"):
        grouped.setdefault((str(r["person_id"]), str(r["competition"])), []).append(r)
    out = []
    for key in sorted(grouped):
        rows, row = grouped[key], meta[key]
        stats = {
            str(r["stat"]): {
                "mean": round_finite(r["mean"], DIGITS),
                "lo80": round_finite(r["lo80"], DIGITS),
                "hi80": round_finite(r["hi80"], DIGITS),
            }
            for r in rows
            if math.isfinite(r["mean"])
        }
        pts = next(r for r in rows if r["stat"] == "pts")
        flags = sorted({f for r in rows for f in str(r["flags"]).split("|") if f})
        out.append(
            {
                "person_id": key[0],
                "competition": key[1],
                "team": str(row["team"]),
                "name": names.get(key[0], key[0]),
                "debut_season": int(row["debut_season"]),
                "stats": stats,
                "exposure": round_finite(float(pts["exposure"]), DIGITS),
                "n_seasons": int(pts["n_seasons"]),
                "flags": flags,
            }
        )
    return out


def projections_report(
    *,
    chosen: Mapping[str, Any],
    gate_passed: bool,
    season: int,
    checkpoints: Mapping[str, float],
    digest: str,
    players: list[dict[str, Any]],
) -> dict[str, Any]:
    """``reports/m6_projections.json`` (the shape the read model serves)."""
    return {
        "model": "m6",
        "variant": str(chosen["variant"]),
        "half_life": float(chosen["half_life"]),
        "gated": True,
        "gate_passed": gate_passed,
        "season": season,
        "checkpoint": checkpoints["euroleague"],
        "checkpoints": dict(checkpoints),
        "data_sha256": digest,
        "stats": list(PROJECTED_STATS),
        "players": players,
    }


def similarity_report(
    similar: pd.DataFrame,
    season: int,
    pool_seasons: Sequence[int],
    shot_features: bool,
    names: Mapping[str, str],
) -> dict[str, Any]:
    """``reports/m6_similarity.json``: per live person his ``neighbours`` rows (``SIMILAR_SCHEMA``)
    as the match's person, competition, season, name and score, with his query season."""
    players: dict[str, list[dict[str, Any]]] = {}
    for r in similar.sort_values(["person_id", "rank"]).to_dict("records"):
        match = str(r["match_person_id"])
        players.setdefault(str(r["person_id"]), []).append(
            {
                "rank": int(r["rank"]),
                "person_id": match,
                "competition": str(r["match_competition"]),
                "season": int(r["match_season"]),
                "name": names.get(match, match),
                "score": round_finite(float(r["score"]), DIGITS),
                "query_season": int(r["season"]),
            }
        )
    el = [*BOX_FEATURES, *(SHOT_FEATURES if shot_features else ())]
    return {
        "model": "m6",
        "season": season,
        "features": {"euroleague": el},
        "pool_seasons": sorted(int(s) for s in pool_seasons),
        "players": players,
    }


def query_rows(
    complete: pd.DataFrame, people: Sequence[str], before: int, min_poss: float
) -> pd.DataFrame:
    """Each live person's newest complete season before ``before`` with ``min_poss``
    possessions (his "plays like" query); a person without one has none."""
    rows = complete[
        complete["person_id"].isin(set(people))
        & (complete["season"] < before)
        & (complete["poss"] >= min_poss)
        & ~complete["partial"]
    ]
    rows = rows.sort_values(["person_id", "season", "poss"], kind="stable")
    return rows.drop_duplicates("person_id", keep="last").reset_index(drop=True)
