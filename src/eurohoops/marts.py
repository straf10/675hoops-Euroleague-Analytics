"""DuckDB marts: staging Parquet -> ``data/marts/eurohoops.duckdb``.

``backtest``, ``predict``, ``score`` and ``publish`` read games and teams from here.
"""

import gzip
import json
from pathlib import Path

import duckdb
import pandas as pd

from eurohoops.config import EUROLEAGUE
from eurohoops.parse.games import TEAMS_SCHEMA, conform


def _sql(path: Path, **files: Path) -> str:
    """Fill ``{name}`` placeholders with quoted paths (all paths come from config, not users)."""
    return path.read_text(encoding="utf-8").format(
        **{name: "'" + file.as_posix() + "'" for name, file in files.items()}
    )


def build_marts(mart_path: Path, sql_dir: Path) -> None:
    """(Re)build the games and teams marts from the EuroLeague staging files."""
    mart_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(mart_path)) as con:
        con.execute(
            _sql(
                sql_dir / "games.sql",
                euroleague_games=EUROLEAGUE.staging_games,
                euroleague_teams=EUROLEAGUE.staging_teams,
            )
        )


def data_volume(mart_path: Path, playbyplay_dir: Path | None = None) -> dict[str, int]:
    """The site's headline data counts, EuroLeague only, read from the marts and the cache.

    ``games``: played EuroLeague games that were not forfeits. ``seasons``: the distinct seasons
    of those games. ``shots_with_coordinates``: rows of the ``shots`` mart with both coordinates
    (that mart holds EuroLeague shots only); left out when that mart was never built. ``actions``:
    play-by-play entries across the cached EuroLeague files in ``playbyplay_dir`` (see
    ``playbyplay_actions``); left out when no directory is given.
    """
    with duckdb.connect(str(mart_path), read_only=True) as con:
        games = con.execute(
            "SELECT count(*), count(DISTINCT season) FROM games "
            "WHERE competition = 'euroleague' AND played AND NOT coalesce(forfeit, FALSE)"
        ).fetchone()
        has_shots = "shots" in {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        shots_sql = "SELECT count(*) FROM shots WHERE x IS NOT NULL AND y IS NOT NULL"
        shots = con.execute(shots_sql).fetchone() if has_shots else None
    assert games is not None  # a count(*) always returns one row
    volume = {"games": int(games[0]), "seasons": int(games[1])}
    if shots is not None:  # the shots mart is optional (never built without play-by-play)
        volume["shots_with_coordinates"] = int(shots[0])
    if playbyplay_dir is not None:
        volume["actions"] = playbyplay_actions(playbyplay_dir)
    return volume


def playbyplay_actions(playbyplay_dir: Path) -> int:
    """Play-by-play entries in the cached files: each dict with a ``PLAYTYPE`` key, in every list.

    The files are ``E<season>/<code>.json.gz``, one JSON object per game whose period lists hold
    the rows. About 13 s for the whole EuroLeague cache (5,070 files), so it runs in the publish
    step only, never in ``export-stats --from-cache``.
    """
    total = 0
    for path in sorted(playbyplay_dir.glob("E*/*.json.gz")):
        game = json.loads(gzip.decompress(path.read_bytes()))
        for rows in game.values():
            if isinstance(rows, list):
                total += sum(1 for row in rows if isinstance(row, dict) and "PLAYTYPE" in row)
    return total


def write_tables(mart_path: Path, tables: dict[str, pd.DataFrame]) -> None:
    """Create or replace mart tables from frames (names come from code, never from users)."""
    with duckdb.connect(str(mart_path)) as con:
        for name, frame in tables.items():
            con.register("frame", frame)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM frame")
            con.unregister("frame")


def read_table(mart_path: Path, name: str, competition: str | None = None) -> pd.DataFrame | None:
    """A mart table (optionally one competition's rows) in its stored row order.

    None when the table does not exist (e.g. the stints mart was never built).
    """
    with duckdb.connect(str(mart_path), read_only=True) as con:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if name not in tables:
            return None
        con.execute("SET TimeZone = 'UTC'")
        if competition is None:
            return con.execute(f"SELECT * FROM {name}").df()
        return con.execute(f"SELECT * FROM {name} WHERE competition = ?", [competition]).df()


def _query(mart_path: Path, sql: str, competition: str) -> pd.DataFrame:
    with duckdb.connect(str(mart_path), read_only=True) as con:
        con.execute("SET TimeZone = 'UTC'")
        return con.execute(sql, [competition]).df()


def read_games(mart_path: Path, competition: str) -> pd.DataFrame:
    games = _query(mart_path, "SELECT * FROM games WHERE competition = ?", competition)
    return conform(games.drop(columns="competition"))


def read_teams(mart_path: Path, competition: str) -> pd.DataFrame:
    teams = _query(mart_path, "SELECT team, name FROM teams WHERE competition = ?", competition)
    return TEAMS_SCHEMA.validate(teams.astype(str))
