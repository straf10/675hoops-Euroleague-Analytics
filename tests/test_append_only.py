"""Rule 1: the public logs only grow. The check runs on a temporary git repo that holds a real
committed log (odds/api_calls.csv); each planted edit must be caught and a plain append must not."""

import importlib.util
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

from tests.conftest import REPO

LOG = "odds/api_calls.csv"


def _load_check() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "append_only", REPO / "scripts/checks/append_only.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo_with_log(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "odds").mkdir(parents=True)
    shutil.copyfile(REPO / LOG, repo / LOG)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "base")
    return repo


def test_unchanged_log_passes(tmp_path: Path) -> None:
    check = _load_check()
    repo = _repo_with_log(tmp_path)
    assert check.violations(repo, "HEAD") == []


def test_appended_rows_pass(tmp_path: Path) -> None:
    check = _load_check()
    repo = _repo_with_log(tmp_path)
    with (repo / LOG).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("2026-10-28T09:00:00Z,200,3,9,491,3,0\n")
    assert check.violations(repo, "HEAD") == []


def test_a_planted_edit_to_an_old_row_is_caught(tmp_path: Path) -> None:
    check = _load_check()
    repo = _repo_with_log(tmp_path)
    path = repo / LOG
    data = path.read_bytes()
    assert data.count(b",200,3,3,497,3,0") == 1  # the first real data row
    path.write_bytes(data.replace(b",200,3,3,497,3,0", b",200,3,3,498,3,0"))
    problems = check.violations(repo, "HEAD")
    assert len(problems) == 1 and problems[0].startswith(f"{LOG}: changed at byte ")


def test_a_removed_last_row_is_caught(tmp_path: Path) -> None:
    check = _load_check()
    repo = _repo_with_log(tmp_path)
    path = repo / LOG
    lines = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(b"".join(lines[:-1]))
    problems = check.violations(repo, "HEAD")
    assert len(problems) == 1 and "truncated" in problems[0]


def test_a_deleted_log_is_caught(tmp_path: Path) -> None:
    check = _load_check()
    repo = _repo_with_log(tmp_path)
    (repo / LOG).unlink()
    problems = check.violations(repo, "HEAD")
    assert len(problems) == 1 and problems[0].startswith(f"{LOG}: deleted")


def test_a_new_log_file_is_not_a_violation(tmp_path: Path) -> None:
    check = _load_check()
    repo = _repo_with_log(tmp_path)
    (repo / "predictions").mkdir()
    (repo / "predictions" / "new_season.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert check.violations(repo, "HEAD") == []
