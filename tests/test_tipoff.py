from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from eurohoops import cli
from eurohoops.cli import live as live_mod
from eurohoops.marts import read_games, write_tables
from eurohoops.tipoff import first_tipoff_on
from tests.conftest import make_games

TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


def at(hour: int, minute: int = 0, day: int = 20) -> pd.Timestamp:
    return pd.Timestamp(datetime(2026, 10, day, hour, minute, tzinfo=UTC))


def small_mart(tmp_path: Path) -> Path:
    """Unplayed by default; the rows below set the tip-offs, played flags and confirmations."""
    games = make_games({2026: False}).iloc[:6].copy()
    games["tipoff_utc"] = [
        at(18),  # unplayed, confirmed, today
        at(15, 30),  # unplayed, confirmed, today: the first of the day
        at(12),  # played today (excluded)
        at(10),  # unconfirmed today (excluded)
        at(9, 0, day=21),  # tomorrow (excluded)
        at(8, 0, day=19),  # yesterday (excluded)
    ]
    games["played"] = [False, False, True, False, False, False]
    games["home_score"] = [None, None, 90, None, None, None]
    games["away_score"] = [None, None, 80, None, None, None]
    games["confirmed_date"] = [True, True, True, False, True, True]
    games["competition"] = "euroleague"
    mart = tmp_path / "mart.duckdb"
    write_tables(mart, {"games": games})
    return mart


def test_first_unplayed_confirmed_tipoff_of_the_utc_day(tmp_path: Path) -> None:
    games = read_games(small_mart(tmp_path), "euroleague")
    assert first_tipoff_on(games, TODAY) == at(15, 30)


def test_no_game_today_gives_none(tmp_path: Path) -> None:
    games = read_games(small_mart(tmp_path), "euroleague")
    assert first_tipoff_on(games, date(2026, 10, 22)) is None


def test_all_of_todays_games_played_gives_none(tmp_path: Path) -> None:
    games = read_games(small_mart(tmp_path), "euroleague")
    games = games.assign(played=True, home_score=80, away_score=70)
    assert first_tipoff_on(games, TODAY) is None


def test_cli_prints_the_iso_utc_time_or_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(live_mod, "MART_PATH", small_mart(tmp_path))
    monkeypatch.setattr(live_mod, "utc_now", lambda: NOW)
    runner = CliRunner()
    result = runner.invoke(cli.app, ["first-tipoff", "--today"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "2026-10-20T15:30:00Z"
    monkeypatch.setattr(live_mod, "utc_now", lambda: datetime(2026, 10, 22, 9, tzinfo=UTC))
    result = runner.invoke(cli.app, ["first-tipoff", "--today"])
    assert result.exit_code == 0, result.output
    assert result.output == ""
