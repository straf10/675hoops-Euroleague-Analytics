"""E1: the EuroLeague ``team_games`` table and its validation report."""

import gzip
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from eurohoops.parse.possession_report import (
    coverage,
    euroleague_sample,
    points_mismatches,
    possession_report,
)
from eurohoops.parse.team_box import build_team_games
from tests.conftest import FIXTURES

BOX = json.loads((FIXTURES / "box_E2023_1.json").read_text(encoding="utf-8"))  # RED 94-73 ASV


def cache(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(payload, mtime=0))


def frame(
    rows: list[tuple[str, int, int, str, str, int, int]], neutral: bool = False
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [r[0] for r in rows],
            "season": [r[1] for r in rows],
            "game_code": [r[2] for r in rows],
            "home": [r[3] for r in rows],
            "away": [r[4] for r in rows],
            "home_score": [r[5] for r in rows],
            "away_score": [r[6] for r in rows],
            "played": True,
            "forfeit": False,
            "neutral": neutral,
        }
    )


EMPTY_BOX = {"ByQuarter": [], "Stats": [{"PlayersStats": []}, {"PlayersStats": []}]}


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    el = tmp_path / "euroleague"
    cache(el / "boxscore" / "E2023" / "1.json.gz", json.dumps(BOX).encode())
    cache(el / "boxscore" / "E2023" / "2.json.gz", json.dumps(EMPTY_BOX).encode())
    cache(el / "boxscore" / "E2023" / "3.json.gz", json.dumps(BOX).encode())
    cache(el / "boxscore" / "E2023" / "4.json.gz", json.dumps(BOX).encode())
    return el


EL_GAMES = [
    ("E2023_1", 2023, 1, "RED", "ASV", 94, 73),
    ("E2023_2", 2023, 2, "RED", "ASV", 80, 70),  # API placeholder box
    ("E2023_3", 2023, 3, "MAD", "ASV", 94, 73),  # box of other teams
    ("E2023_4", 2023, 4, "RED", "ASV", 95, 73),  # box points differ from the result
    ("E2023_5", 2023, 5, "RED", "ASV", 90, 80),  # not cached
]


def build(raw: Path) -> Any:
    return build_team_games(frame(EL_GAMES), raw)


def test_team_games_rows_and_missing_reasons(raw: Path) -> None:
    built = build(raw)
    table = built.table.set_index(["game_id", "team"])
    red = table.loc[("E2023_1", "RED")]
    assert (red["opponent"], bool(red["home"]), red["source"]) == ("ASV", True, "euroleague_box")
    assert red["poss_raw"] == pytest.approx(69.46)
    assert red["poss_game"] == pytest.approx((69.46 + 69.82) / 2)
    assert not table.loc[("E2023_1", "ASV"), "home"]
    reasons = dict(zip(built.missing["game_id"], built.missing["reason"], strict=True))
    assert reasons == {
        "E2023_2": "box score has no players (API placeholder)",
        "E2023_3": "box score teams ['ASV', 'RED'] are not the game's ['MAD', 'ASV']",
        "E2023_4": "box points 94-73 are not the result",
        "E2023_5": "no cached box score (ingest --details)",
    }
    assert len(built.table) == 2


def test_neutral_games_have_no_home_team(raw: Path) -> None:
    built = build_team_games(frame(EL_GAMES[:1], neutral=True), raw)
    assert not built.table["home"].any()


def test_coverage_and_points_checks(raw: Path) -> None:
    built = build(raw)
    games = frame(EL_GAMES).assign(competition="euroleague")
    cov = coverage(built.table, built.missing, games)
    assert cov["euroleague"]["2023"] == {"rated_games": 5, "with_rows": 1, "missing": 4}
    assert points_mismatches(built.table, games) == []
    moved = built.table.assign(points=built.table["points"] + (built.table["game_id"] == "E2023_1"))
    assert points_mismatches(moved, games) == ["E2023_1"]


def pbp_json(rows: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "FirstQuarter": [
            {"PLAYTYPE": k, "CODETEAM": t, "PLAYER_ID": "", "MARKERTIME": c, "MINUTE": 1}
            for k, t, c in rows
        ]
    }


def test_euroleague_sample_compares_box_and_pbp(tmp_path: Path) -> None:
    raw = tmp_path / "el"
    cache(raw / "boxscore" / "E2023" / "1.json.gz", json.dumps(BOX).encode())
    pbp = pbp_json([("2FGM", "RED", "09:00")] * 70 + [("2FGM", "ASV", "08:00")] * 66)
    cache(raw / "playbyplay" / "E2023" / "1.json.gz", json.dumps(pbp).encode())
    cache(raw / "boxscore" / "E2024" / "7.json.gz", json.dumps(EMPTY_BOX).encode())
    cache(raw / "playbyplay" / "E2024" / "7.json.gz", json.dumps(pbp_json([])).encode())
    report = euroleague_sample(raw)
    assert report["games"] == 1
    assert report["excluded"] == {"E2024_7": "box score has no players (API placeholder)"}
    assert [(r["team"], r["box"], r["pbp"]) for r in report["per_team"]] == [
        ("RED", 69.46, 70),
        ("ASV", 69.82, 66),
    ]
    assert report["within_tolerance_share_of_teams"] == 0.5
    assert report["within_tolerance_share_of_games"] == 0.0
    assert report["mean_gap_pbp_minus_box"] == pytest.approx((0.54 - 3.82) / 2, abs=1e-4)


def test_full_report_without_pbp_cache(raw: Path) -> None:
    built = build(raw)
    games = frame(EL_GAMES).assign(competition="euroleague")
    report = possession_report(built.table, missing=built.missing, games=games, euroleague_raw=raw)
    assert report["euroleague_pbp_sample"] is None  # no EuroLeague PBP cached
    assert len(report["missing_games"]) == 4
    assert report["points_mismatches"] == []
