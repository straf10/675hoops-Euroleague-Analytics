"""Rule 1 (CLAUDE.md): the public logs only grow. Each CSV tracked at BASE in predictions/, odds/ or
injuries/ must still start with exactly the bytes it had at BASE. An edited or removed row, a
truncated file or a deleted log is a violation.

Usage: python scripts/checks/append_only.py [BASE]   (BASE defaults to HEAD). Exit 1 on violations.
The daily job runs it on the checked-out commit before it commits the day's rows.
"""

import subprocess
import sys
from pathlib import Path

LOG_DIRS = ("predictions", "odds", "injuries")


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def tracked_logs(repo: Path, base: str) -> list[str]:
    listed = _git(repo, "ls-tree", "-r", "--name-only", base, "--", *LOG_DIRS).decode()
    return [p for p in listed.splitlines() if p.endswith(".csv")]


def violations(repo: Path, base: str) -> list[str]:
    problems: list[str] = []
    for rel in tracked_logs(repo, base):
        old = _git(repo, "show", f"{base}:{rel}")
        path = repo / rel
        if not path.exists():
            problems.append(f"{rel}: deleted ({len(old)} bytes at {base})")
            continue
        new = path.read_bytes()
        if new.startswith(old):
            continue
        first = next(
            (i for i, (a, b) in enumerate(zip(old, new, strict=False)) if a != b), len(new)
        )
        kind = "truncated" if old.startswith(new) else "changed"
        problems.append(f"{rel}: {kind} at byte {first} (an existing row was edited or removed)")
    return problems


def main(argv: list[str]) -> int:
    base = argv[1] if len(argv) > 1 else "HEAD"
    repo = Path(__file__).resolve().parents[2]
    problems = violations(repo, base)
    for line in problems:
        print(f"APPEND-ONLY VIOLATION: {line}", file=sys.stderr)
    if problems:
        return 1
    print(f"append-only: every log tracked at {base} is unchanged or only appended to")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
