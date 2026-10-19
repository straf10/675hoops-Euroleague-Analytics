"""Every value in the Numbers table of the candidate card matches the committed blend report."""

import json
import re
from typing import Any

import pytest

from tests.conftest import REPO

CARD = REPO / "docs" / "models" / "candidate_elo_blend.md"
REPORT = REPO / "reports" / "backtest_blend.json"
ROW = re.compile(
    r"^\| (?P<label>[^|]+) \| (?P<value>-?\d+(?:\.\d+)?) \| `(?P<file>[\w.]+):(?P<path>[\w.]+)` \|$"
)


def lookup(report: Any, path: str) -> Any:
    for key in path.split("."):
        report = report[int(key)] if isinstance(report, list) else report[key]
    return report


def card_rows() -> list[dict[str, str]]:
    return [
        m.groupdict()
        for line in CARD.read_text(encoding="utf-8").splitlines()
        if (m := ROW.match(line))
    ]


def test_the_numbers_table_is_not_empty() -> None:
    assert len(card_rows()) >= 20


@pytest.mark.parametrize("row", card_rows(), ids=lambda r: r["label"].strip())
def test_card_value_matches_report(row: dict[str, str]) -> None:
    assert row["file"] == REPORT.name
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    value = lookup(report, row["path"])
    decimals = len(row["value"].split(".")[1]) if "." in row["value"] else 0
    assert float(row["value"]) == pytest.approx(float(value), abs=0.5 * 10**-decimals + 1e-12)
