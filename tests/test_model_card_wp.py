"""Every number in the in-game WP card matches the committed report (the M7 card check).

Report keys hold dots (the games-by-season keys, the CI indices), so the card's paths separate
keys with "/". The card's version line must equal the version in the report.
"""

import json
import re
from pathlib import Path
from typing import Any

from tests.test_model_card_m4 import DECIMAL, MINUS, shown

REPO = Path(__file__).parent.parent
DOC = REPO / "docs" / "models" / "wp_card.md"
REPORT = REPO / "reports" / "backtest_wp.json"
ROW = re.compile(
    r"^\| (?P<label>[^|]+) \| (?P<value>[^|]+) \| `(?P<file>[\w.]+):(?P<path>[\w./-]+)` \|$"
)
VERSION = re.compile(r"`(0\.2\.0\+wp\.[0-9a-f]{8})`")


def rows() -> list[dict[str, str]]:
    return [
        m.groupdict()
        for line in DOC.read_text(encoding="utf-8").splitlines()
        if (m := ROW.match(line))
    ]


def lookup(report: Any, path: str) -> Any:
    for key in path.split("/"):
        report = report[int(key)] if isinstance(report, list) else report[key]
    return report


def test_every_table_value_matches_its_report_path() -> None:
    table = rows()
    assert len(table) >= 25
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    wrong = []
    for r in table:
        assert r["file"] == "backtest_wp.json"
        value = r["value"].strip().replace(MINUS, "-")
        got = shown(lookup(report, r["path"]), value)
        if got != value:
            wrong.append(f"{r['path']} doc {value} report {got}")
    assert wrong == []


def test_every_decimal_in_the_prose_is_a_table_value() -> None:
    prose = DOC.read_text(encoding="utf-8").split("## Numbers")[0].replace(MINUS, "-")
    values = {r["value"].strip().replace(MINUS, "-").lstrip("-") for r in rows()}
    missing = sorted({n for n in DECIMAL.findall(prose) if n.lstrip("-") not in values})
    assert missing == []


def test_card_version_is_the_report_version() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    found = VERSION.findall(DOC.read_text(encoding="utf-8"))
    assert found and set(found) == {report["version"]}
