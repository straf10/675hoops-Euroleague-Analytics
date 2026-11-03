"""F-03 drift check (scripts/checks/csp_hashes.py): a stale CSP hash fails the check.

The check runs on a small HTML page written to a temporary folder, so it needs no site build and
never skips: CI runs it with the same inputs as the daily job."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import REPO


def _load_check() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "csp_hashes", REPO / "scripts/checks/csp_hashes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_check()

PAGE = """<!doctype html>
<html><head>
<script>console.log("theme")</script>
<style>p{margin:0}</style>
<script type="application/ld+json">{"@type":"Thing"}</script>
</head><body>
<form onsubmit="return false"></form>
</body></html>
"""


def _site(tmp_path: Path, html: str = PAGE) -> Path:
    site = tmp_path / "site"
    (site / "about").mkdir(parents=True)
    (site / "about" / "index.html").write_text(html, encoding="utf-8")
    return site


def _headers(tmp_path: Path, hashes: list[str]) -> Path:
    sources = " ".join(f"'{h}'" for h in hashes)
    path = tmp_path / "_headers"
    path.write_text(
        f"/*\n  Content-Security-Policy: default-src 'self'; script-src 'self' {sources}\n",
        encoding="utf-8",
    )
    return path


SCRIPT = 'console.log("theme")'
STYLE = "p{margin:0}"
HANDLER = "return false"


def test_every_inline_block_declared_gives_no_warning(tmp_path: Path) -> None:
    site = _site(tmp_path)
    headers = _headers(
        tmp_path, [check.csp_hash(SCRIPT), check.csp_hash(STYLE), check.csp_hash(HANDLER)]
    )
    assert check.check(site, headers) == []


def test_an_undeclared_block_is_reported_with_its_hash(tmp_path: Path) -> None:
    site = _site(tmp_path)
    headers = _headers(tmp_path, [check.csp_hash(STYLE), check.csp_hash(HANDLER)])
    messages = check.check(site, headers)
    assert len(messages) == 1
    assert check.csp_hash(SCRIPT) in messages[0]
    assert messages[0].startswith("script ")
    assert "about/index.html" in messages[0]


def test_a_changed_inline_script_is_reported_as_drift(tmp_path: Path) -> None:
    # The hash of the old script stays declared; the page now carries a new script.
    site = _site(tmp_path, PAGE.replace('"theme"', '"theme-v2"'))
    headers = _headers(
        tmp_path, [check.csp_hash(SCRIPT), check.csp_hash(STYLE), check.csp_hash(HANDLER)]
    )
    messages = check.check(site, headers)
    assert [m.split()[0] for m in messages] == ["script"]
    assert check.csp_hash('console.log("theme-v2")') in messages[0]


def test_json_data_blocks_are_not_checked(tmp_path: Path) -> None:
    site = _site(tmp_path, '<script type="application/ld+json">{"@type":"Thing"}</script>')
    assert check.check(site, _headers(tmp_path, [])) == []


def test_a_missing_site_is_a_warning_not_a_silent_pass(tmp_path: Path) -> None:
    messages = check.check(tmp_path / "absent", _headers(tmp_path, []))
    assert len(messages) == 1
    assert "no built pages" in messages[0]


def test_main_prints_a_github_error_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = _site(tmp_path)
    headers = _headers(tmp_path, [])
    assert check.main(["csp_hashes.py", str(site), str(headers)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("::error title=CSP hash drift::script ")


def test_main_is_quiet_when_everything_is_declared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = _site(tmp_path)
    headers = _headers(
        tmp_path, [check.csp_hash(SCRIPT), check.csp_hash(STYLE), check.csp_hash(HANDLER)]
    )
    assert check.main(["csp_hashes.py", str(site), str(headers)]) == 0
    assert "::error" not in capsys.readouterr().out
