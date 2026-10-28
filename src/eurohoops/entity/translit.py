"""Greek↔Latin name folding (weeks 12-14 I-d).

``fold`` uppercases, strips accents/diaeresis/tonos, maps punctuation to spaces, and per token
folds minority-script look-alike letters into the majority script (ties → Greek).

``latin_key`` is the EuroLeague-side normaliser (the injury and roster name matching): fold, keep
A–Z and spaces, drop generational suffix tokens (JR/SR/II/III/IV when not the only token), sort
tokens.
"""

from __future__ import annotations

import unicodedata

_LATIN_LETTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_GENERATIONAL = frozenset({"JR", "SR", "II", "III", "IV"})
_PUNCT_TO_SPACE = str.maketrans({c: " " for c in "-'’.,"})

_LATIN_TO_GREEK = str.maketrans(
    {
        "A": "Α",
        "B": "Β",
        "E": "Ε",
        "Z": "Ζ",
        "H": "Η",
        "I": "Ι",
        "K": "Κ",
        "M": "Μ",
        "N": "Ν",
        "O": "Ο",
        "P": "Ρ",
        "T": "Τ",
        "Y": "Υ",
        "X": "Χ",
    }
)
_GREEK_TO_LATIN = str.maketrans(
    {
        "Α": "A",
        "Β": "B",
        "Ε": "E",
        "Ζ": "Z",
        "Η": "H",
        "Ι": "I",
        "Κ": "K",
        "Μ": "M",
        "Ν": "N",
        "Ο": "O",
        "Ρ": "P",
        "Τ": "T",
        "Υ": "Y",
        "Χ": "X",
    }
)


def fold(text: str) -> str:
    """Uppercase, strip accents, fold look-alikes per-token, normalise punctuation/spaces."""
    if not text:
        return ""
    upper = text.upper().replace("ς", "Σ").replace("Ϲ", "Σ")
    decomposed = unicodedata.normalize("NFD", upper)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    spaced = stripped.translate(_PUNCT_TO_SPACE)
    tokens = spaced.split()
    return " ".join(_fold_token(tok) for tok in tokens)


def latin_key(text: str) -> str:
    """Fold ``text``, keep A–Z and spaces, drop generational suffixes, sort tokens."""
    folded = fold(text)
    cleaned = "".join(ch if ch in _LATIN_LETTERS or ch == " " else "" for ch in folded)
    tokens = [t for t in cleaned.split() if t]
    if len(tokens) > 1:
        tokens = [t for t in tokens if t not in _GENERATIONAL]
    return " ".join(sorted(tokens))


def _fold_token(token: str) -> str:
    # Count by Unicode block so a Latin look-alike inside a Greek name stays Latin until mapped.
    greek_n = sum(1 for ch in token if "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff")
    latin_n = sum(1 for ch in token if "A" <= ch <= "Z")
    if greek_n == 0 and latin_n == 0:
        return token
    if latin_n > greek_n:
        return token.translate(_GREEK_TO_LATIN)
    return token.translate(_LATIN_TO_GREEK)
