"""The shadow-log module's interface: what is due, what is stamped, when it refuses.

A fake model supplies the forecast, so these tests do not depend on any real model; the golden
logs (tests/test_shadow_log_golden.py) pin each model's bytes."""

import csv
import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from eurohoops import config
from eurohoops.config import EUROLEAGUE
from eurohoops.shadow_log import (
    LatePredictionError,
    Shadow,
    append_log,
    append_shadow_log,
    is_active,
    run_shadows,
)

COLUMNS = (
    "game_id",
    "season",
    "round",
    "phase",
    "tipoff_utc",
    "home",
    "away",
    "p_home",
    "model",
    "model_version",
    "predicted_at_utc",
)
SEASON = 2026
NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
LEAD = timedelta(hours=48)


def league() -> pd.DataFrame:
    """Round 1 (two confirmed, unplayed games, 10 h out), round 2 far out, one played game."""
    tip = pd.Timestamp("2026-10-01T18:00:00Z")
    rows = [
        ("G1", 1, tip, False),
        ("G2", 1, tip + pd.Timedelta(hours=2), False),
        ("G3", 2, tip + pd.Timedelta(days=7), False),
        ("G0", 1, tip - pd.Timedelta(days=30), True),
    ]
    return pd.DataFrame(
        {
            "game_id": [r[0] for r in rows],
            "season": SEASON,
            "round": [r[1] for r in rows],
            "phase": "RS",
            "tipoff_utc": [r[2] for r in rows],
            "home": "AAA",
            "away": "BBB",
            "played": [r[3] for r in rows],
            "confirmed_date": True,
        }
    )


def forecast_all(due: pd.DataFrame) -> Mapping[str, Mapping[str, str]]:
    return {str(g): {"p_home": "0.6000"} for g in due["game_id"]}


def run(
    log: Path,
    forecast: object = forecast_all,
    *,
    version: str = "v1",
    at: datetime = NOW,
    skip_reason: str | None = None,
) -> int | None:
    return append_shadow_log(
        league(),
        forecast,  # type: ignore[arg-type]
        tag="fake",
        label="FAKE",
        version=version,
        columns=COLUMNS,
        log_path=log,
        season=SEASON,
        round_lead=LEAD,
        clock=lambda: at,
        skip_reason=skip_reason,
    )


def rows(log: Path) -> list[dict[str, str]]:
    with log.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_logs_the_due_games_of_the_open_round_once(tmp_path: Path) -> None:
    log = tmp_path / "fake.csv"
    assert run(log) == 2
    logged = rows(log)
    assert [r["game_id"] for r in logged] == ["G1", "G2"]
    assert {r["model"] for r in logged} == {"fake"} and {r["model_version"] for r in logged} == {
        "v1"
    }
    assert logged[0]["predicted_at_utc"] == "2026-10-01T08:00:00Z"
    assert logged[0]["tipoff_utc"] == "2026-10-01T18:00:00Z"
    first = log.read_bytes()
    assert run(log) == 0  # same version: nothing new
    assert log.read_bytes() == first


def test_a_new_version_is_logged_beside_the_old_one(tmp_path: Path) -> None:
    log = tmp_path / "fake.csv"
    run(log)
    assert run(log, version="v2") == 2
    assert [r["model_version"] for r in rows(log)] == ["v1", "v1", "v2", "v2"]


def test_the_forecast_is_asked_only_for_due_games_and_only_when_there_are_some(
    tmp_path: Path,
) -> None:
    log = tmp_path / "fake.csv"
    asked: list[list[str]] = []

    def spy(due: pd.DataFrame) -> Mapping[str, Mapping[str, str]]:
        asked.append(list(due["game_id"]))
        return forecast_all(due)

    run(log, spy)
    run(log, spy)  # everything logged: the forecast is not built again
    assert asked == [["G1", "G2"]]


def test_a_gated_off_model_logs_nothing_and_says_why(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    log = tmp_path / "fake.csv"

    def never(_due: pd.DataFrame) -> Mapping[str, Mapping[str, str]]:
        raise AssertionError("built a forecast for a gated-off model")

    with caplog.at_level(logging.INFO):
        assert run(log, never, skip_reason="FAKE did not pass: not logged") is None
    assert "FAKE did not pass: not logged" in caplog.text
    assert not log.exists()


def test_a_game_without_a_forecast_is_skipped_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    log = tmp_path / "fake.csv"

    def only_g2(due: pd.DataFrame) -> Mapping[str, Mapping[str, str]]:
        return {g: v for g, v in forecast_all(due).items() if g == "G2"}

    with caplog.at_level(logging.WARNING):
        assert run(log, only_g2) == 1
    assert [r["game_id"] for r in rows(log)] == ["G2"]
    assert "FAKE: 1 upcoming games have no forecast" in caplog.text


def test_a_forecast_with_nothing_to_log_writes_nothing(tmp_path: Path) -> None:
    log = tmp_path / "fake.csv"
    assert run(log, lambda _due: None) == 0
    assert not log.exists()


def test_a_stamp_at_or_after_a_tipoff_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    log = tmp_path / "fake.csv"
    reads = iter([NOW, NOW + timedelta(hours=11)])  # select 10 h before, stamp 1 h after tip-off
    with pytest.raises(LatePredictionError):
        append_shadow_log(
            league(),
            forecast_all,
            tag="fake",
            label="FAKE",
            version="v1",
            columns=COLUMNS,
            log_path=log,
            season=SEASON,
            round_lead=LEAD,
            clock=lambda: next(reads),
        )
    assert not log.exists()


def _append_as_of(log: Path, reads: list[datetime], as_of: datetime) -> int:
    ticks = iter(reads)
    return append_log(
        league(),
        forecast_all,
        tag="fake",
        label="FAKE",
        version="v1",
        columns=COLUMNS,
        log_path=log,
        season=SEASON,
        round_lead=LEAD,
        clock=lambda: next(ticks),
        as_of=as_of,
    )


def test_a_model_forecasting_as_of_an_earlier_instant_is_stamped_with_it(tmp_path: Path) -> None:
    log = tmp_path / "fake.csv"
    assert _append_as_of(log, [NOW, NOW + timedelta(hours=1)], NOW - timedelta(hours=1)) == 2
    assert {r["predicted_at_utc"] for r in rows(log)} == {"2026-10-01T07:00:00Z"}


def test_an_early_stamp_does_not_excuse_a_write_after_a_tipoff(tmp_path: Path) -> None:
    """The frozen-stamp case: stamped 10 h before tip-off, but the forecast ran past it."""
    log = tmp_path / "fake.csv"
    with pytest.raises(LatePredictionError):
        _append_as_of(log, [NOW, NOW + timedelta(hours=11)], NOW)
    assert not log.exists()


def test_the_rows_just_appended_are_handed_on(tmp_path: Path) -> None:
    log = tmp_path / "fake.csv"
    handed: list[list[str]] = []
    append_log(
        league(),
        forecast_all,
        tag="fake",
        label="FAKE",
        version="v1",
        columns=COLUMNS,
        log_path=log,
        season=SEASON,
        round_lead=LEAD,
        clock=lambda: NOW,
        after_append=lambda written: handed.append([str(r["game_id"]) for r in written]),
    )
    assert handed == [["G1", "G2"]]


# --- is_active: the one answer to "does this model log?" ----------------------------------------


@pytest.mark.parametrize(
    ("tag", "flag"),
    [("m5inj", "M5INJ_LIVE_ENABLED"), ("eloc", "ELOC_LIVE_ENABLED"), ("eloh", "ELOH_LIVE_ENABLED")],
)
def test_a_flagged_model_is_active_only_while_its_flag_is_on(
    tag: str, flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, flag, False)
    assert is_active(tag, EUROLEAGUE) is False
    monkeypatch.setattr(config, flag, True)
    assert is_active(tag, EUROLEAGUE) is True


def test_a_flagged_model_without_a_log_path_is_never_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "ELOH_LIVE_ENABLED", True)
    assert is_active("eloh", replace(EUROLEAGUE, eloh_prediction_log=None)) is False


def test_m1_and_m5_have_no_flag_only_a_log_path() -> None:
    assert is_active("m1", EUROLEAGUE) and is_active("m5", EUROLEAGUE)
    assert not is_active("m1", replace(EUROLEAGUE, m1_prediction_log=None))


# --- run_shadows: order, isolation, outcomes ------------------------------------------------


def _ok(rows: int | None) -> Callable[[], int | None]:
    return lambda: rows


def _boom(error: Exception) -> Callable[[], int | None]:
    def run() -> int | None:
        raise error

    return run


def test_active_models_run_in_order_and_say_what_they_appended(tmp_path: Path) -> None:
    said: list[str] = []
    shadows = [
        Shadow("A", tmp_path / "a.csv", _ok(3)),
        Shadow("B", tmp_path / "b.csv", _ok(None)),  # off here: silent
        Shadow("C", tmp_path / "c.csv", _ok(0)),
    ]
    outcomes = run_shadows(shadows, said.append)
    assert said == [
        f"3 A predictions appended to {tmp_path / 'a.csv'}",
        f"0 C predictions appended to {tmp_path / 'c.csv'}",
    ]
    assert [(o.label, o.status, o.rows) for o in outcomes] == [
        ("A", "logged", 3),
        ("B", "inactive", 0),
        ("C", "logged", 0),
    ]


def test_a_failing_model_is_logged_and_the_next_still_runs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shadows = [
        Shadow("A", None, _boom(ValueError("boom"))),
        Shadow("B", tmp_path / "b.csv", _ok(2)),
    ]
    outcomes = run_shadows(shadows, lambda _line: None)
    assert [(o.label, o.status) for o in outcomes] == [("A", "failed"), ("B", "logged")]
    assert "A skipped: its forecast failed" in caplog.text
    assert not any(o.blocking for o in outcomes)


def test_a_required_model_failing_is_reported_as_blocking_but_does_not_stop_the_rest(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shadows = [
        Shadow("M1", None, _boom(ValueError("boom")), required=True),
        Shadow("M5", tmp_path / "m5.csv", _ok(1)),
    ]
    outcomes = run_shadows(shadows, lambda _line: None)
    assert [o.status for o in outcomes] == ["failed", "logged"]
    assert [o.blocking for o in outcomes] == [True, False]
    assert "M1 failed" in caplog.text


@pytest.mark.parametrize("required", [False, True])
def test_a_late_stamp_is_never_swallowed(tmp_path: Path, required: bool) -> None:
    later = Shadow("B", tmp_path / "b.csv", _ok(1))
    shadows = [Shadow("A", None, _boom(LatePredictionError("late")), required=required), later]
    with pytest.raises(LatePredictionError):
        run_shadows(shadows, lambda _line: None)
