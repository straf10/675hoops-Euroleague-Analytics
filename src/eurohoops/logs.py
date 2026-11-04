"""The public records the pipeline commits: append-only CSV logs (predictions, odds, odds calls),
whose rows are only ever appended, and the JSON reports. Also the one reading of a forecast log
that decides which row of a game is shown and scored (GLOSSARY: pre-registered row)."""

import csv
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa

from eurohoops.parse.schemas import validated

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # UTC stamps in the logs, the reports and the site data


def require_terminated(path: Path) -> None:
    """Raise ValueError if ``path`` exists and its last row has no newline.

    A run killed mid-write or a hand edit can leave it so; the next row would be glued onto it.
    """
    if not path.exists() or not path.stat().st_size:
        return
    with path.open("rb") as fh:
        fh.seek(-1, 2)
        if fh.read() != b"\n":
            raise ValueError(f"{path} does not end with a newline; fix it by hand first")


def append_rows(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    """Append ``rows`` (a new or empty file gets the header first, even with no rows).

    Refuses a file whose last row is unterminated (``require_terminated``): nothing is written.
    """
    require_terminated(path)
    is_new = not path.exists() or not path.stat().st_size
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


# ---- reading a forecast log: which row of a game counts ----

LOG_SCHEMA = pa.DataFrameSchema(
    {
        "game_id": pa.Column(str),
        "season": pa.Column("int64"),
        "round": pa.Column("int64"),
        "phase": pa.Column(str),
        "tipoff_utc": pa.Column(str),
        "home": pa.Column(str),
        "away": pa.Column(str),
        "p_home": pa.Column("float64", pa.Check.in_range(0.0, 1.0)),
        "exp_margin": pa.Column("float64"),
        "model": pa.Column(str),
        "model_version": pa.Column(str),
        "predicted_at_utc": pa.Column(str),
    },
    strict=False,  # M1 and M5 rows carry extra forecast columns
)


def read_log(path: Path | None, columns: Sequence[str] | None = None) -> pd.DataFrame:
    """A forecast log, schema-checked (``LOG_SCHEMA``). A missing or empty file gives no rows,
    with ``columns`` (default: the schema's)."""
    if path is None or not path.exists() or not path.stat().st_size:
        frame = pd.DataFrame(columns=list(columns or LOG_SCHEMA.columns))
    else:
        frame = pd.read_csv(path, dtype={"game_id": str})
    return validated(frame, LOG_SCHEMA)


def _stamps(log: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Each row's stamp and its game's tip-off, as UTC datetimes."""
    return (
        pd.to_datetime(log["predicted_at_utc"], utc=True),
        pd.to_datetime(log["tipoff_utc"], utc=True),
    )


def is_late(log: pd.DataFrame) -> pd.Series:
    """Late rows: stamped at or after their game's tip-off. Never scored."""
    stamp, tipoff = _stamps(log)
    return stamp >= tipoff


def not_provable(log: pd.DataFrame, manual_pushes: Sequence[datetime]) -> pd.Series:
    """Rows stamped before tip-off that reached the public log only at or after it.

    A row became public at the first manual push at or after its stamp, else at its stamp (the
    daily workflow commits a row in the run that stamps it).
    """
    stamp, tipoff = _stamps(log)
    public = stamp.copy()
    for pushed in sorted(manual_pushes, reverse=True):
        public = public.where(stamp > pd.Timestamp(pushed), pd.Timestamp(pushed))
    return (stamp < tipoff) & (public >= tipoff)


def pre_registered_rows(log: pd.DataFrame) -> pd.DataFrame:
    """The pre-registered row of each game logged before its tip-off: its latest row stamped
    before tip-off, of the earliest model version that logged it (the version of its first row
    stamped before tip-off). A re-log before tip-off replaces the row; a new version does not."""
    stamp, tipoff = _stamps(log)
    on_time = (
        log[stamp < tipoff]
        .assign(_stamp=stamp[stamp < tipoff])
        .sort_values("_stamp", kind="stable")
    )
    first_version = on_time.groupby("game_id")["model_version"].transform("first")
    kept = on_time[on_time["model_version"] == first_version]
    return kept.drop_duplicates("game_id", keep="last").drop(columns="_stamp")


def scored_rows(log: pd.DataFrame, manual_pushes: Sequence[datetime]) -> pd.DataFrame:
    """The rows scored: each game's pre-registered row, when it is provable (public before
    tip-off). A game whose pre-registered row is not provable is not scored."""
    rows = pre_registered_rows(log)
    return rows[~not_provable(rows, manual_pushes)]


def displayed_rows(log: pd.DataFrame) -> pd.DataFrame:
    """The one row the site shows for each game, with a ``late`` flag.

    A game logged before tip-off shows its pre-registered row, the one that is scored. A game
    with only late rows shows its earliest one ("Logged late"), never scored. The site build and
    the API both read the log through this, so they cannot disagree on which row a game shows.
    """
    shown = pre_registered_rows(log).assign(late=False)
    stamp, _ = _stamps(log)
    after = log[is_late(log) & ~log["game_id"].isin(shown["game_id"])]
    first_late = (
        after.assign(_stamp=stamp[after.index], late=True)
        .sort_values("_stamp", kind="stable")
        .drop_duplicates("game_id", keep="first")
        .drop(columns="_stamp")
    )
    return pd.concat([shown, first_late])


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """A JSON report, indented, LF line endings, so reruns diff cleanly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
