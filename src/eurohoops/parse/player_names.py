"""EuroLeague player names per competition, season and team, from ``stats/box.py``'s player lines.

The entity pass writes them to the ``player_names`` mart, which the site's player pages read.
"""

import pandas as pd
import pandera.pandas as pa

from eurohoops.parse.schemas import validated

COMPETITIONS = ("euroleague",)

PLAYER_NAMES_SCHEMA = pa.DataFrameSchema(
    {
        "competition": pa.Column(str, pa.Check.isin(COMPETITIONS)),
        "source_id": pa.Column(str),
        "season": pa.Column("int64"),
        "team": pa.Column(str),
        "jersey": pa.Column(str, nullable=True),
        "surname_raw": pa.Column(str),
        "first_raw": pa.Column(str),
        "games": pa.Column("int64", pa.Check.ge(0)),
        "minutes": pa.Column("float64", pa.Check.ge(0)),
    },
    unique=["competition", "source_id", "season", "team"],
    strict=True,
)


def _mode(values: pd.Series) -> str | None:
    counts = values.dropna().value_counts()
    if counts.empty:
        return None
    top = counts[counts == counts.max()].index
    return str(min(str(v) for v in top))


def _aggregate(lines: pd.DataFrame, competition: str) -> pd.DataFrame:
    """Lines (source_id season team jersey surname_raw first_raw seconds) -> name rows."""
    keys = ["source_id", "season", "team"]
    grouped = lines.groupby(keys, sort=True)
    spelling = lines.sort_values([*keys, "surname_raw", "first_raw"]).drop_duplicates(keys)
    rows = grouped.agg(
        games=("seconds", lambda s: int((s > 0).sum())),
        minutes=("seconds", lambda s: round(float(s.sum()) / 60.0, 2)),
    ).reset_index()
    rows["jersey"] = grouped["jersey"].agg(_mode).to_numpy()
    rows = rows.merge(spelling[[*keys, "surname_raw", "first_raw"]], on=keys, how="left")
    rows.insert(0, "competition", competition)
    return validated(rows[list(PLAYER_NAMES_SCHEMA.columns)], PLAYER_NAMES_SCHEMA)


def euroleague_names(players: pd.DataFrame) -> pd.DataFrame:
    """EuroLeague name rows from ``stats/box.py`` player lines (``player_id player dorsal team
    season sec``); ``player`` is ``SURNAME, NAME`` (no comma: all surname)."""
    split = players["player"].str.partition(", ")
    lines = pd.DataFrame(
        {
            "source_id": players["player_id"].astype(str),
            "season": players["season"].astype("int64"),
            "team": players["team"].astype(str),
            "jersey": players["dorsal"].where(players["dorsal"].astype(str).str.len() > 0),
            "surname_raw": split[0].str.strip(),
            "first_raw": split[2].str.strip(),
            "seconds": players["sec"].astype("int64"),
        }
    )
    return _aggregate(lines, "euroleague")
