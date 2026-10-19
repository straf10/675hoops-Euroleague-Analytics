"""Documented box repairs: the owner's 2022 PBP scope and the per-player corrections file."""

from pathlib import Path

import pytest

from eurohoops.parse.box import (
    OWNER_FILL_GAMES,
    BoxCorrection,
    build_box_tables,
    load_box_corrections,
)
from tests.test_gbl_pbp import (
    BOX,
    EXTRA,
    cache,
    events_for,
    export,
    games_frame,
    with_final,
    write_box_game,
)

REPAIRED = "GBL2022_4180233B"


def test_the_owner_scope_is_exactly_the_two_games() -> None:
    assert {"GBL2022_4180233B", "GBL2022_AF0B05AA"} == OWNER_FILL_GAMES


def test_a_repaired_2022_game_is_filled_to_its_result(tmp_path: Path) -> None:
    assert BOX is not None
    home, away = list(BOX[0].players), list(BOX[1].players)
    rows = events_for([*home, EXTRA], 0, list(range(len(home) + 1)))
    rows += events_for(away, 1, list(range(50, 50 + len(away))))
    write_box_game(tmp_path, 2022, 0x4180233B, box=True)
    cache(tmp_path / "pbp" / "2022" / "4180233B.xlsx.gz", export(with_final(rows, 88, 64)))
    tables = build_box_tables(tmp_path, games_frame([(REPAIRED, 2022, 0x4180233B, 88, 64)]))
    [log] = tables.fill.to_dict("records")
    assert (log["team"], log["fill"]) == ("HOM", "missing_player_from_pbp")
    filled = tables.player_box[tables.player_box["game_id"] == REPAIRED]
    home_points = filled[filled["team"] == "HOM"]["points"].sum()
    assert home_points == 88  # the filled points equal the final score


def test_other_2022_games_stay_outside_the_scope(tmp_path: Path) -> None:
    assert BOX is not None
    home, away = list(BOX[0].players), list(BOX[1].players)
    rows = events_for([*home, EXTRA], 0, list(range(len(home) + 1)))
    rows += events_for(away, 1, list(range(50, 50 + len(away))))
    write_box_game(tmp_path, 2022, 0x00000042, box=True)
    cache(tmp_path / "pbp" / "2022" / "00000042.xlsx.gz", export(with_final(rows, 88, 64)))
    games = games_frame([("GBL2022_00000042", 2022, 0x42, 88, 64)])
    [log] = build_box_tables(tmp_path, games).fill.to_dict("records")
    assert log["fill"] == "not_filled"
    assert log["detail"].startswith("outside the 2018-19/2019-20 fill scope")


def test_a_correction_replaces_the_documented_seconds(tmp_path: Path) -> None:
    assert BOX is not None
    player = BOX[0].players[0]
    write_box_game(tmp_path, 2018, 0x0000000A, box=True)
    games = games_frame([("G_CORR", 2018, 0x0000000A, 81, 64)])
    key = ("G_CORR", "HOM", player.player_id)
    fixes = {key: BoxCorrection(raw_value=player.seconds, value=1234, reason="test")}
    tables = build_box_tables(tmp_path, games, corrections=fixes)
    row = tables.player_box[tables.player_box["player_id"] == player.player_id].iloc[0]
    assert row["seconds"] == 1234
    assert row["points"] == player.points  # only the minutes change


def test_a_stale_correction_raises(tmp_path: Path) -> None:
    assert BOX is not None
    player = BOX[0].players[0]
    write_box_game(tmp_path, 2018, 0x0000000B, box=True)
    games = games_frame([("G_STALE", 2018, 0x0000000B, 81, 64)])
    fixes = {
        ("G_STALE", "HOM", player.player_id): BoxCorrection(
            raw_value=player.seconds + 1, value=1, reason="stale"
        )
    }
    with pytest.raises(ValueError, match="stale correction"):
        build_box_tables(tmp_path, games, corrections=fixes)


def test_the_corrections_file_loads_by_game_team_and_player(tmp_path: Path) -> None:
    path = tmp_path / "gbl_box.csv"
    path.write_text(
        "game_id,team,player_id,raw_seconds,seconds,reason\n"
        'G1,T1,P1,3782,2163,"a reason, with a comma"\n',
        encoding="utf-8",
    )
    fixes = load_box_corrections(path)
    assert fixes == {("G1", "T1", "P1"): BoxCorrection(3782, 2163, "a reason, with a comma")}
    assert load_box_corrections(tmp_path / "missing.csv") == {}


def test_the_repository_corrections_file_is_well_formed() -> None:
    fixes = load_box_corrections(Path("corrections/gbl_box.csv"))
    for (game_id, team, player), fix in fixes.items():
        assert game_id.startswith("GBL") and team and player
        assert fix.raw_value != fix.value
        assert fix.value < fix.raw_value  # a correction here removes an impossible minutes cell
        assert fix.reason
