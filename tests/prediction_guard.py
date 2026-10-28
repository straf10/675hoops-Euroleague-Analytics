"""Rule 1 of CLAUDE.md (logs are append-only) as a test guard. Import the fixture into any test
module that calls live-path code, and point every prediction log of that test at tmp_path."""

from collections.abc import Iterator

import pytest

from tests.conftest import REPO


def _predictions_state() -> dict[str, tuple[int, int]]:
    """Size and mtime of every file under the repo predictions/, subfolders included."""
    state = {}
    for path in (REPO / "predictions").rglob("*"):
        if path.is_file():
            info = path.stat()
            state[path.relative_to(REPO).as_posix()] = (info.st_size, info.st_mtime_ns)
    return state


@pytest.fixture(autouse=True)
def real_prediction_logs_untouched() -> Iterator[None]:
    """Fails the test if any file under the repo's predictions/ is added, removed or changed."""
    before = _predictions_state()
    yield
    assert _predictions_state() == before
