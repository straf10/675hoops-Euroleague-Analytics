"""The public records the pipeline commits: append-only CSV logs (predictions, odds, odds calls),
whose rows are only ever appended, and the JSON reports."""

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

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


def displayed_rows(log: pd.DataFrame) -> pd.DataFrame:
    """The one log row shown for each game, with a ``late`` flag (stamped at or after tip-off).

    That is the latest row stamped before the game's tip-off, so a game re-logged before tip-off
    shows its newest pick. A game with only late rows keeps its earliest one: the moment it was
    first logged late. Late rows are shown ("Logged late") and never scored. The site build and
    the API both read the log through this, so they cannot disagree on which row a game shows.
    """
    stamps = pd.to_datetime(log["predicted_at_utc"], utc=True)
    tips = pd.to_datetime(log["tipoff_utc"], utc=True)
    marked = log.assign(late=stamps >= tips, _stamp=stamps)
    by_stamp = marked.sort_values("_stamp", kind="stable")
    on_time = by_stamp[~by_stamp["late"]].drop_duplicates("game_id", keep="last")
    after = by_stamp[by_stamp["late"]].drop_duplicates("game_id", keep="first")
    after = after[~after["game_id"].isin(on_time["game_id"])]
    return pd.concat([on_time, after]).drop(columns="_stamp")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """A JSON report, indented, LF line endings, so reruns diff cleanly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
