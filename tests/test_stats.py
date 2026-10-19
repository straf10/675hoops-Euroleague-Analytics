"""Stats-site export: box and shot parsing, hex bins, payloads, the CLI and the committed fixture.

``tests/fixtures/stats_raw`` is a slice of the real raw cache (rounds 1-6 of 2024-25 and round 1
of 2010-11, schedules trimmed to those games). ``tests/fixtures/stats`` is the exporter's output
on it; the CI web build reads it. Refresh it after a payload change:
``UPDATE_STATS_FIXTURE=1 uv run pytest tests/test_stats.py``
"""

import gzip
import hashlib
import io
import json
import os
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from eurohoops import cli
from eurohoops.cli import publish as publish_mod
from eurohoops.config import MART_PATH
from eurohoops.eval.backtest import load_tuned_model
from eurohoops.marts import write_tables
from eurohoops.models.roster import read_rosters
from eurohoops.publish import DISPLAY_CODES
from eurohoops.stats.assists import game_assists
from eurohoops.stats.box import build_box_games, game_lines, seconds
from eurohoops.stats.coach_style import game_styles
from eurohoops.stats.coaches import coach_games, with_elo
from eurohoops.stats.downloads import COLUMNS, DATASETS, build_downloads, write_downloads
from eurohoops.stats.export import (
    OTHER_RESULTS,
    PLAYER_FIELDS,
    RESULTS,
    TEAM_FIELDS,
    Inputs,
    _continuity_by_club,
    build_payloads,
    display_name,
    load_cached_games,
    player_slugs,
    playoff_results,
    regular_season_standings,
    season_label,
    site_window,
    slugify,
    write_stats,
)
from eurohoops.stats.positions import games_by_club, season_positions
from eurohoops.stats.runs import game_runs
from eurohoops.stats.shots import (
    BANDS,
    HEX_RADIUS_M,
    SQRT3,
    band_counts,
    bands,
    build_shots,
    game_shots,
    hex_cells,
    hexbins,
    period,
)
from eurohoops.stats.units import load_units
from eurohoops.stats.zones import shot_zones
from tests.conftest import FIXTURES

RAW = FIXTURES / "stats_raw"
OUT = FIXTURES / "stats"
HISTORY_REPORT = FIXTURES / "api" / "reports" / "backtest_elo_history.json"
NOW = datetime(2026, 9, 26, 8, tzinfo=UTC)
runner = CliRunner()


@pytest.fixture(scope="module")
def inputs() -> Inputs:
    games, teams = load_cached_games(RAW)
    box = build_box_games(RAW, games)
    return Inputs(
        games=games,
        names=dict(teams.itertuples(index=False)),
        box=box,
        shots=build_shots(RAW, games),
        codes=DISPLAY_CODES["euroleague"],
        live_season=2026,
        positions=season_positions(RAW, games_by_club(box.players)),
        runs=game_runs(RAW, games[games["played"]]),
        roster=read_rosters(RAW, [2010, 2024]),
        units=load_units(
            RAW,
            games,
            site_window(box.players["season"].unique()),
            DISPLAY_CODES["euroleague"],
        ),
        assists=game_assists(RAW, games[games["played"]]),
        coaches=coach_games(
            RAW,
            with_elo(games, load_tuned_model(HISTORY_REPORT).params, 2007),
        ),
        styles=game_styles(RAW, games),
    )


@pytest.fixture(scope="module")
def files(inputs: Inputs) -> dict[str, dict[str, Any]]:
    return build_payloads(inputs, NOW)


def test_only_the_latest_site_seasons_are_published(
    inputs: Inputs, files: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert sorted(f for f in files if f.endswith("/players.json")) == [
        "seasons/2010/players.json",
        "seasons/2024/players.json",
    ]
    monkeypatch.setattr("eurohoops.stats.export.SITE_SEASONS", 1)
    latest = build_payloads(inputs, NOW)
    assert [s["season"] for s in latest["meta.json"]["seasons"]] == [2024]
    assert not any(f.startswith("seasons/2010/") for f in latest)
    # players follow the window; splits keep the careers of those players
    assert all(2010 not in p["seasons"] for p in latest["players.json"]["players"])
    assert {row[0] for row in latest["splits.json"]["rows"]} == {
        p["id"] for p in latest["players.json"]["players"]
    }
    assert {row[1] for row in latest["splits.json"]["rows"]} >= {2024}


def test_units_are_written_for_the_seasons_given(inputs: Inputs) -> None:
    payload = {"season": 2024, "minimums": {"pair": 100, "unit": 50}, "sd": 1.5, "clubs": {}}
    files = build_payloads(replace(inputs, units={2024: payload}), NOW)
    assert files["seasons/2024/units.json"] == payload
    assert "seasons/2010/units.json" not in files


def test_season_rows_carry_the_listed_position(files: dict[str, dict[str, Any]]) -> None:
    for season in (2010, 2024):
        rows = files[f"seasons/{season}/players.json"]["players"]
        assert {r["pos"] for r in rows if "pos" in r} <= {"G", "F", "C"}
        assert sum("pos" in r for r in rows) > 0.9 * len(rows)


def test_seconds_parses_box_minutes() -> None:
    assert seconds("05:04") == 304
    assert seconds("200:00") == 12000
    assert seconds("DNP") is None


def test_period_counts_overtimes_after_the_fourth_quarter() -> None:
    assert [period(m) for m in (0, 1, 10, 11, 40, 41, 45, 46)] == [1, 1, 1, 2, 4, 5, 5, 6]


def test_bands_split_twos_by_distance_and_threes_at_eight_metres() -> None:
    distance = pd.Series([0.5, 2.0, 4.0, 6.0, 7.0, 9.0])
    value = pd.Series([2, 2, 2, 2, 3, 3])
    assert list(bands(distance, value)) == ["rim", "short", "mid", "long2", "three", "deep3"]


def test_hex_cells_round_trip_through_cell_centres() -> None:
    q = pd.Series([0, 1, -3, 4, 2])
    r = pd.Series([0, 2, 5, -1, 7])
    x = HEX_RADIUS_M * SQRT3 * (q + r / 2)
    y = HEX_RADIUS_M * 1.5 * r
    # nudge every point off-centre, well inside the cell
    got_q, got_r = hex_cells(x + 0.1, y - 0.1)
    assert list(got_q) == list(q) and list(got_r) == list(r)


def test_hexbins_group_by_key_and_count_points() -> None:
    shots = pd.DataFrame(
        {
            "player_id": ["A", "A", "B"],
            "x": [0.0, 0.05, 0.0],
            "y": [0.0, 0.05, 0.0],
            "made": [True, False, True],
            "value": [2, 2, 3],
        }
    )
    assert hexbins(shots, "player_id") == {"A": [[0, 0, 2, 1, 2]], "B": [[0, 0, 1, 1, 3]]}
    assert hexbins(shots) == {"": [[0, 0, 3, 2, 5]]}
    assert hexbins(shots.iloc[0:0]) == {}


def test_band_counts_list_every_band() -> None:
    shots = pd.DataFrame({"band": ["rim", "rim", "three"], "made": [True, False, True]})
    counts = band_counts(shots)
    assert list(counts) == list(BANDS)
    assert counts["rim"] == [2, 1] and counts["three"] == [1, 1] and counts["deep3"] == [0, 0]


def test_names_and_slugs() -> None:
    assert display_name("DE COLO, NANDO") == "Nando De Colo"
    assert display_name("MCCALEBB, BO") == "Bo McCalebb"
    assert display_name("O'NEAL, SHAQ") == "Shaq O'Neal"
    assert display_name("TEODOSIC") == "Teodosic"
    assert display_name("WALKER IV, LONNIE") == "Lonnie Walker IV"
    assert display_name("IVANOV, IVO") == "Ivo Ivanov"
    assert display_name("SHORTS, TJ") == "TJ Shorts"
    assert display_name("MACON JR, DARYL") == "Daryl Macon Jr"
    assert display_name("MC LEOD, KEITH") == "Keith Mc Leod"
    assert display_name("TY, SY") == "Sy Ty"
    assert slugify("Nikola Mirotić") == "nikola-mirotic"
    assert player_slugs({"P1": "John Smith", "P2": "John Smith", "P3": "Ana Ivić"}) == {
        "P1": "john-smith-p1",
        "P2": "john-smith-p2",
        "P3": "ana-ivic",
    }
    assert season_label(2024) == "2024-25" and season_label(2099) == "2099-00"


def test_game_lines_reject_placeholders_and_foreign_teams() -> None:
    game = {"season": 2024, "game_id": "E2024_1", "home": "AAA", "away": "BBB"}
    assert "placeholder" in str(game_lines({"Stats": []}, game))
    box = json.loads((FIXTURES / "box_E2023_1.json").read_text(encoding="utf-8"))
    assert "are not the game's" in str(
        game_lines(box, game | {"home_score": 1, "away_score": 0, "neutral": False})
    )


def test_missing_box_scores_are_listed_not_dropped(tmp_path: Path) -> None:
    games, _ = load_cached_games(RAW)
    built = build_box_games(tmp_path, games.head(3))  # an empty cache
    assert built.players.empty and built.teams.empty
    assert list(built.missing["reason"].unique()) == ["no cached box score (ingest --details)"]


def test_player_lines_add_up_to_the_team_box(inputs: Inputs) -> None:
    players = inputs.box.players.groupby(["game_id", "team"])[["pts", "fg2a", "ast"]].sum()
    teams = inputs.box.teams.set_index(["game_id", "team"])[["pts", "fg2a", "ast"]]
    pd.testing.assert_frame_equal(players.sort_index(), teams.sort_index(), check_names=False)
    # five players on court: player possessions add up to five times the game's, even where
    # the box records more minutes than were played (E2010_1)
    per_team = inputs.box.players.groupby(["game_id", "team"])["poss"].sum()
    game_poss = inputs.box.teams.groupby("game_id")["poss"].mean()
    ratio = per_team / game_poss.reindex(per_team.index.get_level_values(0)).to_numpy()
    assert ratio.between(5 - 1e-9, 5 + 1e-9).all()


def test_every_shot_is_a_box_field_goal_attempt(inputs: Inputs) -> None:
    shots = inputs.shots.table.groupby(["game_id", "team"]).size()
    box = inputs.box.teams.set_index(["game_id", "team"])
    fga = (box["fg2a"] + box["fg3a"]).reindex(shots.index)
    unplaced = int(inputs.shots.coverage["unplaced"].sum())
    assert int((fga - shots).sum()) == unplaced
    assert (fga >= shots).all()
    three = inputs.shots.table["value"] == 3
    assert inputs.shots.table.loc[three, "band"].isin(["three", "deep3"]).all()


def test_game_shots_skip_free_throws_and_unplaced_rows() -> None:
    game = {"season": 2024, "game_id": "E2024_1", "home": "AAA", "away": "BBB"}
    row = {"ID_PLAYER": "P1", "POINTS": 2, "MINUTE": 3, "FASTBREAK": "1", "SECOND_CHANCE": "0"}
    feed = {
        "Rows": [
            row | {"ID_ACTION": "2FGM", "TEAM": "AAA ", "COORD_X": 100, "COORD_Y": 0},
            row | {"ID_ACTION": "FTM", "TEAM": "AAA", "COORD_X": -1, "COORD_Y": -1},
            row | {"ID_ACTION": "3FGA", "TEAM": "BBB", "COORD_X": 0, "COORD_Y": 0},
            row | {"ID_ACTION": "2FGA", "TEAM": "BBB", "COORD_X": -1, "COORD_Y": -1},
            row | {"ID_ACTION": "2FGM", "TEAM": "ZZZ", "COORD_X": 5, "COORD_Y": 5},
        ]
    }
    shots, unplaced = game_shots(feed, game)
    assert unplaced == 2
    assert [(s["team"], s["opponent"], s["fastbreak"], s["coord_x"]) for s in shots] == [
        ("AAA", "BBB", True, 100.0)
    ]


def test_payload_windows_and_bands(files: dict[str, dict[str, Any]]) -> None:
    season = files["seasons/2024/players.json"]
    assert season["fields"] == list(PLAYER_FIELDS)
    gp = PLAYER_FIELDS.index("gp")
    for row in season["players"]:
        played = row["totals"]["season"][gp]
        assert ("last5" in row["totals"]) == (played > 5)
        assert "last10" not in row["totals"]  # six rounds only
        assert list(row["bands"]) == list(BANDS)
    pts = PLAYER_FIELDS.index("pts")
    tops = [r["totals"]["season"][pts] for r in season["players"]]
    assert tops == sorted(tops, reverse=True)


def test_team_totals_cover_the_player_lines(files: dict[str, dict[str, Any]]) -> None:
    season = files["seasons/2024/players.json"]
    assert {"tm_fgm", "tm_oreb", "tm_dreb", "opp_oreb", "opp_dreb"} <= set(season["fields"])
    idx = {f: i for i, f in enumerate(season["fields"])}
    for row in season["players"]:
        for window, t in row["totals"].items():
            made = t[idx["fg2m"]] + t[idx["fg3m"]]
            assert t[idx["tm_fgm"]] >= made, (row["id"], window)
            assert t[idx["tm_oreb"]] + t[idx["tm_dreb"]] >= t[idx["oreb"]] + t[idx["dreb"]]


def test_splits_add_up_to_the_season_rows(files: dict[str, dict[str, Any]]) -> None:
    splits = files["splits.json"]
    assert splits["fields"] == list(PLAYER_FIELDS)
    seasons = {s["season"] for s in files["meta.json"]["seasons"]}
    for season in seasons:
        rows = [r for r in splits["rows"] if r[1] == season]
        for player in files[f"seasons/{season}/players.json"]["players"]:
            own = [r for r in rows if r[0] == player["id"]]
            assert [r[2] for r in own] == player["teams"]  # clubs in the order he joined them
            summed = [round(sum(r[4][i] for r in own), 1) for i in range(len(PLAYER_FIELDS))]
            # possessions are rounded to 0.1 in each split and in the season row
            assert summed == pytest.approx(player["totals"]["season"], abs=0.1 * len(own))
            assert all(r[3] for r in own) or not player["dorsal"]
    assert {r[2] for r in splits["rows"]} <= set(files["meta.json"]["teams"])


def test_payload_uses_display_codes_and_flags_early_coordinates(
    files: dict[str, dict[str, Any]],
) -> None:
    meta = files["meta.json"]
    assert "PAO" in meta["teams"] and "PAN" not in meta["teams"]
    flags = {s["season"]: s["coords_validated"] for s in meta["seasons"]}
    assert flags == {2010: False, 2024: True}
    teams = files["seasons/2024/teams.json"]
    assert sum(t["w"] for t in teams["teams"]) == sum(t["l"] for t in teams["teams"]) == 54
    shots = files["seasons/2024/shots.json"]
    assert set(shots["teams"]) == {t["code"] for t in teams["teams"]}
    league_att = sum(cell[2] for cell in shots["league"])
    assert league_att == sum(a for a, _ in teams["league"]["bands"].values())
    games = files["seasons/2024/games.json"]
    assert len(games["games"]) == 54
    assert {line[0] for log in games["logs"].values() for line in log} <= set(games["games"])
    index = files["players.json"]["players"]
    assert len({p["slug"] for p in index}) == len(index)


def test_team_record_counts_regular_season_games_only(inputs: Inputs) -> None:
    games = inputs.games.copy()
    first = games[games["season"] == 2024].index[0]
    games.loc[first, "phase"] = "PO"
    teams = build_payloads(replace(inputs, games=games), NOW)["seasons/2024/teams.json"]["teams"]
    assert sum(t["w"] for t in teams) == sum(t["l"] for t in teams) == 53
    gp = TEAM_FIELDS.index("gp")
    assert sum(t["totals"][gp] for t in teams) == 108  # totals keep every game, two clubs each


def test_attempts_decode_to_the_shot_bins_and_bands(files: dict[str, dict[str, Any]]) -> None:
    attempts = files["seasons/2024/attempts.json"]
    shots, teams = files["seasons/2024/shots.json"], files["seasons/2024/teams.json"]
    bits = attempts["bits"]
    flags = pd.Series(np.array(attempts["flags"], dtype=np.int64))

    def bit(name: str, width: int = 1) -> pd.Series:
        return (flags // 2 ** bits[name]) % 2**width

    frame = pd.DataFrame(
        {
            "x": pd.Series(attempts["x"]) / 100,
            "y": pd.Series(attempts["y"]) / 100,
            "made": bit("made"),
            "value": 2 + bit("three"),
            "band": [BANDS[b] for b in bit("band", 3)],
            "period": flags // 2 ** bits["period"],
            "team": [attempts["teams"][i] for i in attempts["team"]],
        }
    )
    columns = ("x", "y", "flags", "player", "team", "opp")
    assert len({len(attempts[c]) for c in columns}) == 1
    assert frame["period"].between(1, 8).all()
    assert hexbins(frame)[""] == shots["league"]  # centimetres keep every shot in its hex
    assert hexbins(frame, "team") == {c: v["taken"] for c, v in shots["teams"].items()}
    counts = frame.groupby("band")["made"].agg(["size", "sum"])
    assert {b: [int(n), int(m)] for b, (n, m) in counts.iterrows()} == {
        b: v for b, v in teams["league"]["bands"].items() if v[0]
    }


def test_shot_zones_split_bands_by_side_and_corner() -> None:
    shots = pd.DataFrame(
        {
            "x": [0.2, -2.0, 0.0, 2.0, -6.8, 6.8, 0.5, 0.0],
            "y": [0.1, 0.5, 4.0, 0.3, 0.5, 0.5, 7.0, 9.0],
            "band": ["rim", "short", "mid", "short", "three", "three", "three", "deep3"],
        }
    )
    assert list(shot_zones(shots)) == [
        "rim",
        "short_l",
        "mid_c",
        "short_r",
        "corner3_l",
        "corner3_r",
        "three_c",
        "deep3",
    ]


def test_write_stats_replaces_old_seasons(tmp_path: Path) -> None:
    (tmp_path / "seasons" / "1999").mkdir(parents=True)
    write_stats(tmp_path, {"meta.json": {"a": 1}, "seasons/2024/x.json": {"b": [1, 2]}})
    assert not (tmp_path / "seasons" / "1999").exists()
    assert (tmp_path / "seasons/2024/x.json").read_text(encoding="utf-8") == '{"b":[1,2]}\n'


def _repo_layout(tmp: Path) -> Path:
    raw = tmp / "data" / "raw" / "euroleague"
    for path in RAW.rglob("*.gz"):
        target = raw / path.relative_to(RAW)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    (tmp / "reports").mkdir(exist_ok=True)  # the coach expectation's history Elo parameters
    (tmp / "reports" / "backtest_elo_history.json").write_bytes(HISTORY_REPORT.read_bytes())
    return raw


def test_cli_exports_from_the_cache_and_from_the_marts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(publish_mod, "utc_now", lambda: NOW)
    _repo_layout(tmp_path)
    cached = runner.invoke(cli.app, ["export-stats", "--from-cache", "--out", "cached"])
    assert cached.exit_code == 0, cached.output
    assert "2 seasons" in cached.output and "0 played games without a box score" in cached.output

    games, teams = load_cached_games(Path("data/raw/euroleague"))
    MART_PATH.parent.mkdir(parents=True)
    write_tables(
        MART_PATH,
        {
            "games": games.assign(competition="euroleague"),
            "teams": teams.assign(competition="euroleague"),
        },
    )
    marts = runner.invoke(cli.app, ["export-stats", "--out", "marts"])
    assert marts.exit_code == 0, marts.output
    for path in (tmp_path / "cached").rglob("*.json"):
        assert (
            path.read_bytes()
            == (tmp_path / "marts" / path.relative_to(tmp_path / "cached")).read_bytes()
        )


def test_committed_stats_fixture_matches_the_export(
    files: dict[str, dict[str, Any]], tmp_path: Path
) -> None:
    fresh = tmp_path / "stats"
    write_stats(fresh, files)
    if os.environ.get("UPDATE_STATS_FIXTURE"):
        write_stats(OUT, files)
    written = sorted(p.relative_to(fresh).as_posix() for p in fresh.rglob("*.json"))
    committed = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*.json"))
    assert written == committed
    for name in written:
        assert (OUT / name).read_text(encoding="utf-8") == (fresh / name).read_text(
            encoding="utf-8"
        )


# ---- downloads (stats/downloads.py) ----


def _csv(data: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(gzip.decompress(data)), dtype={"dorsal": str})


def test_downloads_manifest_columns_and_window(inputs: Inputs) -> None:
    out = build_downloads(inputs, NOW)
    manifest = json.loads(out["manifest.json"])
    assert manifest["built"] == "2026-09-26T08:00:00Z"
    assert {e["dataset"] for e in manifest["files"]} == set(DATASETS)
    assert sorted({e["season"] for e in manifest["files"]}) == [2010, 2024]
    for e in manifest["files"]:
        assert set(e) == {"dataset", "season", "path", "rows", "bytes", "sha256"}
        assert e["path"] == f"downloads/{e['dataset']}-{e['season']}.csv.gz"
        data = out[e["path"]]
        assert e["bytes"] == len(data) and e["sha256"] == hashlib.sha256(data).hexdigest()
        frame = _csv(data)
        assert len(frame) == e["rows"] > 0
        assert list(frame.columns) == [c for c, _, _ in COLUMNS[e["dataset"]]]
        assert set(frame["season"]) == {e["season"]}
    dictionary = json.loads(out["columns.json"])["datasets"]
    assert [c["name"] for c in dictionary["shots"]] == [c for c, _, _ in COLUMNS["shots"]]


def test_downloads_use_display_codes_and_athens_dates(inputs: Inputs) -> None:
    out = build_downloads(inputs, NOW)
    games = _csv(out["downloads/games-2024.csv.gz"])
    source = inputs.games[inputs.games["season"] == 2024]
    shown = {inputs.codes.get(t, t) for t in (*source["home"], *source["away"])}
    assert set(games["home"]) | set(games["away"]) == shown
    first = source.sort_values("tipoff_utc").iloc[0]["tipoff_utc"]
    assert games["date"].iloc[0] == first.tz_convert("Europe/Athens").strftime("%Y-%m-%d")
    assert (games["season_label"] == "2024-25").all()
    box = _csv(out["downloads/player_box-2024.csv.gz"])
    assert set(box["team"]) <= shown and box["player"].str.contains(" ").any()
    shots = _csv(out["downloads/shots-2024.csv.gz"])
    assert set(shots["made"]) <= {0, 1} and set(shots["band"]) <= set(BANDS)


def test_downloads_are_byte_stable_and_clean_up(inputs: Inputs, tmp_path: Path) -> None:
    first, second = build_downloads(inputs, NOW), build_downloads(inputs, NOW)
    assert first == second
    data = first["downloads/games-2024.csv.gz"]
    assert data[4:8] == b"\0\0\0\0" and b"\r" not in gzip.decompress(data)
    (tmp_path / "old-2019.csv.gz").write_bytes(b"x")
    write_downloads(tmp_path, first)
    assert not (tmp_path / "old-2019.csv.gz").exists()
    assert (tmp_path / "games-2024.csv.gz").read_bytes() == data
    assert (tmp_path / "manifest.json").exists()


def test_downloads_window_follows_site_seasons(
    inputs: Inputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eurohoops.stats.downloads.SITE_SEASONS", 1)
    manifest = json.loads(build_downloads(inputs, NOW)["manifest.json"])
    assert {e["season"] for e in manifest["files"]} == {2024}
    assert [b["season"] for b in manifest["bundles"]] == [2024, None]


def test_downloads_zip_bundles_hold_the_gzipped_files(inputs: Inputs) -> None:
    out = build_downloads(inputs, NOW)
    manifest = json.loads(out["manifest.json"])
    files = manifest["files"]
    bundles = {b["season"]: b for b in manifest["bundles"]}
    assert list(bundles) == [2024, 2010, None]  # newest season first, all seasons last
    for season in (2024, 2010):
        bundle = bundles[season]
        assert bundle["path"] == f"downloads/euroleague-{season}.zip"
        members = {
            f"{e['dataset']}-{season}.csv.gz": out[e["path"]]
            for e in files
            if e["season"] == season
        }
        assert len(members) == len(DATASETS)
        with zipfile.ZipFile(io.BytesIO(out[bundle["path"]])) as archive:
            assert archive.namelist() == sorted(members)
            assert all(i.compress_type == zipfile.ZIP_STORED for i in archive.infolist())
            assert {i.date_time for i in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}
            for name, data in members.items():
                assert archive.read(name) == data
    everything = bundles[None]
    assert everything["path"] == "downloads/euroleague-all-seasons.zip"
    with zipfile.ZipFile(io.BytesIO(out[everything["path"]])) as archive:
        assert archive.namelist() == sorted(f"{e['dataset']}-{e['season']}.csv.gz" for e in files)
    for bundle in manifest["bundles"]:
        data = out[bundle["path"]]
        assert set(bundle) == {"season", "path", "bytes", "sha256"}
        assert bundle["bytes"] == len(data)
        assert bundle["sha256"] == hashlib.sha256(data).hexdigest()
        assert zipfile.is_zipfile(io.BytesIO(data))


def test_downloads_zips_are_byte_stable(inputs: Inputs, tmp_path: Path) -> None:
    first, second = build_downloads(inputs, NOW), build_downloads(inputs, NOW)
    for path in ("downloads/euroleague-2024.zip", "downloads/euroleague-all-seasons.zip"):
        assert first[path] == second[path]
    write_downloads(tmp_path, first)
    assert (tmp_path / "euroleague-all-seasons.zip").read_bytes() == first[
        "downloads/euroleague-all-seasons.zip"
    ]


def test_team_rows_carry_standing_playoff_and_club_seasons(
    inputs: Inputs, files: dict[str, dict[str, Any]]
) -> None:
    for season in (2010, 2024):
        rows = files[f"seasons/{season}/teams.json"]["teams"]
        assert sorted(r["standing"] for r in rows) == list(range(1, len(rows) + 1))
        assert all(isinstance(r["standing"], int) for r in rows)
        assert all(r["playoff"]["result"] in RESULTS + OTHER_RESULTS for r in rows)
        assert all(isinstance(r["el_seasons"], int) and r["el_seasons"] >= 1 for r in rows)
    by_code = {r["code"]: r for r in files["seasons/2024/teams.json"]["teams"]}
    old = {r["code"]: r for r in files["seasons/2010/teams.json"]["teams"]}
    for code, row in by_code.items():
        if code in old:  # a club in both seasons has one more season in the later one
            assert row["el_seasons"] >= old[code]["el_seasons"] + 1


def test_live_season_has_no_playoff_result(inputs: Inputs) -> None:
    live = build_payloads(replace(inputs, live_season=2024), NOW)["seasons/2024/teams.json"]
    assert all(r["playoff"] is None and r["standing"] >= 1 for r in live["teams"])


def _with_last_season(inputs: Inputs, roster_pids: set[str] | None = None) -> Inputs:
    """The fixture has no 2023 box scores. Copy the 2024 lines to 2023 (last season for 2024),
    and put every 2024 player on the 2024 roster, minus ``roster_pids``."""
    players = inputs.box.players
    season = players[players["season"] == 2024]
    box = replace(
        inputs.box,
        players=pd.concat([players, season.assign(season=2023)], ignore_index=True),
    )
    lines = season[["team", "player_id"]].drop_duplicates()
    if roster_pids:
        lines = lines[~lines["player_id"].isin(roster_pids)]
    roster = pd.DataFrame(
        {
            "season": 2024,
            "club": lines["team"].to_numpy(),
            "player_id": lines["player_id"].to_numpy(),
            "start": np.nan,
            "end": np.nan,
        }
    )
    return replace(inputs, box=box, roster=roster)


def test_returning_minutes_are_one_when_the_roster_is_unchanged(inputs: Inputs) -> None:
    found = _continuity_by_club(2024, _with_last_season(inputs))
    assert found and all(c["share"] == pytest.approx(1.0) for c in found.values())
    assert all(c["departures"] == [] for c in found.values())


def test_returning_minutes_name_the_departures_by_last_season_minutes(inputs: Inputs) -> None:
    season = inputs.box.players[inputs.box.players["season"] == 2024]
    club = season.groupby("team")["sec"].sum().idxmax()
    top = season[season["team"] == club].groupby(["player_id", "player"])["sec"].sum()
    gone = str(top.idxmax()[0])
    found = _continuity_by_club(2024, _with_last_season(inputs, {gone}))
    assert found[club]["share"] < 1.0
    assert found[club]["departures"][0]["id"] == gone
    assert found[club]["departures"][0]["sec"] == int(top.max())
    assert found[club]["returning_sec"] == found[club]["last_sec"] - int(top.max())


def test_teams_rows_carry_continuity_or_null(files: dict[str, dict[str, Any]]) -> None:
    rows = files["seasons/2024/teams.json"]["teams"]
    assert all("continuity" in r for r in rows)
    # no 2023 box scores in the fixture, so no club has a last season
    assert all(r["continuity"] is None for r in rows)


def _games(rows: list[tuple[str, str, str, int, int]]) -> pd.DataFrame:
    """(phase, home, away, home points, away points) in tip-off order."""
    return pd.DataFrame(
        [
            {
                "game_id": f"g{i}",
                "phase": phase,
                "home": home,
                "away": away,
                "home_score": hs,
                "away_score": a_s,
                "played": True,
                "tipoff_utc": pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(hours=i),
            }
            for i, (phase, home, away, hs, a_s) in enumerate(rows)
        ]
    )


def test_playoff_results_read_the_phases() -> None:
    games = _games(
        [
            ("RS", "A", "B", 80, 70),
            ("PI", "G", "H", 80, 70),
            ("PO", "A", "F", 80, 70),
            ("PO", "B", "E", 80, 70),
            ("FF", "A", "B", 80, 70),  # semifinals
            ("FF", "C", "D", 70, 80),
            ("FF", "B", "C", 80, 70),  # third place
            ("FF", "A", "D", 80, 70),  # final
        ]
    )
    result = playoff_results(games, list("ABCDEFGHI"))
    assert result == {
        "A": "Champions",
        "D": "Runners-up",
        "B": "Third place",
        "C": "Fourth place",
        "E": "Lost in the playoffs",
        "F": "Lost in the playoffs",
        "G": "Lost in the play-in",
        "H": "Lost in the play-in",
        "I": "Did not qualify",
    }
    no_third = playoff_results(games.drop(index=[6]), list("ABCD"))
    assert no_third["B"] == no_third["C"] == "Lost in the semifinals"
    cancelled = playoff_results(games[games["phase"] == "RS"], ["A", "B"])
    assert set(cancelled.values()) == {"Season cancelled"}


def test_standing_prefers_the_official_table_and_breaks_ties_head_to_head() -> None:
    games = _games(
        [
            ("RS", "A", "B", 80, 70),
            ("RS", "B", "A", 80, 70),
            ("RS", "A", "C", 90, 60),
            ("RS", "C", "A", 60, 70),
            ("RS", "B", "C", 80, 70),
            ("RS", "C", "B", 70, 80),
        ]
    )
    assert regular_season_standings(games, None) == {"A": 1, "B": 2, "C": 3}
    assert regular_season_standings(games, {"B": 1, "A": 2, "C": 3}) == {"B": 1, "A": 2, "C": 3}
    # an official table that disagrees with the wins is ignored
    assert regular_season_standings(games, {"C": 1, "A": 2, "B": 3}) == {"A": 1, "B": 2, "C": 3}
