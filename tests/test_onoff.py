import json
import logging
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pytest

from eurohoops.ingest.cache import write_atomic
from eurohoops.stats.onoff import (
    SCORE_COLUMNS,
    clutch_points,
    empty_payload,
    load_onoff,
    onoff_payload,
    qualifying_seasons,
    write_onoff,
)


def stint(  # noqa: PLR0917
    period: int,
    start: int,
    end: int,
    home: list[str],
    away: list[str],
    pts: tuple[int, int] = (0, 0),
    poss: tuple[int, int] = (0, 0),
    game: str = "G1",
    season: int = 2025,
) -> dict[str, Any]:
    return {
        "game_id": game,
        "season": season,
        "period": period,
        "start_s": start,
        "end_s": end,
        "home": "HOM",
        "away": "AWY",
        "home_players": home,
        "away_players": away,
        "home_points": pts[0],
        "away_points": pts[1],
        "home_poss": poss[0],
        "away_poss": poss[1],
    }


def checks(game: str = "G1", passed: bool = True, season: int = 2025) -> pd.DataFrame:
    return pd.DataFrame([{"game_id": game, "season": season, "passed": passed}])


def build(rows: list[dict[str, Any]], scores: pd.DataFrame | None = None) -> dict[str, Any]:
    return onoff_payload(pd.DataFrame(rows), checks(), {2025: 1}, [2025], scores)


def test_on_off_totals() -> None:
    payload = build(
        [
            stint(1, 0, 300, ["a", "b"], ["x"], (6, 4), (3, 3)),
            stint(1, 300, 600, ["a", "c"], ["x"], (2, 7), (2, 4)),
        ]
    )
    assert payload["seasons"] == [2025]
    players = payload["players"]
    assert players["a"]["2025"]["on"] == {"sec": 600, "poss": 5, "pf": 8, "pa": 11}
    assert players["a"]["2025"]["off"] == {"sec": 0, "poss": 0, "pf": 0, "pa": 0}
    assert players["b"]["2025"]["on"] == {"sec": 300, "poss": 3, "pf": 6, "pa": 4}
    assert players["b"]["2025"]["off"] == {"sec": 300, "poss": 2, "pf": 2, "pa": 7}
    assert players["c"]["2025"]["off"] == {"sec": 300, "poss": 3, "pf": 6, "pa": 4}
    # the away side sees the points the other way round
    assert players["x"]["2025"]["on"] == {"sec": 600, "poss": 7, "pf": 11, "pa": 8}


def test_off_counts_only_games_the_player_appeared_in() -> None:
    rows = [
        stint(1, 0, 600, ["a"], ["x"], (10, 8), (5, 5)),
        stint(1, 0, 600, ["b"], ["x"], (30, 20), (9, 9), game="G2"),
    ]
    frame = pd.concat([checks("G1"), checks("G2")], ignore_index=True)
    payload = onoff_payload(pd.DataFrame(rows), frame, {2025: 2}, [2025])
    assert payload["players"]["a"]["2025"]["off"]["sec"] == 0
    assert payload["players"]["b"]["2025"]["off"]["sec"] == 0


def test_failed_games_are_left_out() -> None:
    rows = [
        stint(1, 0, 600, ["a"], ["x"], (10, 8), (5, 5)),
        stint(1, 0, 600, ["a"], ["x"], (30, 20), (9, 9), game="G2"),
    ]
    frame = pd.concat([checks("G1"), checks("G2", passed=False)], ignore_index=True)
    payload = onoff_payload(pd.DataFrame(rows), frame, {2025: 2}, [2025])
    assert payload["seasons"] == []  # 1 of 2 passes
    payload = onoff_payload(pd.DataFrame(rows), frame, {2025: 1}, [2025])
    assert payload["players"]["a"]["2025"]["on"]["pf"] == 10


def clutch_game(margin_before: int, tail: tuple[int, int] = (4, 2)) -> dict[str, Any]:
    """Q4 game: the home side leads by ``margin_before`` at 35:00, then one 5-minute stint."""
    return build(
        [
            stint(4, 1800, 2100, ["a"], ["x"], (margin_before, 0), (10, 10)),
            stint(4, 2100, 2400, ["a"], ["x"], tail, (8, 9)),
        ]
    )


@pytest.mark.parametrize(("margin", "inside"), [(0, True), (5, True), (6, False)])
def test_clutch_margin_boundary(margin: int, inside: bool) -> None:
    clutch = clutch_game(margin)["players"]["a"]["2025"]["clutch"]
    assert clutch["sec"] == (300 if inside else 0)
    assert clutch["poss"] == (8 if inside else 0)
    assert (clutch["pf"], clutch["pa"]) == ((4, 2) if inside else (0, 0))


def test_clutch_margin_is_symmetric() -> None:
    rows = [
        stint(4, 1800, 2100, ["a"], ["x"], (0, 5)),
        stint(4, 2100, 2400, ["a"], ["x"], (2, 2)),
    ]
    assert build(rows)["players"]["a"]["2025"]["clutch"]["sec"] == 300
    rows[0] = stint(4, 1800, 2100, ["a"], ["x"], (0, 6))
    assert build(rows)["players"]["a"]["2025"]["clutch"]["sec"] == 0


def test_clutch_window_starts_at_five_minutes_left() -> None:
    rows = [
        stint(3, 1200, 1800, ["a"], ["x"], (2, 2), (5, 5)),  # 3rd quarter: never clutch
        stint(4, 1800, 2000, ["a"], ["x"], (2, 2), (4, 4)),  # before the window
        stint(4, 2000, 2200, ["a"], ["x"], (4, 6), (4, 6)),  # straddles it: half counts
        stint(4, 2200, 2400, ["a"], ["x"], (2, 0), (2, 2)),
    ]
    clutch = build(rows)["players"]["a"]["2025"]["clutch"]
    assert clutch["sec"] == 100 + 200
    assert (clutch["pf"], clutch["pa"], clutch["poss"]) == (2 + 2, 3 + 0, 2 + 2)


def test_clutch_overtime_counts_whole_period() -> None:
    rows = [
        stint(4, 1800, 2100, ["a"], ["x"], (20, 20)),
        stint(5, 2400, 2700, ["a"], ["x"], (3, 1), (4, 4)),
        stint(6, 2700, 3000, ["a"], ["x"], (0, 2), (5, 5)),
    ]
    clutch = build(rows)["players"]["a"]["2025"]["clutch"]
    assert clutch["sec"] == 600
    assert (clutch["pf"], clutch["pa"], clutch["poss"]) == (3, 3, 9)


def test_clutch_margin_runs_over_the_game() -> None:
    # 12 points up after the first stint, back to 4 after the next: only the last is clutch
    rows = [
        stint(1, 0, 600, ["a"], ["x"], (30, 18)),
        stint(4, 2100, 2200, ["a"], ["x"], (0, 8)),
        stint(4, 2200, 2400, ["a"], ["x"], (1, 1)),
    ]
    assert build(rows)["players"]["a"]["2025"]["clutch"]["sec"] == 200


def score_rows(*events: tuple[int, float, bool, int, str]) -> pd.DataFrame:
    """(period, elapsed, home, points, player) in log order for one game."""
    return pd.DataFrame(
        [("G1", 2025, p, e, "HOM" if h else "AWY", pl, pts, h) for p, e, h, pts, pl in events],
        columns=list(SCORE_COLUMNS),
    )


def test_clutch_points_use_the_margin_before_the_event() -> None:
    scores = score_rows(
        (4, 1700.0, True, 3, "a"),  # not in the window; home 3-0
        (4, 2100.0, False, 2, "x"),  # 3-0 -> in; away 3-2... margin before 3
        (4, 2150.0, True, 3, "a"),  # margin before 1 -> in; 6-2
        (4, 2200.0, True, 3, "a"),  # margin before 4 -> in; 9-2
        (4, 2250.0, True, 2, "a"),  # margin before 7 -> out; 11-2
        (4, 2300.0, False, 3, "x"),  # margin before 9 -> out
    )
    pts = clutch_points(scores).set_index("player")["pts"].to_dict()
    assert pts == {"a": 6, "x": 2}


def test_clutch_points_boundary_and_overtime() -> None:
    scores = score_rows(
        (4, 1000.0, True, 3, "b"),
        (4, 1500.0, True, 2, "b"),  # home 5-0 before the next event
        (4, 2150.0, True, 1, "a"),  # margin before exactly 5 -> in
        (4, 2160.0, True, 2, "a"),  # margin before 6 -> out
        (5, 2410.0, False, 3, "x"),  # overtime, margin before 8 -> out
    )
    assert clutch_points(scores).set_index("player")["pts"].to_dict() == {"a": 1}
    ot = score_rows((5, 2410.0, True, 2, "a"), (6, 2710.0, False, 3, "x"))
    assert clutch_points(ot).set_index("player")["pts"].to_dict() == {"a": 2, "x": 3}


def test_clutch_points_skip_events_without_a_clock() -> None:
    scores = score_rows((4, 2200.0, True, 2, "a"))
    scores.loc[0, "elapsed"] = None
    assert clutch_points(scores).empty
    assert clutch_points(scores.iloc[0:0]).empty


def test_clutch_points_land_in_the_payload() -> None:
    rows = [stint(4, 2100, 2400, ["a"], ["x"], (2, 0), (4, 4))]
    payload = build(rows, score_rows((4, 2200.0, True, 2, "a")))
    assert payload["players"]["a"]["2025"]["clutch"]["pts"] == 2
    assert payload["players"]["x"]["2025"]["clutch"]["pts"] == 0


def test_season_needs_90_percent_passing_games() -> None:
    frame = pd.DataFrame(
        [{"game_id": f"G{i}", "season": 2025, "passed": i < 9} for i in range(10)]
        + [{"game_id": f"H{i}", "season": 2024, "passed": i < 8} for i in range(10)]
    )
    assert qualifying_seasons(frame, {2025: 10, 2024: 10, 2023: 10}, [2023, 2024, 2025]) == [2025]
    # a game without stints counts against the season
    assert qualifying_seasons(frame, {2025: 11}, [2025]) == []


def test_empty_stints_give_the_empty_shape() -> None:
    payload = onoff_payload(
        pd.DataFrame(columns=list(stint(1, 0, 1, [], []))), checks(), {2025: 1}, [2025]
    )
    assert payload["players"] == {}
    assert payload["clutch"] == {"last_seconds": 300, "margin": 5}


def test_missing_mart_writes_an_empty_payload(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        payload = load_onoff(tmp_path / "none.duckdb", tmp_path, pd.DataFrame(), [2025])
    assert payload == empty_payload()
    assert "missing" in caplog.text


def test_mart_without_stints_writes_an_empty_payload(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    mart = tmp_path / "m.duckdb"
    with duckdb.connect(str(mart)) as con:
        con.execute("CREATE TABLE other (x INTEGER)")
    with caplog.at_level(logging.WARNING):
        assert load_onoff(mart, tmp_path, pd.DataFrame(), [2025]) == empty_payload()
    assert "no stints" in caplog.text


def test_load_from_mart_and_play_by_play(tmp_path: Path) -> None:
    mart = tmp_path / "m.duckdb"
    rows = pd.DataFrame([stint(4, 2100, 2400, ["a"], ["x"], (2, 0), (4, 4), game="E2025_7")])
    with duckdb.connect(str(mart)) as con:
        con.register("rows", rows)
        con.execute("CREATE TABLE stints AS SELECT * FROM rows")
        con.execute(
            "CREATE TABLE stint_game_checks AS SELECT 'E2025_7' game_id, 2025 season, true passed"
        )
    pbp = {
        "ForthQuarter": [
            {"PLAYTYPE": "2FGM", "CODETEAM": "HOM ", "PLAYER_ID": "a ", "MARKERTIME": "02:00"},
            {"PLAYTYPE": "2FGM", "CODETEAM": "AWY", "PLAYER_ID": "x", "MARKERTIME": "09:00"},
        ]
    }
    path = tmp_path / "raw" / "playbyplay" / "E2025" / "7.json.gz"
    path.parent.mkdir(parents=True)
    write_atomic(path, json.dumps(pbp).encode())
    games = pd.DataFrame(
        [
            {
                "game_id": "E2025_7",
                "season": 2025,
                "game_code": 7,
                "home": "HOM",
                "away": "AWY",
                "played": True,
                "forfeit": False,
            }
        ]
    )
    payload = load_onoff(mart, tmp_path / "raw", games, [2025])
    assert payload["seasons"] == [2025]
    assert payload["players"]["a"]["2025"]["clutch"]["pts"] == 2
    assert payload["players"]["x"]["2025"]["clutch"]["pts"] == 0  # 9:00 left is before the window
    write_onoff(tmp_path / "out", payload)
    assert json.loads((tmp_path / "out" / "onoff.json").read_text())["seasons"] == [2025]
