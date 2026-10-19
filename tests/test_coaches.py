"""Coach export (stats/coaches.py) on synthetic box scores: sides, expectation, head to head."""

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from eurohoops.stats.coaches import (
    H2H_MIN_GAMES,
    coach_games,
    coach_payloads,
    current_coaches,
    final_winners,
)


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
        "tipoff_utc": f"2020-10-{i:02d}T18:00:00Z",
        "phase": "RS",
        "round": 1,
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


def test_current_coach_is_the_one_of_each_clubs_latest_game_in_the_latest_season(
    tmp_path: Path,
) -> None:
    def game(
        *, season: int, i: int, home: str, away: str, day: str, home_c: str, away_c: str
    ) -> dict:
        _write(tmp_path, season, str(i), _box(home, away, home_c, away_c))
        row = _game(i, home, away, home_won=True, p_home=0.5)
        return {**row, "season": season, "game_id": f"E{season}_{i}", "tipoff_utc": day}

    games = _games(
        [
            # 2020 (not the latest season): AAA's coach is Kim Lee.
            game(
                season=2020,
                i=1,
                home="AAA",
                away="BBB",
                day="2020-10-01T18:00:00Z",
                home_c="LEE, KIM",
                away_c="JONES, ANN",
            ),
            # 2021: AAA fires Smith after game 2 and Lee takes over; BBB keeps Jones.
            game(
                season=2021,
                i=2,
                home="AAA",
                away="BBB",
                day="2021-10-02T18:00:00Z",
                home_c="SMITH, JOHN",
                away_c="JONES, ANN",
            ),
            game(
                season=2021,
                i=3,
                home="BBB",
                away="AAA",
                day="2021-10-09T18:00:00Z",
                home_c="JONES, ANN",
                away_c="LEE, KIM",
            ),
            # CCC's latest game names no coach: the club has no current coach.
            game(
                season=2021,
                i=4,
                home="CCC",
                away="BBB",
                day="2021-10-03T18:00:00Z",
                home_c="PARK, SAM",
                away_c="JONES, ANN",
            ),
            game(
                season=2021,
                i=5,
                home="CCC",
                away="AAA",
                day="2021-10-10T18:00:00Z",
                home_c="",
                away_c="LEE, KIM",
            ),
        ]
    )
    rows = coach_games(tmp_path, games)
    latest, current = current_coaches(rows, codes={"AAA": "ALP", "BBB": "BET"})
    assert latest == 2021
    assert current == [
        {"team": "ALP", "slug": "kim-lee"},
        {"team": "BET", "slug": "ann-jones"},
    ]
    files = coach_payloads(rows, codes={}, names={})
    assert files["coaches/index.json"]["current_season"] == 2021
    assert files["coaches/index.json"]["current_through"] == "2021-10-10"
    assert files["coaches/index.json"]["current"] == [
        {"team": "AAA", "slug": "kim-lee"},
        {"team": "BBB", "slug": "ann-jones"},
    ]


def test_no_rows_means_no_current_season(tmp_path: Path) -> None:
    rows = pd.DataFrame(columns=["season", "team", "slug", "tipoff_utc"])
    assert current_coaches(rows, codes={}) == (None, [])


def _ff(  # noqa: PLR0917 -- compact Final Four row builder
    i: int, season: int, rnd: int, home: str, away: str, hs: int, aws: int
) -> dict:
    return {
        "season": season,
        "game_id": f"E{season}_{i}",
        "home": home,
        "away": away,
        "home_score": hs,
        "away_score": aws,
        "phase": "FF",
        "round": rnd,
        "played": True,
        "forfeit": False,
    }


def test_final_is_the_later_game_between_the_semifinal_winners() -> None:
    # Semifinals in round 40 (AAA and DDD win). The final is AAA-DDD in round 41; the
    # third-place game (BBB-CCC) has two losing semifinalists and is not the final.
    games = pd.DataFrame(
        [
            _ff(1, 2021, 40, "AAA", "BBB", 80, 70),
            _ff(2, 2021, 40, "CCC", "DDD", 60, 75),
            _ff(3, 2021, 41, "AAA", "DDD", 70, 65),
            _ff(4, 2021, 41, "BBB", "CCC", 90, 80),
        ]
    )
    assert final_winners(games) == {"E2021_3": "AAA"}


def test_a_season_without_one_clear_final_gets_no_champion() -> None:
    # Only the semifinals are in the data: no final, so no entry rather than a guess.
    games = pd.DataFrame(
        [_ff(1, 2021, 40, "AAA", "BBB", 80, 70), _ff(2, 2021, 40, "CCC", "DDD", 60, 75)]
    )
    assert final_winners(games) == {}


def _named(  # noqa: PLR0917 -- compact one-game builder: a box score and its games row
    tmp_path: Path,
    i: int,
    season: int,
    phase: str,
    rnd: int,
    teams: tuple[str, str, str, str],
    home_won: bool,
) -> dict:
    home, away, home_coach, away_coach = teams
    _write(tmp_path, season, str(i), _box(home, away, home_coach, away_coach))
    home_score, away_score = (80, 70) if home_won else (70, 80)
    return {
        "season": season,
        "game_id": f"E{season}_{i}",
        "game_code": str(i),
        "home": home,
        "away": away,
        "home_score": home_score,
        "away_score": away_score,
        "p_home": 0.5,
        "tipoff_utc": f"{season}-05-{i:02d}T18:00:00Z",
        "phase": phase,
        "round": rnd,
        "played": True,
        "forfeit": False,
    }


def test_playoff_seasons_final_fours_and_titles_come_from_the_named_games(tmp_path: Path) -> None:
    smith, jones, lee, park = "SMITH, JOHN", "JONES, ANN", "LEE, KIM", "PARK, SU"
    games = [
        # 2020: semifinals AAA-BBB and CCC-DDD (AAA and DDD win), then the final AAA-DDD (AAA wins).
        _named(tmp_path, 1, 2020, "FF", 40, ("AAA", "BBB", smith, jones), True),
        _named(tmp_path, 2, 2020, "FF", 40, ("CCC", "DDD", lee, park), False),
        _named(tmp_path, 3, 2020, "FF", 41, ("AAA", "DDD", smith, park), True),
        _named(tmp_path, 4, 2020, "PO", 30, ("CCC", "AAA", lee, smith), False),
        # 2021: a playoff game for LEE's CCC and JONES's BBB; a play-in game is not a playoff game.
        _named(tmp_path, 5, 2021, "PO", 30, ("CCC", "BBB", lee, jones), True),
        _named(tmp_path, 6, 2021, "PI", 9, ("DDD", "CCC", park, lee), True),
    ]
    rows = coach_games(tmp_path, _games(games))
    index = coach_payloads(rows, codes={}, names={})["coaches/index.json"]
    playoffs = {c["slug"]: c["playoffs"] for c in index["coaches"]}
    assert playoffs["john-smith"] == {"seasons": 1, "final_four": 1, "titles": 1}
    assert playoffs["ann-jones"] == {"seasons": 2, "final_four": 1, "titles": 0}
    assert playoffs["kim-lee"] == {"seasons": 2, "final_four": 1, "titles": 0}
    assert playoffs["su-park"] == {"seasons": 1, "final_four": 1, "titles": 0}
