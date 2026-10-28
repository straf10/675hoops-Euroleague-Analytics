"""Transliteration: ``fold`` (Greek/Latin look-alikes) and ``latin_key`` (EuroLeague name keys)."""

from __future__ import annotations

import pytest

from eurohoops.entity.translit import fold, latin_key


def test_fold_mixed_token_tyson() -> None:
    assert fold("ΤYSON") == "TYSON"
    assert fold("ΚΩΝΣΤAΝΤΙΝΟΣ") == "ΚΩΝΣΤΑΝΤΙΝΟΣ"


@pytest.mark.parametrize(
    ("raw", "expected_fold"),
    [
        ("μητόγλου", "ΜΗΤΟΓΛΟΥ"),
        ("ΜΗΤΌΓΛΟΥ", "ΜΗΤΟΓΛΟΥ"),
        ("ΚΩΝΣΤAΝΤΙΝΟΣ", "ΚΩΝΣΤΑΝΤΙΝΟΣ"),
        ("κωνσταντινος", "ΚΩΝΣΤΑΝΤΙΝΟΣ"),
        ("WARD", "WARD"),
        ("ΣAΝΤ-ΡΟΣ", "ΣΑΝΤ ΡΟΣ"),
    ],
)
def test_fold_case_accent_lookalike(raw: str, expected_fold: str) -> None:
    assert fold(raw) == expected_fold


def test_latin_key_sorts_hyphenated() -> None:
    assert latin_key("SANT-ROOS, HOWARD") == "HOWARD ROOS SANT"
    assert latin_key("SANT-ROOS") == "ROOS SANT"


def test_latin_key_drops_generational_suffix() -> None:
    assert latin_key("MACON JR") == "MACON"
    assert latin_key("SMITH SR III") == "SMITH"
    assert latin_key("JR") == "JR"
    assert latin_key("II") == "II"
