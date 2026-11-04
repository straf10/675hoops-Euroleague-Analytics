"""Which row of a forecast log a game shows and scores (``logs``: GLOSSARY "Pre-registered row").

One case table through the interface: ``displayed_rows`` (what the site and API show) and
``scored_rows`` (what the scorecard, forecasts and promotion test score) on the same log.
"""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from pandera.errors import SchemaError

from eurohoops.logs import (
    LOG_SCHEMA,
    displayed_rows,
    is_late,
    not_provable,
    pre_registered_rows,
    read_log,
    scored_rows,
)
from eurohoops.predict import LOG_COLUMNS

TIP = "2026-10-01T18:00:00Z"


def row(stamp: str, p_home: float, version: str = "v1", tipoff: str = TIP) -> dict[str, object]:
    return {
        "game_id": "G1",
        "season": 2026,
        "round": 1,
        "phase": "RS",
        "tipoff_utc": tipoff,
        "home": "AAA",
        "away": "BBB",
        "p_home": p_home,
        "exp_margin": 1.0,
        "model": "elo",
        "model_version": version,
        "predicted_at_utc": stamp,
    }


def push(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 1, hour, minute, tzinfo=UTC)


# (rows, manual pushes, shown (p_home, late), scored p_home or None)
CASES = {
    "re-logged before tip-off: the latest such row": (
        [
            row("2026-10-01T10:00:00Z", 0.6),
            row("2026-10-01T17:30:00Z", 0.7),
            row("2026-10-01T11:00:00Z", 0.5),
        ],
        (),
        (0.7, False),
        0.7,
    ),
    "two versions: the earliest version's row": (
        [row("2026-10-01T10:00:00Z", 0.6, "v1"), row("2026-10-01T12:00:00Z", 0.5, "v2")],
        (),
        (0.6, False),
        0.6,
    ),
    "the earliest version re-logged after a newer one: its latest row": (
        [
            row("2026-10-01T10:00:00Z", 0.6, "v1"),
            row("2026-10-01T11:00:00Z", 0.5, "v2"),
            row("2026-10-01T12:00:00Z", 0.65, "v1"),
        ],
        (),
        (0.65, False),
        0.65,
    ),
    "late only, several rows: the earliest late row, never scored": (
        [
            row("2026-10-01T20:00:00Z", 0.8),
            row("2026-10-01T19:00:00Z", 0.9),
            row("2026-10-01T21:00:00Z", 0.7),
        ],
        (),
        (0.9, True),
        None,
    ),
    "late and on time: the on-time row": (
        [row("2026-10-01T10:00:00Z", 0.6), row("2026-10-01T19:00:00Z", 0.9)],
        (),
        (0.6, False),
        0.6,
    ),
    "stamped exactly at tip-off: late": ([row(TIP, 0.5)], (), (0.5, True), None),
    "public only after tip-off (manual push): shown, not scored": (
        [row("2026-10-01T17:00:00Z", 0.6)],
        (push(18, 30),),
        (0.6, False),
        None,
    ),
    "an earlier provable row does not replace a non-provable pre-registered row": (
        [row("2026-10-01T10:00:00Z", 0.6), row("2026-10-01T17:00:00Z", 0.7)],
        (push(11), push(18, 30)),
        (0.7, False),
        None,
    ),
    "pushed before tip-off: provable": (
        [row("2026-10-01T17:00:00Z", 0.6)],
        (push(17, 30),),
        (0.6, False),
        0.6,
    ),
    "offset stamps compare as instants, not strings (17:30Z is on time)": (
        [row("2026-10-01T19:30:00+02:00", 0.6)],
        (),
        (0.6, False),
        0.6,
    ),
    "offset stamps compare as instants, not strings (18:30Z is late)": (
        [row("2026-10-01T10:00:00Z", 0.6), row("2026-10-01T17:30:00-01:00", 0.7)],
        (),
        (0.6, False),
        0.6,
    ),
}


@pytest.mark.parametrize("case", CASES)
def test_the_row_a_game_shows_and_scores(case: str) -> None:
    rows, pushes, shown, scored = CASES[case]
    log = pd.DataFrame(rows)
    (picked,) = displayed_rows(log).to_dict("records")
    assert (picked["p_home"], bool(picked["late"])) == shown
    counted = scored_rows(log, pushes)
    assert counted["p_home"].tolist() == ([] if scored is None else [scored])
    if not shown[1]:  # an on-time game shows the row it scores (when provable)
        assert pre_registered_rows(log)["p_home"].tolist() == [shown[0]]


def test_each_game_is_judged_on_its_own_tipoff() -> None:
    log = pd.DataFrame(
        [
            row("2026-10-01T10:00:00Z", 0.6),
            {**row("2026-10-01T10:00:00Z", 0.4, tipoff="2026-10-01T09:00:00Z"), "game_id": "G2"},
        ]
    )
    shown = displayed_rows(log).set_index("game_id")
    assert shown["late"].to_dict() == {"G1": False, "G2": True}
    assert is_late(log).tolist() == [False, True]
    assert scored_rows(log, ())["game_id"].tolist() == ["G1"]


def test_not_provable_marks_only_on_time_rows_pushed_at_or_after_tip_off() -> None:
    log = pd.DataFrame(
        [
            row("2026-10-01T09:00:00Z", 0.5),  # public at the 10:00 push
            row("2026-10-01T12:00:00Z", 0.5),  # public at the 18:00 push: at tip-off
            row("2026-10-01T19:00:00Z", 0.5),  # late, not "not provable"
        ]
    )
    assert not_provable(log, (push(10), push(18))).tolist() == [False, True, False]


def test_displayed_rows_keep_the_log_columns_and_index() -> None:
    log = pd.DataFrame([row("2026-10-01T10:00:00Z", 0.6), row("2026-10-01T19:00:00Z", 0.9)])
    shown = displayed_rows(log)
    assert list(shown.columns) == [*LOG_COLUMNS, "late"]
    assert shown.index.tolist() == [0]


def test_read_log_checks_the_schema(tmp_path: Path) -> None:
    empty = read_log(tmp_path / "missing.csv")
    assert empty.empty and list(empty.columns) == list(LOG_SCHEMA.columns)
    assert list(read_log(None, [*LOG_COLUMNS, "exp_total"]).columns)[-1] == "exp_total"
    path = tmp_path / "log.csv"
    pd.DataFrame([row("2026-10-01T10:00:00Z", 0.6)]).to_csv(path, index=False)
    assert read_log(path)["game_id"].tolist() == ["G1"]
    pd.DataFrame([row("2026-10-01T10:00:00Z", 1.6)]).to_csv(path, index=False)
    with pytest.raises(SchemaError):
        read_log(path)
