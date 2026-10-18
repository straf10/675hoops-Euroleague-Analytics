"""The Sign Colour Rule (docs/DESIGN.md): signed for-minus-against figures share one helper.

Source checks only: the colour is set in CSS and in renderers, so these keep the rule in one place
and keep RAPM (which stays ink) out of it."""

import re

from tests.conftest import REPO

WEB = REPO / "web" / "src"


def test_sign_class_is_defined_once_in_delta_ts() -> None:
    text = (WEB / "lib" / "delta.ts").read_text(encoding="utf-8")
    assert re.search(r"export function signClass\(", text)
    assert '"sign-pos"' in text and '"sign-neg"' in text


def test_sign_classes_use_the_delta_tokens() -> None:
    css = (WEB / "styles" / "global.css").read_text(encoding="utf-8")
    assert re.search(r"\.sign-pos\s*\{\s*color:\s*var\(--delta-up\);\s*\}", css)
    assert re.search(r"\.sign-neg\s*\{\s*color:\s*var\(--delta-down\);\s*\}", css)


def test_rapm_stays_ink() -> None:
    rapm = [WEB / "components" / "RapmTable.astro", WEB / "components" / "player" / "Rapm.astro"]
    for path in rapm:
        assert "signClass" not in path.read_text(encoding="utf-8"), path.name
