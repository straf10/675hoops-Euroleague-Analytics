"""Glossary ids are anchors (/glossary/#id), so each must appear once."""

import re
from collections import Counter

from tests.conftest import REPO

GLOSSARY = REPO / "web" / "src" / "lib" / "glossary.ts"


def test_glossary_ids_are_unique() -> None:
    ids = re.findall(r'\bid: "([a-z0-9-]+)"', GLOSSARY.read_text(encoding="utf-8"))
    assert len(ids) > 50
    assert [i for i, n in Counter(ids).items() if n > 1] == []
