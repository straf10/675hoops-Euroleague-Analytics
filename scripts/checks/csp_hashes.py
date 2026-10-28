"""F-03 drift check: every executable inline script, style and event handler in the built site must
have its hash in the served Content-Security-Policy-Report-Only header.

Usage: python3 scripts/checks/csp_hashes.py SITE_DIR HEADERS_FILE

A stale hash only shows up as a browser report, so the daily job runs this right after the site
build and prints one GitHub warning per missing hash. It always exits 0: a warning, never a failed
day. Standard library only, so the build-site job runs it with the runner's python3.
"""

import base64
import collections
import hashlib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

TITLE = "CSP hash drift"
REPORT_ONLY = "Content-Security-Policy-Report-Only"


def csp_hash(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


class _Collect(HTMLParser):
    """The executable inline blocks of one page: (kind, hash-source text)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.blocks: list[tuple[str, str]] = []
        self.current: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        for name, value in attrs:
            if name.startswith("on") and value is not None:
                self.blocks.append(("handler", value))
        if tag == "script" and not a.get("src"):
            kind = (a.get("type") or "").lower()
            if kind.startswith("application/") or kind == "application/json":
                return  # data blocks (JSON-LD, embedded JSON): the browser does not run them
            self.current = ("script", [])
        elif tag == "style":
            self.current = ("style", [])

    def handle_endtag(self, tag: str) -> None:
        if self.current is not None and tag in ("script", "style"):
            kind, parts = self.current
            self.blocks.append((kind, "".join(parts)))
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current[1].append(data)


def inline_blocks(html: str) -> list[tuple[str, str]]:
    parser = _Collect()
    parser.feed(html)
    parser.close()
    return parser.blocks


def declared_hashes(headers_text: str) -> set[str]:
    """Every sha256 in the Report-Only header of the _headers file (any path rule)."""
    found: set[str] = set()
    for line in headers_text.splitlines():
        if line.strip().startswith(f"{REPORT_ONLY}:"):
            found.update(re.findall(r"'(sha256-[A-Za-z0-9+/=]+)'", line))
    return found


def check(site: Path, headers: Path) -> list[str]:
    """Warning messages, one per hash the built site uses that the headers file does not declare."""
    pages = sorted(site.rglob("*.html"))
    if not pages or not headers.is_file():
        return [f"no built pages under {site} or no headers file at {headers}"]
    declared = declared_hashes(headers.read_text(encoding="utf-8"))
    used: dict[str, tuple[str, collections.Counter[str]]] = {}
    for page in pages:
        rel = page.relative_to(site).as_posix()
        for kind, text in inline_blocks(page.read_text(encoding="utf-8")):
            digest = csp_hash(text)
            kind_seen, pages_seen = used.setdefault(digest, (kind, collections.Counter()))
            pages_seen[rel] += 1
            used[digest] = (kind_seen, pages_seen)
    messages = []
    for digest, (kind, pages_seen) in sorted(used.items()):
        if digest in declared:
            continue
        first = pages_seen.most_common(1)[0][0]
        messages.append(
            f"{kind} {digest} is on {sum(pages_seen.values())} block(s), "
            f"e.g. {first}, and not in {REPORT_ONLY}; update web/public/_headers"
        )
    return messages


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: csp_hashes.py SITE_DIR HEADERS_FILE", file=sys.stderr)
        return 2
    messages = check(Path(argv[1]), Path(argv[2]))
    for message in messages:
        print(f"::warning title={TITLE}::{message}")
    if not messages:
        print(f"CSP hashes: every inline block in {argv[1]} is declared")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
