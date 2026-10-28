"""The rule-1 guard (tests/prediction_guard.py) detects each kind of change, on a tmp folder."""

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.prediction_guard import _predictions_state


def _tree(root: Path) -> None:
    (root / "sub").mkdir(parents=True)
    (root / "log.csv").write_bytes(b"a,b\n1,2\n")
    (root / "sub" / "other.csv").write_bytes(b"x\n")


def _added(root: Path) -> None:
    (root / "new.csv").write_bytes(b"n\n")


def _appended(root: Path) -> None:
    with (root / "log.csv").open("ab") as fh:
        fh.write(b"3")


def _removed(root: Path) -> None:
    (root / "sub" / "other.csv").unlink()


@pytest.mark.parametrize(
    "change",
    [_added, _appended, _removed],
    ids=["added", "appended", "removed"],
)
def test_the_guard_detects_each_kind_of_change(
    tmp_path: Path, change: Callable[[Path], None]
) -> None:
    root = tmp_path / "predictions"
    _tree(root)
    before = _predictions_state(root)
    assert set(before) == {"log.csv", "sub/other.csv"}
    assert _predictions_state(root) == before  # reading changes nothing
    change(root)
    assert _predictions_state(root) != before
