"""``eurohoops backtest --model elor --cv`` / ``--cv-check``: flags, run-once guards, no writes."""

from __future__ import annotations

import dataclasses
import gzip
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from typer.testing import CliRunner

from eurohoops import cli
from eurohoops.cli import backtest as backtest_mod
from eurohoops.config import EUROLEAGUE, ElorCv
from eurohoops.eval.elor_cv import ElorInputs
from eurohoops.ingest.bios import el_people_path
from eurohoops.models.player_part import PlayerPartError, el_player_ratings
from tests import elor_synthetic as syn

runner = CliRunner()
PEOPLE = (Path(__file__).parent / "fixtures" / "elor" / "el_people_E2026.json").read_bytes()


class _Stop(Exception):
    """Raised by a fake input builder: the command got past its guards."""


def _stop() -> ElorInputs:
    raise _Stop


@pytest.fixture
def elor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ElorCv:
    """A tmp report location, the live-parameter check passing and inputs that stop the run."""
    monkeypatch.chdir(tmp_path)
    spec = syn.spec(tmp_path / "reports")
    monkeypatch.setattr(backtest_mod, "ELOR_CV", spec)
    monkeypatch.setattr(backtest_mod, "_live_elo_params_match", lambda: True)
    monkeypatch.setattr(backtest_mod, "_elor_inputs", _stop)
    return spec


@pytest.mark.usefixtures("elor")
@pytest.mark.parametrize(
    "args",
    [
        ["backtest", "--model", "elor"],
        ["backtest", "--model", "elor", "--cv", "--cv-check"],
        ["backtest", "--cv"],
        ["backtest", "--model", "m5", "--cv-check"],
    ],
)
def test_elor_flags_refuse_other_models_competitions_and_combinations(args: list[str]) -> None:
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 1
    assert not isinstance(result.exception, _Stop)


def test_cv_refuses_when_the_report_exists(elor: ElorCv, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: True)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: True)
    elor.report.parent.mkdir(parents=True)
    elor.report.write_text("{}", encoding="utf-8")
    result = runner.invoke(cli.app, ["backtest", "--model", "elor", "--cv"])
    assert result.exit_code == 1 and not isinstance(result.exception, _Stop)


@pytest.mark.usefixtures("elor")
@pytest.mark.parametrize(("clean", "on_main"), [(False, True), (True, False)])
def test_cv_refuses_a_dirty_tree_or_a_head_off_main(
    monkeypatch: pytest.MonkeyPatch, clean: bool, on_main: bool
) -> None:
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: clean)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: on_main)
    result = runner.invoke(cli.app, ["backtest", "--model", "elor", "--cv"])
    assert result.exit_code == 1 and not isinstance(result.exception, _Stop)


@pytest.mark.usefixtures("elor")
def test_cv_passes_the_guards_on_a_clean_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: True)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: True)
    result = runner.invoke(cli.app, ["backtest", "--model", "elor", "--cv"])
    assert isinstance(result.exception, _Stop)


@pytest.mark.usefixtures("elor")
def test_both_flags_refuse_other_elo_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "_live_elo_params_match", lambda: False)
    for flag in ("--cv", "--cv-check"):
        result = runner.invoke(cli.app, ["backtest", "--model", "elor", flag])
        assert result.exit_code == 1 and not isinstance(result.exception, _Stop)


def test_cv_check_prints_and_writes_nothing(
    elor: ElorCv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backtest_mod, "_elor_inputs", syn.inputs)
    monkeypatch.setattr(backtest_mod, "_elor_live_priors", lambda: {})
    monkeypatch.setattr(
        backtest_mod, "is_clean_tree", lambda: False
    )  # a dirty tree is fine for a check
    before = sorted(tmp_path.rglob("*"))
    result = runner.invoke(cli.app, ["backtest", "--model", "elor", "--cv-check"])
    assert result.exit_code == 0, result.output
    assert '"per_fold_games"' in result.output and '"start_dates"' in result.output
    assert '"newcomer_priors_live"' in result.output
    assert sorted(tmp_path.rglob("*")) == before
    assert not elor.report.exists()


def test_cv_writes_the_report_and_games_once(elor: ElorCv, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "_elor_inputs", syn.inputs)
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: True)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: True)
    monkeypatch.setattr(backtest_mod, "git_head_sha", lambda: "f" * 40)
    elor.report.parent.mkdir(parents=True)
    result = runner.invoke(cli.app, ["backtest", "--model", "elor", "--cv"])
    assert result.exit_code == 0, result.output
    report = json.loads(elor.report.read_text(encoding="utf-8"))
    assert report["git_head"] == "f" * 40 and report["model"] == "elor"
    assert len(pd.read_csv(elor.games_report)) == report["scored_games"]
    again = runner.invoke(cli.app, ["backtest", "--model", "elor", "--cv"])
    assert again.exit_code == 1


def test_live_elo_params_check_reads_the_committed_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert backtest_mod._live_elo_params_match()  # the repository's reports/backtest_elo.json
    monkeypatch.chdir(tmp_path)
    assert not backtest_mod._live_elo_params_match()
    report = EUROLEAGUE.live_backtest.report
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"tuned": {"k": 30, "hca": 90, "reversion": 0.25}}))
    assert not backtest_mod._live_elo_params_match()


def _fake_m5_inputs(*args: object) -> tuple[object, pd.DataFrame]:
    games, box = syn.games_and_box()
    fake = dataclasses.make_dataclass("Fake", ["games", "player_games"])(games, box)
    return fake, games


def test_elor_inputs_read_the_roster_cache_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(backtest_mod, "ELOR_CV", syn.spec(tmp_path, folds=(2026,)))
    monkeypatch.setattr(backtest_mod, "_m5_inputs", _fake_m5_inputs)
    games, _ = syn.games_and_box()
    lookups = [None] * len(games)
    ratings = dataclasses.make_dataclass("R", ["frame", "wf", "possessions"])(
        games, dataclasses.make_dataclass("W", ["lookups"])(lookups), pd.Series(dtype=float)
    )
    monkeypatch.setattr(backtest_mod, "_el_player_ratings", lambda inputs, frame: ratings)
    with pytest.raises(Exception) as missing:
        backtest_mod._elor_inputs()
    assert getattr(missing.value, "exit_code", None) == 1
    path = el_people_path(EUROLEAGUE.raw_dir, 2026)
    path.parent.mkdir(parents=True)
    path.write_bytes(gzip.compress(PEOPLE))
    built = backtest_mod._elor_inputs()
    assert len(built.roster) == 4
    assert not built.has_state(2026, 0.0)
    assert built.season_end_rating(2025, "A1") is None  # no lookups at all


def test_elor_live_priors_cover_the_live_season(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "_m5_inputs", _fake_m5_inputs)
    monkeypatch.setattr(backtest_mod, "ELOR_CV", syn.spec())
    games, _ = syn.games_and_box()
    ordered = games.sort_values("tipoff_utc").reset_index(drop=True)
    lookups = syn.fake_lookups(ordered)
    ratings = dataclasses.make_dataclass("R", ["frame", "wf", "possessions"])(
        ordered, dataclasses.make_dataclass("W", ["lookups"])(lookups), pd.Series(dtype=float)
    )
    monkeypatch.setattr(backtest_mod, "_el_player_ratings", lambda inputs, frame: ratings)
    priors = backtest_mod._elor_live_priors()
    assert set(priors) == {2025, 2026, backtest_mod.LIVE_SEASON}
    live = priors[backtest_mod.LIVE_SEASON]
    assert live.history == (2024, 2025) and live.share > 0 and live.rating != 0


def test_player_ratings_refuse_a_wrong_m3_variant_or_missing_stints(tmp_path: Path) -> None:
    report = tmp_path / "m3.json"
    report.write_text(json.dumps({"chosen": {"variant": "rapm"}}), encoding="utf-8")
    games, box = syn.games_and_box()
    mart = tmp_path / "empty.duckdb"
    duckdb.connect(str(mart)).close()
    with pytest.raises(PlayerPartError, match="rapm_spm"):
        el_player_ratings(games, box, pd.DataFrame(), m3_report=report, mart_path=mart)
    report.write_text(json.dumps({"chosen": {"variant": "rapm_spm"}}), encoding="utf-8")
    with pytest.raises(PlayerPartError, match="stints"):
        el_player_ratings(games, box, pd.DataFrame(), m3_report=report, mart_path=mart)
