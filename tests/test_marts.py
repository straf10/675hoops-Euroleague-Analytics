import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from eurohoops.config import EUROLEAGUE, MART_PATH, SQL_DIR
from eurohoops.marts import (
    build_marts,
    data_volume,
    playbyplay_actions,
    read_games,
    read_teams,
    write_tables,
)
from eurohoops.parse.games import write_table
from tests.conftest import REPO, make_games, teams_table, write_pipeline


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.usefixtures("workdir")
def test_marts_round_trip_euroleague() -> None:
    euroleague = make_games({2024: True, 2025: False})
    write_pipeline(euroleague)
    pd.testing.assert_frame_equal(read_games(MART_PATH, "euroleague"), euroleague)
    assert read_teams(MART_PATH, "euroleague").equals(teams_table(euroleague))


@pytest.mark.usefixtures("workdir")
def test_marts_build_from_euroleague_staging(tmp_path: Path) -> None:
    euroleague = make_games({2024: True, 2025: False})
    write_table(euroleague, EUROLEAGUE.staging_games)
    write_table(teams_table(euroleague), EUROLEAGUE.staging_teams)
    build_marts(MART_PATH, REPO / SQL_DIR)
    pd.testing.assert_frame_equal(read_games(MART_PATH, "euroleague"), euroleague)
    assert read_teams(MART_PATH, "euroleague").equals(teams_table(euroleague))


def test_data_volume_counts_played_non_forfeit_games_seasons_and_shots(tmp_path: Path) -> None:
    mart = tmp_path / "eurohoops.duckdb"
    games = pd.DataFrame(
        {
            "competition": ["euroleague"] * 4 + ["other"] * 2,
            "season": [2024, 2024, 2025, 2025, 2024, 2026],
            "played": [True, True, True, False, True, True],
            "forfeit": [False, False, True, False, False, False],
        }
    )
    shots = pd.DataFrame({"x": [1.0, 2.0, None, 4.0], "y": [1.0, None, 3.0, 4.0]})
    write_tables(mart, {"games": games, "shots": shots})
    # EuroLeague only: E2024 x2 are played and not forfeits. The E2025 forfeit and the unplayed
    # rows are out. Shots need both coordinates.
    assert data_volume(mart) == {"games": 2, "seasons": 1, "shots_with_coordinates": 2}


def test_playbyplay_actions_count_playtype_entries_in_every_period_list(tmp_path: Path) -> None:
    game = tmp_path / "E2024"
    game.mkdir()
    rows = {
        "FirstQuarter": [{"PLAYTYPE": "BP"}, {"PLAYTYPE": "2FGM"}, {"PLAYER": "no type"}],
        "SecondQuarter": [{"PLAYTYPE": "D"}],
        "ExtraTime": [],
        "Live": False,
        "TeamA": "not a list",
    }
    (game / "1.json.gz").write_bytes(gzip.compress(json.dumps(rows).encode()))
    (game / "2.json.gz").write_bytes(gzip.compress(json.dumps({"FirstQuarter": []}).encode()))
    assert playbyplay_actions(tmp_path) == 3


def test_data_volume_adds_actions_only_with_a_playbyplay_directory(tmp_path: Path) -> None:
    mart = tmp_path / "eurohoops.duckdb"
    games = pd.DataFrame(
        {"competition": ["euroleague"], "season": [2025], "played": [True], "forfeit": [False]}
    )
    write_tables(mart, {"games": games})
    pbp = tmp_path / "playbyplay"
    (pbp / "E2025").mkdir(parents=True)
    (pbp / "E2025" / "7.json.gz").write_bytes(
        gzip.compress(
            json.dumps({"FirstQuarter": [{"PLAYTYPE": "OUT"}, {"PLAYTYPE": "IN"}]}).encode()
        )
    )
    assert data_volume(mart) == {"games": 1, "seasons": 1}
    assert "actions" not in data_volume(mart)
    assert data_volume(mart, pbp)["actions"] == 2
