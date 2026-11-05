"""Player pages, the RAPM board and projections."""

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pandera.pandas as pa

from eurohoops.api.read.store import NotFound, Store, cached, check_rows, jsonable
from eurohoops.config import (
    EUROLEAGUE,
    M2_PLAYERS_REPORT,
    M3_PLAYERS_REPORT,
    M6_PROJECTIONS,
    M6_SIMILARITY,
    MART_PATH,
    PLAYER_XWALK_FILE,
)
from eurohoops.live_m6 import person_names
from eurohoops.marts import read_table
from eurohoops.models.player_seasons import (
    COUNT_COLUMNS,
    COUNT_STATS,
    PCT_STATS,
    build_player_seasons,
    person_ids,
    rate_table,
    read_xwalk_file,
)
from eurohoops.parse.schemas import validated

M3_ROWS_SCHEMA = pa.DataFrameSchema(
    {
        "player_id": pa.Column(str),
        "season": pa.Column("int64"),
        "total": pa.Column("float64"),
        "sd_total": pa.Column("float64"),
        "minutes": pa.Column("float64", pa.Check.ge(0.0)),
        "games": pa.Column("int64", pa.Check.ge(0)),
    },
    strict=False,
)


M2_ROWS_SCHEMA = pa.DataFrameSchema(
    {
        "shooter": pa.Column(str),
        "season": pa.Column("int64"),
        "split": pa.Column(str),
        "fga": pa.Column("int64", pa.Check.ge(0)),
        "shrunk": pa.Column("float64"),
    },
    strict=False,
)


PROJECTION_ROWS_SCHEMA = pa.DataFrameSchema(
    {
        "person_id": pa.Column(str),
        "competition": pa.Column(str, pa.Check.isin([EUROLEAGUE.name])),
        "team": pa.Column(str),
        "name": pa.Column(str),
        "debut_season": pa.Column("int64"),
        "exposure": pa.Column("float64", pa.Check.ge(0.0)),
        "n_seasons": pa.Column("int64", pa.Check.ge(0)),
    },
    strict=False,
)


SIMILAR_ROWS_SCHEMA = pa.DataFrameSchema(
    {
        "rank": pa.Column("int64", pa.Check.ge(1)),
        "person_id": pa.Column(str),
        "competition": pa.Column(str, pa.Check.isin([EUROLEAGUE.name])),
        "season": pa.Column("int64"),
        "name": pa.Column(str),
        "score": pa.Column("float64"),
    },
    strict=False,
)


@cached
def _xwalk(store: Store) -> pd.DataFrame:
    """The committed crosswalk file (D25; what CI has), else the ``player_xwalk`` mart."""
    if store.path(PLAYER_XWALK_FILE).exists():
        return read_xwalk_file(store.path(PLAYER_XWALK_FILE))
    found = read_table(store.mart(), "player_xwalk") if store.path(MART_PATH).exists() else None
    if found is None:
        return pd.DataFrame(columns=["person_id", "competition", "source_id"])
    return found


@cached
def _player_seasons(store: Store) -> pd.DataFrame:
    try:
        games = {"euroleague": store.euroleague_box().players}
        return build_player_seasons(games, _xwalk(store))
    except ValueError as empty:
        raise NotFound(f"no box scores are cached: {empty}") from empty


@cached
def _person_names(store: Store) -> dict[str, str]:
    """Person id -> display name: the EuroLeague box-score spelling."""
    return person_names(store.euroleague_box().players, _xwalk(store))


@dataclass(frozen=True)
class Impact:
    units: str
    rows: dict[str, list[dict[str, Any]]]  # person id -> one dict per season


@cached
def _m3_index(store: Store) -> Impact | None:
    report = store.report(M3_PLAYERS_REPORT)
    if report is None:
        return None
    records = [
        {"season": int(season), **p}
        for season, snapshot in report["seasons"].items()
        for p in snapshot["players"]
    ]
    frame = validated(pd.DataFrame(records, columns=list(M3_ROWS_SCHEMA.columns)), M3_ROWS_SCHEMA)
    ids = person_ids(frame["player_id"], "euroleague", _xwalk(store))["person_id"]
    keep = (
        "season",
        "o",
        "d",
        "total",
        "sd_total",
        "ci90_o",
        "ci90_d",
        "ci90_total",
        "minutes",
        "games",
        "seen",
    )
    rows: dict[str, list[dict[str, Any]]] = {}
    for pid, record in zip(ids, records, strict=True):
        rows.setdefault(pid, []).append({k: record[k] for k in keep})
    return Impact(str(report["units"]), rows)


# The RAPM leaderboard's floor: box minutes in the rated season. Under it a player has a rating
# and an interval, but no rank and no row in the table (about one rotation player in three is
# above it; the caption of the Leaders table states the same number).
RAPM_MIN_MINUTES = 500.0


def rapm_board(store: Store) -> dict[str, Any]:
    """The latest M3 season's EuroLeague ratings: every player the stints rated, by total, with his
    90% intervals and his rank among the players at ``RAPM_MIN_MINUTES`` (``rank`` null below
    it). Nothing is fitted here."""
    report = store.required_report(M3_PLAYERS_REPORT, "the M3 player ratings")
    season = max(int(s) for s in report["seasons"])
    records = [
        {"season": season, **p} for p in report["seasons"][str(season)]["players"] if p["seen"]
    ]
    frame = validated(pd.DataFrame(records, columns=list(M3_ROWS_SCHEMA.columns)), M3_ROWS_SCHEMA)
    ids = person_ids(frame["player_id"], "euroleague", _xwalk(store))["person_id"]
    names = _person_names(store)
    players = [
        {
            "person_id": pid,
            "name": names.get(pid, pid),
            "team": p["teams"][-1],
            "o": p["o"],
            "d": p["d"],
            "total": p["total"],
            "ci90_o": p["ci90_o"],
            "ci90_d": p["ci90_d"],
            "ci90_total": p["ci90_total"],
            "minutes": p["minutes"],
            "games": p["games"],
            "rank": None,
        }
        for pid, p in zip(ids, records, strict=True)
    ]
    players.sort(key=lambda r: -r["total"])
    place = 0
    for r in players:
        if r["minutes"] >= RAPM_MIN_MINUTES:
            place += 1
            r["rank"] = place
    out: dict[str, Any] = jsonable(
        {
            "model": "m3",
            "variant": report["variant"],
            "units": report["units"],
            "interval": report["interval"],
            "season": season,
            "minimum_minutes": RAPM_MIN_MINUTES,
            "players": players,
        }
    )
    return out


@cached
def _m2_index(store: Store) -> Impact | None:
    report = store.report(M2_PLAYERS_REPORT)
    if report is None:
        return None
    records = report["players"]
    frame = validated(pd.DataFrame(records, columns=list(M2_ROWS_SCHEMA.columns)), M2_ROWS_SCHEMA)
    ids = person_ids(frame["shooter"], "euroleague", _xwalk(store))["person_id"]
    rows: dict[str, list[dict[str, Any]]] = {}
    for pid, r in zip(ids, records, strict=True):
        rows.setdefault(pid, []).append(
            {
                "season": r["season"],
                "split": r["split"],
                "fga": r["fga"],
                "shot_making": r["shrunk"],
                "ci90": r["ci90"],
            }
        )
    return Impact(str(report["units"]), rows)


def player(store: Store, person_id: str) -> dict[str, Any]:
    """One person's seasons (box totals, per-100 rates, shooting percentages), his M3 impact
    snapshots and M2 shot-making; the impact blocks are null for a person they do not cover."""
    frame = _player_seasons(store)
    rows = frame[frame["person_id"] == person_id]
    if rows.empty:
        raise NotFound(f"unknown person_id '{person_id}'")
    rows = rows.sort_values(["season", "competition"])
    rates = rate_table(rows)
    seasons = []
    for row, rate in zip(rows.to_dict("records"), rates.to_dict("records"), strict=True):
        seasons.append(
            {
                "competition": row["competition"],
                "season": int(row["season"]),
                "partial": bool(row["partial"]),
                "team": row["team"],
                "games": int(row["games"]),
                "minutes": float(row["minutes"]),
                "poss": float(row["poss"]),
                "totals": {c: int(row[c]) for c in COUNT_COLUMNS},
                "per100": {s: rate[s] for s in COUNT_STATS},
                "pct": {s: rate[s] for s in PCT_STATS},
            }
        )
    m3, m2 = _m3_index(store), _m2_index(store)
    out: dict[str, Any] = jsonable(
        {
            "person_id": person_id,
            "name": _person_names(store).get(person_id, person_id),
            "debut_season": int(rows["debut_season"].iloc[0]),
            "seasons": seasons,
            "impact": None
            if m3 is None or person_id not in m3.rows
            else {"model": "m3", "units": m3.units, "seasons": m3.rows[person_id]},
            "shot_making": None
            if m2 is None or person_id not in m2.rows
            else {"model": "m2", "units": m2.units, "seasons": m2.rows[person_id]},
        }
    )
    return out


@cached
def _checked_projections(store: Store) -> dict[str, Any]:
    """The M6 projections report; its whole list is validated once per Store, not once per person
    (the export asks for each)."""
    report = store.required_report(M6_PROJECTIONS, "the M6 projections")
    check_rows(report["players"], PROJECTION_ROWS_SCHEMA)
    return report


def player_projection(store: Store, person_id: str) -> dict[str, Any]:
    report = _checked_projections(store)
    rows = [
        p
        for p in report["players"]
        if p["person_id"] == person_id and p["competition"] == EUROLEAGUE.name
    ]
    if not rows:
        raise NotFound(
            f"no M6 projection for person_id '{person_id}' "
            f"(not in the {report['season']} projected set)"
        )
    keys = (
        "model",
        "variant",
        "half_life",
        "gated",
        "gate_passed",
        "season",
        "checkpoint",
        "data_sha256",
        "stats",
    )
    return {**{k: report[k] for k in keys}, "projections": rows}


def player_similar(store: Store, person_id: str) -> dict[str, Any]:
    report = store.required_report(M6_SIMILARITY, "the M6 similarity lists")
    if person_id not in report["players"]:
        raise NotFound(f"no similarity list for person_id '{person_id}'")
    rows = report["players"][person_id]
    check_rows(rows, SIMILAR_ROWS_SCHEMA)
    rows = [r for r in rows if r["competition"] == EUROLEAGUE.name]
    return {
        "model": report["model"],
        "season": report["season"],
        "person_id": person_id,
        "features": {EUROLEAGUE.name: report["features"][EUROLEAGUE.name]},
        "pool_seasons": report["pool_seasons"],
        "similar": rows,
    }
