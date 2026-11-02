"""Two operational commands of the CLI, with their network and mart reads stubbed at the module
that calls them: ``ingest-bios`` (the count of players with a birth date, and where it writes)
and ``injuries --probe`` (a failed probe is reported, and a torn injury log is a warning)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from eurohoops.cli import ingest as ingest_mod
from eurohoops.cli import live as live_mod
from eurohoops.config import PLAYER_BIOS


@contextmanager
def _no_network() -> Iterator[None]:
    yield None


def test_ingest_bios_reports_the_players_with_a_birth_date_and_writes_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    written: list[tuple[pd.DataFrame, Path]] = []
    monkeypatch.setattr(ingest_mod, "make_client", _no_network)
    monkeypatch.setattr(ingest_mod, "Fetcher", lambda *_a, **_k: None)
    monkeypatch.setattr(ingest_mod, "ingest_bios", lambda *_a, **_k: 3)
    bios = pd.DataFrame({"birth_date": ["1990-01-01", None, "1985-05-05"]})
    monkeypatch.setattr(ingest_mod, "build_bios", lambda _raw: bios)
    monkeypatch.setattr(
        ingest_mod, "write_table", lambda table, path: written.append((table, path))
    )
    ingest_mod.ingest_bios_command()
    assert capsys.readouterr().out == (
        f"fetched 3 EuroLeague seasons; 3 bios, with a birth date: 2; wrote {PLAYER_BIOS}\n"
    )
    ((table, path),) = written
    assert path == PLAYER_BIOS and table.equals(bios)


def test_injuries_probe_reports_a_failed_fetch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(live_mod, "make_client", _no_network)
    monkeypatch.setattr(
        live_mod, "probe_report", lambda _client: {"status": "failed", "detail": "page moved"}
    )
    live_mod.injuries(probe=True)
    assert capsys.readouterr().out == "injuries: probe failed; page moved\n"


def test_a_torn_injury_log_is_a_warning_and_nothing_is_printed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="eurohoops")
    monkeypatch.setattr(live_mod, "make_client", _no_network)
    monkeypatch.setattr(live_mod, "read_teams", lambda *_a: pd.DataFrame())
    monkeypatch.setattr(live_mod, "read_games", lambda *_a: pd.DataFrame())
    monkeypatch.setattr(live_mod, "team_name_map", lambda *_a: {})

    def torn(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("the injury log ends mid-row")

    monkeypatch.setattr(live_mod, "record_injuries", torn)
    live_mod.injuries(probe=False)  # returns normally: a warning, never a non-zero exit
    assert "injuries: the injury log ends mid-row; nothing recorded" in caplog.text
