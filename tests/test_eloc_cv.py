"""ELOC CV harness (``eval/eloc_cv.py``): leakage, the report's shape, the read-only check, and the
run-once guards of ``eurohoops backtest --model eloc --cv`` (no run reaches the games loader)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from eurohoops import cli
from eurohoops.cli import backtest as backtest_mod
from eurohoops.config import ElocCv
from eurohoops.eval import eloc_cv
from eurohoops.models.elo import prepare, replay
from tests import eloc_synthetic as syn

runner = CliRunner()


def _fold_fit(games_frame, spec: ElocCv, fold: int) -> tuple[float, float]:
    ctx = eloc_cv.build_context(games_frame, spec)
    cal = eloc_cv.fold_calibration(ctx, spec, fold)
    return cal.a, cal.b


def _diffs(games_frame, spec: ElocCv) -> np.ndarray:
    ctx = eloc_cv.build_context(games_frame, spec)
    return ctx.elo_diff


def test_later_edits_leave_the_fold_fit_unchanged(tmp_path: Path) -> None:
    """Editing any game of season 2011 or later (the fold's own season and after) cannot move
    fold 2011's (a, b), and cannot move Elo's pre-game differences before 2011."""
    spec = syn.spec(tmp_path / "r.json")
    base = syn.games()
    later = (base["season"] >= 2011).to_numpy()
    edited = syn.with_scores_swapped(base, later)
    assert _fold_fit(base, spec, 2011) == _fold_fit(edited, spec, 2011)
    before = (base["season"] < 2011).to_numpy()
    base_ctx = eloc_cv.build_context(base, spec)
    edit_ctx = eloc_cv.build_context(edited, spec)
    early = base_ctx.season < 2011
    np.testing.assert_array_equal(base_ctx.elo_diff[early], edit_ctx.elo_diff[early])
    assert before.any()


def test_control_an_earlier_edit_moves_the_later_fit(tmp_path: Path) -> None:
    """The control: a season-2010 result does enter fold 2011's fit, so the test above can fail."""
    spec = syn.spec(tmp_path / "r.json")
    base = syn.games()
    edited = syn.with_scores_swapped(base, (base["season"] == 2010).to_numpy())
    assert _fold_fit(base, spec, 2011) != _fold_fit(edited, spec, 2011)


def test_the_fit_window_stops_before_the_fold_season(tmp_path: Path) -> None:
    spec = syn.spec(tmp_path / "r.json")
    ctx = eloc_cv.build_context(syn.games(), spec)
    train = eloc_cv.fold_train(ctx, spec, 2010)
    assert set(ctx.season[train]) == {2008, 2009}
    assert int(train.sum()) == 2 * syn.GAMES_PER_SEASON


def test_cv_check_counts_games_and_fits_nothing(tmp_path: Path) -> None:
    summary = eloc_cv.cv_check(syn.games(), syn.spec(tmp_path / "r.json"))
    assert summary["elo_replay_games"] == len(syn.SEASONS) * syn.GAMES_PER_SEASON
    assert summary["per_fold"]["2010"] == {
        "fit_seasons": [2008, 2009],
        "fit_games": 2 * syn.GAMES_PER_SEASON,
        "scored_games": syn.GAMES_PER_SEASON,
    }
    assert summary["per_fold"]["2011"]["fit_games"] == 3 * syn.GAMES_PER_SEASON
    assert summary["live_fit"] == {"seasons": [2008, 2011], "games": 4 * syn.GAMES_PER_SEASON}
    assert "elo" not in summary and "eloc" not in summary  # no metrics


def test_run_cv_reports_the_protocol_shape(tmp_path: Path) -> None:
    spec = syn.spec(tmp_path / "r.json")
    report, detail = eloc_cv.run_cv(syn.games(), spec=spec, git_head="test")
    assert report["model"] == "eloc"
    assert set(report["per_fold"]) == {"2010", "2011"}
    assert report["scored_games"] == 2 * syn.GAMES_PER_SEASON == len(detail)
    for key in ("elo", "eloc"):
        assert set(report[key]) >= {"n", "log_loss", "brier", "ece", "per_season"}
    criteria = report["shadow_criteria"]
    assert criteria["all"] == (
        criteria["below_elo"] and criteria["non_inferior"] and criteria["worth_a_version"]
    )
    live = report["live_fit"]
    assert live["seasons"] == [2008, 2011] and live["games"] == 4 * syn.GAMES_PER_SEASON
    assert detail["p_eloc"].between(0.0, 1.0).all()
    assert (detail["p_elo"] == detail["p_elo"].round(6)).all()


def test_run_cv_is_deterministic(tmp_path: Path) -> None:
    spec = syn.spec(tmp_path / "r.json")
    first, _ = eloc_cv.run_cv(syn.games(), spec=spec, git_head="test")
    second, _ = eloc_cv.run_cv(syn.games(), spec=spec, git_head="test")
    assert first == second


def test_elo_replay_in_the_harness_is_the_flagship_replay(tmp_path: Path) -> None:
    """The harness replays Elo with the spec's parameters, from the warm-up season."""
    spec = syn.spec(tmp_path / "r.json")
    games = syn.games().sort_values("tipoff_utc", kind="stable").reset_index(drop=True)
    expected = replay(prepare(games), spec.elo_params)
    np.testing.assert_array_equal(_diffs(syn.games(), spec), expected)


class _Stop(Exception):
    """Raised by the fake games loader: the command got past its guards."""


def _stop() -> None:
    raise _Stop


@pytest.fixture
def eloc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ElocCv:
    """A tmp report location, the live-parameter check passing and a games loader that stops."""
    monkeypatch.chdir(tmp_path)
    spec = syn.spec(tmp_path / "reports" / "eloc_cv.json")
    monkeypatch.setattr(backtest_mod, "ELOC_CV", spec)
    monkeypatch.setattr(backtest_mod, "_live_elo_params_match", lambda params=None: True)
    monkeypatch.setattr(backtest_mod, "_eloc_games", _stop)
    return spec


@pytest.mark.usefixtures("eloc")
@pytest.mark.parametrize(
    "args",
    [
        ["backtest", "--model", "eloc"],
        ["backtest", "--model", "eloc", "--cv", "--cv-check"],
        ["backtest", "--cv"],
        ["backtest", "--model", "eloc", "--competition", "gbl"],
        ["backtest", "--model", "eloc", "--competition", "gbl", "--cv"],
        ["backtest", "--model", "eloc", "--competition", "gbl", "--cv-check"],
    ],
)
def test_eloc_flags_refuse_bad_combinations(args: list[str]) -> None:
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 1
    assert not isinstance(result.exception, _Stop)


def test_cv_refuses_when_the_report_exists(eloc: ElocCv, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: True)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: True)
    eloc.report.parent.mkdir(parents=True)
    eloc.report.write_text("{}", encoding="utf-8")
    result = runner.invoke(cli.app, ["backtest", "--model", "eloc", "--cv"])
    assert result.exit_code == 1 and not isinstance(result.exception, _Stop)


@pytest.mark.usefixtures("eloc")
@pytest.mark.parametrize(("clean", "on_main"), [(False, True), (True, False)])
def test_cv_refuses_a_dirty_tree_or_a_head_off_main(
    monkeypatch: pytest.MonkeyPatch, clean: bool, on_main: bool
) -> None:
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: clean)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: on_main)
    result = runner.invoke(cli.app, ["backtest", "--model", "eloc", "--cv"])
    assert result.exit_code == 1 and not isinstance(result.exception, _Stop)


@pytest.mark.usefixtures("eloc")
def test_cv_passes_the_guards_on_a_clean_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: True)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: True)
    result = runner.invoke(cli.app, ["backtest", "--model", "eloc", "--cv"])
    assert isinstance(result.exception, _Stop)


@pytest.mark.usefixtures("eloc")
def test_cv_check_needs_no_clean_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest_mod, "is_clean_tree", lambda: False)
    monkeypatch.setattr(backtest_mod, "_on_origin_main", lambda: False)
    result = runner.invoke(cli.app, ["backtest", "--model", "eloc", "--cv-check"])
    assert isinstance(result.exception, _Stop)
