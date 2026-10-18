"""Text must not touch a link across a line break in web/src/**/*.astro.

Astro's HTML compression drops the newline and indentation between two lines of markup, so
``use`` then a line break then ``<a ...>GitHub</a>`` renders as "useGitHub". The same happens
after a closing ``</a>`` when a word follows on the next line. Keep the text and the anchor on
one line, or write an explicit ``{" "}`` before the anchor."""

import re
from itertools import pairwise

from tests.conftest import REPO

WEB = REPO / "web" / "src"
WORD_BEFORE_LINK = re.compile(r"[\w,;:]$")
LINK_OPENS_NEXT = re.compile(r"^<a[ >]")
LINK_CLOSED_BEFORE_WORD = re.compile(r"</a>$")
WORD_OPENS_NEXT = re.compile(r"^[A-Za-z0-9]")


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(WEB.rglob("*.astro")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, (line, nxt) in enumerate(pairwise(lines), start=1):
            text, following = line.rstrip(), nxt.lstrip()
            glued_before = WORD_BEFORE_LINK.search(text) and LINK_OPENS_NEXT.match(following)
            glued_after = LINK_CLOSED_BEFORE_WORD.search(text) and WORD_OPENS_NEXT.match(following)
            if glued_before or glued_after:
                found.append(f"{path.relative_to(REPO).as_posix()}:{i}")
    return found


def test_no_word_is_glued_to_a_link_across_a_line_break() -> None:
    assert _offenders() == []
