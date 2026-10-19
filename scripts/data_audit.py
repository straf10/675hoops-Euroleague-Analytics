"""Print the cross-table data audit of the marts: one line per check, then offending examples.

Usage: uv run python scripts/data_audit.py [path/to/eurohoops.duckdb]
Reads only; it changes no data. Notes on each check say which counts are expected.
"""

import sys
from pathlib import Path

from eurohoops.audit import run_audit
from eurohoops.config import MART_PATH


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else MART_PATH
    findings = run_audit(str(path))
    for finding in findings:
        print(
            f"{finding.count:>6}  {finding.name}" + (f"  ({finding.note})" if finding.note else "")
        )
        for example in finding.examples:
            print(f"        {example}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
