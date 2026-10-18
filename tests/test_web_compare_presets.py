"""Compare's curated presets (web/src/lib/compare_presets.ts) name real players and seasons.

The build skips an unknown preset with a warning, so this test is the hard check. It checks the
real stats export (web/src/data/stats, written by `eurohoops export-stats`) and skips when there is
none. The fixture copy the CI build uses is not real data, so it is skipped too.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRESETS_TS = ROOT / "web" / "src" / "lib" / "compare_presets.ts"
REAL = ROOT / "web" / "src" / "data" / "stats"
FIXTURE = ROOT / "tests" / "fixtures" / "stats"
PRESET = re.compile(
    r'\{ label: "(?P<label>[^"]+)", scope: "(?P<scope>season|career)", '
    r"picks: \[(?P<picks>[^\]]*)\] \}"
)
PICK = re.compile(r'"([a-z0-9-]+)(?::(\d{4}))?"')


def presets() -> list[tuple[str, str, list[tuple[str, int | None]]]]:
    text = PRESETS_TS.read_text(encoding="utf-8")
    found = []
    for m in PRESET.finditer(text):
        picks = [
            (slug, int(season) if season else None) for slug, season in PICK.findall(m["picks"])
        ]
        found.append((m["label"], m["scope"], picks))
    return found


def test_preset_shape() -> None:
    items = presets()
    assert len(items) == 12, "the file has a different number of presets than the 12 kept"
    for label, scope, picks in items:
        assert picks, f"{label}: no players"
        assert len(picks) <= 5, f"{label}: Compare shows at most five players"
        if scope == "career":
            assert all(season is None for _, season in picks), (
                f"{label}: career picks take no season"
            )
        else:
            assert all(season is not None for _, season in picks), (
                f"{label}: season picks need a season"
            )
            assert all(2007 <= season <= 2030 for _, season in picks if season), (
                f"{label}: season out of range"
            )


def _real_data() -> Path:
    splits = REAL / "splits.json"
    if not splits.exists():
        pytest.skip("no real stats export under web/src/data/stats")
    if splits.read_bytes() == (FIXTURE / "splits.json").read_bytes():
        pytest.skip("web/src/data/stats holds the test fixtures, not the real export")
    return REAL


def test_presets_exist_in_real_data() -> None:
    data = _real_data()
    players = json.loads((data / "players.json").read_text(encoding="utf-8"))["players"]
    by_slug = {p["slug"]: p["id"] for p in players}
    splits = json.loads((data / "splits.json").read_text(encoding="utf-8"))
    seasons: dict[str, set[int]] = defaultdict(set)
    id_to_slug = {v: k for k, v in by_slug.items()}
    for pid, season, *_ in splits["rows"]:
        if pid in id_to_slug:
            seasons[id_to_slug[pid]].add(int(season))
    problems = []
    for label, _, picks in presets():
        for slug, season in picks:
            if slug not in by_slug:
                problems.append(f"{label}: no player {slug}")
            elif season is not None and season not in seasons[slug]:
                problems.append(f"{label}: {slug} has no {season} season")
    assert not problems, "\n".join(problems)
