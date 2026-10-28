import dataclasses
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import httpx
import pandas as pd
import pytest
from typer.testing import CliRunner

from eurohoops import cli
from eurohoops.cli import backtest as backtest_mod
from eurohoops.cli import ingest as ingest_mod
from eurohoops.cli import live as live_mod
from eurohoops.cli import publish as publish_mod
from eurohoops.config import (
    EUROLEAGUE,
    INJURY_LOG,
    M5,
    M5_RETUNE,
    MART_PATH,
    ODDS_TEAMS,
    POSSESSION_REPORT,
    SITE_DATA,
    STINT_REPORT,
    STINTS_MART_REPORT,
    TEAM_CONTINUITY_REPORT,
    M5Backtest,
)
from eurohoops.eval.backtest import load_tuned_model
from eurohoops.eval.m5_retune import retune_backtest_spec
from eurohoops.ingest.cache import write_atomic
from eurohoops.marts import read_games, write_tables
from eurohoops.parse.games import write_table
from tests.conftest import FIXTURES, make_games, make_team_games, write_pipeline
from tests.test_ingest import FakeApi
from tests.test_m1_backtest import SPEC as M1_SPEC
from tests.test_stints import game, write_game
from tests.test_stints_mart import full_box

runner = CliRunner()
NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def pipeline(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Staged + built synthetic EuroLeague data covering every backtest split."""
    write_pipeline(make_games({s: True for s in range(2007, 2026)} | {2026: False}))
    monkeypatch.setattr(live_mod, "utc_now", lambda: NOW)
    monkeypatch.setattr(publish_mod, "utc_now", lambda: NOW)
    return workdir


def invoke(*args: str) -> str:
    result = runner.invoke(cli.app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


def seed_schedule(season: int) -> None:
    """A finished season's schedule in the raw cache: the 2024 fixture with its game ids renamed."""
    payload = (FIXTURES / "schedule_E2024.json").read_bytes()
    write_atomic(
        EUROLEAGUE.raw_dir / "schedule" / f"E{season}.json.gz",
        payload.replace(b"E2024_", f"E{season}_".encode()),
    )


@pytest.mark.usefixtures("workdir", "no_sleep")
def test_ingest_then_build(monkeypatch: pytest.MonkeyPatch) -> None:
    el_api = FakeApi()
    transport = httpx.MockTransport(el_api)
    monkeypatch.setattr(ingest_mod, "make_client", lambda: httpx.Client(transport=transport))
    seed_schedule(2024)
    invoke("ingest", "--seasons", "2024", "2026", "--details")
    # the finished season comes from the cache; only the live schedule is fetched
    schedules = [c for c in el_api.calls if c.endswith("/games")]
    assert len(schedules) == 1 and schedules[0].endswith("/seasons/E2026/games")
    invoke("build")
    assert list(read_games(MART_PATH, "euroleague")["season"].unique()) == [2024, 2026]
    invoke("continuity")
    continuity = json.loads(TEAM_CONTINUITY_REPORT.read_text())
    assert set(continuity) == {"euroleague"}
    assert continuity["euroleague"]["seasons"]["2024"]["first_season_in_data"]
    assert "2026" in continuity["euroleague"]["seasons"]


@pytest.mark.usefixtures("workdir", "no_sleep")
def test_ingest_from_season_adds_the_range_to_the_chosen_seasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    transport = httpx.MockTransport(api)
    monkeypatch.setattr(ingest_mod, "make_client", lambda: httpx.Client(transport=transport))
    monkeypatch.setattr(ingest_mod, "LIVE_SEASON", 2026)
    invoke("ingest", "--from-season", "2026")
    assert list(pd.read_parquet(EUROLEAGUE.staging_games)["season"].unique()) == [2026]
    seed_schedule(2024)
    invoke("ingest", "--seasons", "2024", "--from-season", "2026")
    assert sorted(pd.read_parquet(EUROLEAGUE.staging_games)["season"].unique()) == [2024, 2026]


@pytest.mark.usefixtures("workdir", "no_sleep")
def test_default_ingest_keeps_the_2007_history(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every finished season is cached (the 2024 fixture under each name; only the season label
    # matters here), so the only network call a default ingest may make is the live season.
    for season in range(2007, 2026):
        seed_schedule(season)
    api = FakeApi()
    transport = httpx.MockTransport(api)
    monkeypatch.setattr(ingest_mod, "make_client", lambda: httpx.Client(transport=transport))
    monkeypatch.setattr(ingest_mod, "LIVE_SEASON", 2026)
    invoke("ingest")
    assert len(api.calls) == 1 and api.calls[0].endswith("/seasons/E2026/games")
    staged = pd.read_parquet(EUROLEAGUE.staging_games)
    assert sorted(staged["season"].unique()) == list(range(2007, 2027))


@pytest.mark.usefixtures("workdir", "no_sleep")
def test_current_only_stages_the_live_season_and_rejects_season_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    transport = httpx.MockTransport(api)
    monkeypatch.setattr(ingest_mod, "make_client", lambda: httpx.Client(transport=transport))
    monkeypatch.setattr(ingest_mod, "LIVE_SEASON", 2026)
    invoke("ingest", "--current-only")
    assert len(api.calls) == 1
    assert list(pd.read_parquet(EUROLEAGUE.staging_games)["season"].unique()) == [2026]
    result = runner.invoke(cli.app, ["ingest", "--current-only", "--seasons", "2024"])
    assert result.exit_code != 0


@pytest.mark.usefixtures("workdir", "no_sleep")
def test_ingest_stops_with_an_error_when_a_finished_season_is_not_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeApi()
    transport = httpx.MockTransport(api)
    monkeypatch.setattr(ingest_mod, "make_client", lambda: httpx.Client(transport=transport))
    monkeypatch.setattr(ingest_mod, "LIVE_SEASON", 2026)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 1
    assert api.calls == []


@pytest.mark.usefixtures("workdir")
def test_ingest_rejects_junk_arguments() -> None:
    result = runner.invoke(cli.app, ["ingest", "--seasons", "2024", "--detials"])
    assert result.exit_code != 0


@pytest.mark.usefixtures("workdir")
def test_the_competition_option_is_gone() -> None:
    assert runner.invoke(cli.app, ["ingest", "--competition", "gbl"]).exit_code != 0
    assert runner.invoke(cli.app, ["backtest", "--competition", "gbl"]).exit_code != 0


@pytest.mark.usefixtures("pipeline")
def test_backtest_predict_score_publish_end_to_end() -> None:
    output = invoke("backtest")
    assert "backtest_elo_history.json" in output
    for spec in (EUROLEAGUE.live_backtest, *EUROLEAGUE.history_backtests):
        grid = set(product(spec.grid.k, spec.grid.hca, spec.grid.reversion))
        report = json.loads(spec.report.read_text())
        tuned = report["tuned"]
        assert (tuned["k"], tuned["hca"], tuned["reversion"]) in grid
        assert not tuned["frozen"]
        assert {k: report["grid"]["best"][k] for k in ("k", "hca", "reversion")} == {
            k: tuned[k] for k in ("k", "hca", "reversion")
        }
        assert report["grid"]["best_minus_tuned_log_loss"]["test"]["mean"] == 0.0
        assert report["seasons"]["test"] == list(spec.test)
        assert report["model_version"] == load_tuned_model(spec.report).version()

    invoke("predict")
    assert len(pd.read_csv(EUROLEAGUE.prediction_log)) > 0
    invoke("score")
    invoke("publish")
    data = json.loads(SITE_DATA.read_text(encoding="utf-8"))
    (el,) = data["competitions"]
    assert el["key"] == "euroleague"
    assert any(r["name"] == "Team AAA & Co" for r in el["ratings"])


@pytest.mark.usefixtures("pipeline")
def test_predict_exits_non_zero_when_stamp_is_not_before_tipoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoke("backtest")
    ticks: Iterator[datetime] = iter([NOW, datetime(2026, 10, 1, 18, 0, tzinfo=UTC)])
    monkeypatch.setattr(live_mod, "utc_now", lambda: next(ticks))
    result = runner.invoke(cli.app, ["predict"])
    assert result.exit_code == 1
    assert not EUROLEAGUE.prediction_log.exists()


@pytest.mark.usefixtures("pipeline")
def test_a_failing_m5_forecast_never_blocks_the_elo_log(monkeypatch: pytest.MonkeyPatch) -> None:
    invoke("backtest")

    def broken(*_args: object, **_kwargs: object) -> int:
        raise ValueError("no tuning game with finite forecasts to fit the margin model on")

    monkeypatch.setattr(live_mod, "load_m5", lambda _path: object())
    monkeypatch.setattr(live_mod, "predict_upcoming_m5", broken)
    result = runner.invoke(cli.app, ["predict"])
    assert result.exit_code == 0
    assert EUROLEAGUE.prediction_log.exists()


@pytest.mark.usefixtures("pipeline")
def test_a_failing_elor_forecast_never_blocks_the_elo_log(monkeypatch: pytest.MonkeyPatch) -> None:
    invoke("backtest")

    def broken(*_args: object, **_kwargs: object) -> int:
        raise ValueError("roster club codes do not match the games mart")

    monkeypatch.setattr(live_mod, "load_elor", lambda _path: object())
    monkeypatch.setattr(live_mod, "predict_upcoming_elor", broken)
    result = runner.invoke(cli.app, ["predict"])
    assert result.exit_code == 0
    assert EUROLEAGUE.prediction_log.exists()


def odds_api(status: int) -> httpx.MockTransport:
    events = [
        {
            "commence_time": "2026-10-01T18:00:00Z",
            "home_team": "Alpha",
            "away_team": "Bravo",
            "bookmakers": [
                {
                    "key": "a",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Alpha", "price": 1.5},
                                {"name": "Bravo", "price": 2.5},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    body = events if status == 200 else {"error_code": "INVALID_KEY"}
    headers = {"x-requests-last": "3", "x-requests-remaining": "400"}
    return httpx.MockTransport(lambda request: httpx.Response(status, json=body, headers=headers))


@pytest.mark.usefixtures("pipeline")
def test_odds_records_a_consensus_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODDS_API_KEY", "fake-key")
    ODDS_TEAMS.parent.mkdir(parents=True, exist_ok=True)
    ODDS_TEAMS.write_text("odds_api_name,team,verified\nAlpha,AAA,no\nBravo,BBB,no\n")
    monkeypatch.setattr(live_mod, "make_client", lambda: httpx.Client(transport=odds_api(200)))
    output = invoke("odds")
    assert "1 consensus rows from 1 events" in output
    assert "requests remaining 400" in output
    assert EUROLEAGUE.odds_log is not None
    [row] = pd.read_csv(EUROLEAGUE.odds_log).to_dict("records")
    assert (row["game_id"], row["p_home"]) == ("E2026_1", 0.625)
    invoke("backtest")
    invoke("score")
    assert json.loads(EUROLEAGUE.scorecard.read_text())["market"]["n"] == 0  # not played yet


@pytest.mark.usefixtures("pipeline")
def test_odds_fails_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    result = runner.invoke(cli.app, ["odds"])
    assert result.exit_code == 1
    monkeypatch.setenv("ODDS_API_KEY", "fake-key")
    monkeypatch.setattr(live_mod, "make_client", lambda: httpx.Client(transport=odds_api(401)))
    result = runner.invoke(cli.app, ["odds"])
    assert result.exit_code == 1
    assert "fake-key" not in result.output


@pytest.mark.usefixtures("pipeline")
def test_injuries_records_a_snapshot_and_never_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    page = Path(__file__).parent / "fixtures" / "basketnews" / "injury_report.html"

    def serve(status: int) -> httpx.Client:
        body = page.read_bytes()
        return httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(status, content=body))
        )

    monkeypatch.setattr(live_mod, "make_client", lambda: serve(200))
    output = invoke("injuries")
    assert "appended; 5 rows, 3 teams" in output
    assert "Anadolu Efes Istanbul" in output  # the fixture season has no such team: unmapped
    assert len(pd.read_csv(INJURY_LOG)) == 5
    assert "unchanged" in invoke("injuries")
    monkeypatch.setattr(live_mod, "make_client", lambda: serve(503))
    assert "failed" in invoke("injuries")
    assert len(pd.read_csv(INJURY_LOG)) == 5


@pytest.mark.usefixtures("pipeline")
def test_injuries_probe_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    page = Path(__file__).parent / "fixtures" / "basketnews" / "injury_report.html"
    body = page.read_bytes()
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    )
    monkeypatch.setattr(live_mod, "make_client", lambda: client)
    before = INJURY_LOG.read_bytes() if INJURY_LOG.exists() else b""
    assert "probe ok; 5 rows" in invoke("injuries", "--probe")
    assert (INJURY_LOG.read_bytes() if INJURY_LOG.exists() else b"") == before


@pytest.mark.usefixtures("pipeline")
def test_build_writes_team_games_and_possessions_validates_them() -> None:
    failed = runner.invoke(cli.app, ["possessions"])
    assert failed.exit_code == 1  # the marts have no team_games before `build`
    assert "team_games: 0 games" in invoke("build")  # synthetic games have no box scores
    output = invoke("possessions")
    assert "0 points mismatches; no EuroLeague play-by-play cached" in output
    report = json.loads(POSSESSION_REPORT.read_text(encoding="utf-8"))
    assert report["missing_games"][0]["reason"] == "no cached box score (ingest --details)"


@pytest.mark.usefixtures("workdir")
def test_stints_writes_a_reproducible_report() -> None:
    write_game(EUROLEAGUE.raw_dir, 2024, 5, *game())
    write_game(EUROLEAGUE.raw_dir, 2025, 9, *game(drop_in=True))
    output = invoke("stints")
    assert "2 games: all checks 50%" in output
    first = STINT_REPORT.read_bytes()
    invoke("stints")
    assert STINT_REPORT.read_bytes() == first
    assert json.loads(first)["failing_games"].keys() == {"E2025_9"}


@pytest.mark.usefixtures("pipeline")
def test_stints_mart_builds_tables_and_a_reproducible_report() -> None:
    assert runner.invoke(cli.app, ["stints", "--mart"]).exit_code == 1  # no team_games yet
    pbp, box = game()
    write_game(EUROLEAGUE.raw_dir, 2024, 1, pbp, full_box(box))  # E2024_1 is AAA vs BBB
    invoke("build")
    output = invoke("stints", "--mart")
    assert "pass rate 2011-14 no games, 2015+ 100.0%" in output
    first = STINTS_MART_REPORT.read_bytes()
    invoke("stints", "--mart")
    assert STINTS_MART_REPORT.read_bytes() == first
    assert b"NaN" not in first
    report = json.loads(first)
    assert report["games"] == 1
    assert report["pbp_vs_box_possessions"]["2011_2014"] is None
    assert (
        len(report["not_cached"])
        == len(read_games(MART_PATH, "euroleague").query("played and season >= 2011")) - 1
    )


@pytest.fixture
def small_m1(pipeline: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The pipeline with the small test grid in the EuroLeague M1 spec."""
    assert EUROLEAGUE.m1 is not None
    spec = dataclasses.replace(
        EUROLEAGUE.m1,
        elo_grid=M1_SPEC.elo_grid,
        rating_grid=M1_SPEC.rating_grid,
        pace_grid=M1_SPEC.pace_grid,
    )
    el = dataclasses.replace(EUROLEAGUE, m1=spec)
    monkeypatch.setattr(backtest_mod, "EUROLEAGUE", el)
    monkeypatch.setattr(live_mod, "EUROLEAGUE", el)
    return pipeline


def test_backtest_m1_writes_a_reproducible_report(small_m1: Path) -> None:
    failed = runner.invoke(cli.app, ["backtest", "--model", "m1"])
    assert failed.exit_code == 1  # no team_games in the marts yet
    rows = make_team_games(read_games(MART_PATH, "euroleague"))
    write_tables(MART_PATH, {"team_games": rows})
    output = invoke("backtest", "--model", "m1")
    assert "gate (" in output
    assert "MLflow parent run" in output
    assert (small_m1 / "mlruns" / "mlflow.db").exists()  # the working directory, not the repo
    assert EUROLEAGUE.m1 is not None
    first = EUROLEAGUE.m1.report.read_bytes()
    invoke("backtest", "--model", "m1")
    assert EUROLEAGUE.m1.report.read_bytes() == first
    assert "test" not in json.loads(first)["metrics"]

    # E7: predict appends M1 rows to its own log (for a passed gate) and never touches Elo's.
    invoke("backtest")
    assert EUROLEAGUE.m1_prediction_log is not None
    passed = json.loads(EUROLEAGUE.m1.report.read_text(encoding="utf-8"))["gate"]["passed"]
    output = invoke("predict")
    elo_log = EUROLEAGUE.prediction_log.read_bytes()
    assert EUROLEAGUE.m1_prediction_log.exists() == passed
    if passed:
        assert "3 M1 predictions appended" in output
        m1_log = EUROLEAGUE.m1_prediction_log.read_bytes()
        assert "0 M1 predictions appended" in invoke("predict")
        assert EUROLEAGUE.m1_prediction_log.read_bytes() == m1_log
    assert EUROLEAGUE.prediction_log.read_bytes() == elo_log
    invoke("score")
    card = json.loads(EUROLEAGUE.scorecard.read_text(encoding="utf-8"))
    assert card["m1"]["rows_in_log"] == (3 if passed else 0)
    invoke("publish")
    site = json.loads(SITE_DATA.read_text(encoding="utf-8"))
    assert all(c["scorecard"]["m1"]["n"] == 0 for c in site["competitions"])


class _Stop(Exception):
    """Ends a backtest command right after the fake _m5_inputs has recorded its spec."""


def test_backtest_m5_retune_builds_inputs_with_the_retune_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs: list[M5Backtest] = []

    def fake_inputs(comp: object, spec: M5Backtest) -> None:
        specs.append(spec)
        raise _Stop

    monkeypatch.setattr(backtest_mod, "_m5_inputs", fake_inputs)
    result = runner.invoke(cli.app, ["backtest", "--model", "m5", "--retune-check"])
    assert isinstance(result.exception, _Stop), result.output
    (spec,) = specs
    assert spec == retune_backtest_spec(M5_RETUNE)
    assert spec.test[-1] == M5_RETUNE.folds[-1]
    assert spec != M5


@pytest.mark.parametrize("args", [["backtest", "--retune"]])
def test_retune_flags_refuse_other_models(args: list[str]) -> None:
    assert runner.invoke(cli.app, args).exit_code == 1


@pytest.mark.usefixtures("pipeline")
def test_build_reports_team_continuity() -> None:
    def staged(rows: list[tuple[int, str, str]]) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=["season", "team", "name"])

    write_table(
        staged([(2025, "MCO", "AS Monaco"), (2025, "PAN", "Pana"), (2026, "PAN", "Pana")]),
        EUROLEAGUE.staging_team_seasons,
    )
    output = invoke("build")
    assert "euroleague 2026 teams: left MCO" in output
    assert not TEAM_CONTINUITY_REPORT.exists()  # build never writes the committed report
    assert "wrote" in invoke("continuity")
    report = json.loads(TEAM_CONTINUITY_REPORT.read_text())
    assert set(report) == {"euroleague"}


@pytest.mark.usefixtures("pipeline")
def test_continuity_needs_team_seasons_in_the_marts() -> None:
    invoke("build")  # the synthetic pipeline stages no team seasons
    result = runner.invoke(cli.app, ["continuity"])
    assert result.exit_code == 1
