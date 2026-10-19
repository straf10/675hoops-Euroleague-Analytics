"""Coach export (stats/coaches.py) on synthetic box scores: sides, expectation, head to head."""

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from eurohoops.stats.coaches import H2H_MIN_GAMES, coach_games, coach_payloads


def _box(home: str, away: str, home_coach: str, away_coach: str) -> dict:
    return {
        "Stats": [
            {"Coach": home_coach, "PlayersStats": [{"Team": home}]},
            {"Coach": away_coach, "PlayersStats": [{"Team": away}]},
        ]
    }


def _write(raw: Path, season: int, code: str, box: dict) -> None:
    folder = raw / "boxscore" / f"E{season}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{code}.json.gz").write_bytes(gzip.compress(json.dumps(box).encode()))


def _games(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["played"] = True
    frame["forfeit"] = False
    return frame


def _game(i: int, home: str, away: str, home_won: bool, p_home: float = 0.6) -> dict:
    home_score, away_score = (80, 70) if home_won else (70, 80)
    return {
        "season": 2020,
        "game_id": f"E2020_{i}",
        "game_code": str(i),
        "home": home,
        "away": away,
        "home_score": home_score,
        "away_score": away_score,
        "p_home": p_home,
    }


def test_each_side_gets_its_coach_and_the_pre_game_probability(tmp_path: Path) -> None:
    _write(tmp_path, 2020, "1", _box("AAA", "BBB", "SMITH, JOHN", "JONES, ANN"))
    _write(tmp_path, 2020, "2", _box("BBB", "AAA", "", "SMITH, JOHN"))
    games = _games([_game(1, "AAA", "BBB", True, 0.6), _game(2, "BBB", "AAA", False, 0.4)])
    rows = coach_games(tmp_path, games).sort_values(["game_id", "team"])
    home = rows[(rows["game_id"] == "E2020_1") & (rows["team"] == "AAA")].iloc[0]
    away = rows[(rows["game_id"] == "E2020_1") & (rows["team"] == "BBB")].iloc[0]
    assert (home["slug"], home["won"], round(home["p_win"], 2)) == ("john-smith", True, 0.6)
    assert (away["slug"], away["won"], round(away["p_win"], 2)) == ("ann-jones", False, 0.4)
    unnamed = rows[(rows["game_id"] == "E2020_2") & (rows["team"] == "BBB")].iloc[0]
    assert pd.isna(unnamed["slug"])


def test_a_box_score_with_other_teams_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, 2020, "1", _box("AAA", "CCC", "SMITH, JOHN", "JONES, ANN"))
    games = _games([_game(1, "AAA", "BBB", True)])
    assert coach_games(tmp_path, games).empty


def test_games_without_an_elo_probability_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, 2020, "1", _box("AAA", "BBB", "SMITH, JOHN", "JONES, ANN"))
    games = _games([{**_game(1, "AAA", "BBB", True), "p_home": float("nan")}])
    assert coach_games(tmp_path, games).empty


def test_expected_wins_head_to_head_and_coverage(tmp_path: Path) -> None:
    # Smith (AAA) coaches home in five games against Jones (BBB) and wins four of them; Jones
    # wins once. A third coach (CAR) meets Smith in three games only.
    games_rows = []
    for i in range(5):
        _write(tmp_path, 2020, str(i), _box("AAA", "BBB", "SMITH, JOHN", "JONES, ANN"))
        games_rows.append(_game(i, "AAA", "BBB", home_won=i < 4, p_home=0.6))
    for i in range(5, 8):
        _write(tmp_path, 2020, str(i), _box("AAA", "CCC", "SMITH, JOHN", "LEE, KIM"))
        games_rows.append(_game(i, "AAA", "CCC", home_won=True, p_home=0.5))
    _write(tmp_path, 2020, "8", _box("DDD", "EEE", "", ""))
    games_rows.append(_game(8, "DDD", "EEE", home_won=True, p_home=0.5))
    rows = coach_games(tmp_path, _games(games_rows))

    files = coach_payloads(rows, codes={"AAA": "AAA"}, names={"AAA": "Alpha"})
    smith = files["coaches/john-smith.json"]
    assert smith["career"]["games"] == 8
    assert smith["career"]["wins"] == 7
    assert smith["career"]["expected_wins"] == pytest.approx(4.5)
    assert smith["career"]["wins_above_expectation"] == pytest.approx(2.5)
    assert smith["seasons"][0] == {
        "season": 2020,
        "team": "AAA",
        "team_name": "Alpha",
        "games": 8,
        "wins": 7,
        "losses": 1,
        "expected_wins": 4.5,
        "wins_above_expectation": 2.5,
    }
    # Only pairs with at least H2H_MIN_GAMES games are listed: Jones (5) yes, Lee (3) no.
    assert H2H_MIN_GAMES == 4
    assert [(o["slug"], o["games"], o["wins"]) for o in smith["h2h"]] == [("ann-jones", 5, 4)]
    jones = files["coaches/ann-jones.json"]
    assert [(o["slug"], o["wins"]) for o in jones["h2h"]] == [("john-smith", 1)]
    index = files["coaches/index.json"]
    assert [c["slug"] for c in index["coaches"]] == ["john-smith", "ann-jones", "kim-lee"]
    assert index["coverage"] == [{"season": 2020, "games": 9, "with_coach": 8}]
