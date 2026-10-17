"""Flagship promotion test (PLAN R1): the statistic, the pairing and the checkpoint guard.

Synthetic data only. Never run the command on the real logs before a look is due.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.eval import promotion
from eurohoops.eval.promotion import (
    LookNotDueError,
    bootstrap_ci,
    checkpoint_status,
    paired_log_losses,
    promotion_verdict,
    run_look,
)
from eurohoops.live_m1 import M1_LOG_COLUMNS
from eurohoops.predict import LOG_COLUMNS

SEASON = 2026
ELO_LOSS = 0.65


def verdict_for(gap: float, spread: float, n: int = 100) -> promotion.Verdict:
    """A verdict on games whose gap (flagship - Elo) is ``gap`` +/- ``spread`` alternately."""
    sign = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    elo = np.full(n, ELO_LOSS)
    return promotion_verdict(
        elo + gap + spread * sign,
        elo,
        competition="euroleague",
        season=SEASON,
        look=1,
        checkpoint="test",
        flagship_version="v1",
        elo_versions=["e1"],
        first_round=4,
    )


def test_clear_pass() -> None:
    v = verdict_for(-0.05, 0.02)
    assert v.promote
    assert v.ci_hi < 0
    assert v.mean_diff == pytest.approx(-0.05)
    assert v.n_games == 100
    assert (v.resamples, v.seed, v.ci_level) == (10_000, promotion.SEED, 0.975)


def test_clear_fail() -> None:
    v = verdict_for(0.03, 0.02)
    assert not v.promote
    assert not v.ci_upper_below_zero
    assert not v.mean_at_most_min_gap


def test_deep_mean_but_ci_crosses_zero() -> None:
    v = verdict_for(-0.02, 0.3)
    assert v.mean_at_most_min_gap
    assert v.ci_hi > 0
    assert not v.promote


def test_ci_below_zero_but_mean_too_small() -> None:
    v = verdict_for(-0.005, 0.002, n=400)
    assert v.ci_upper_below_zero
    assert not v.mean_at_most_min_gap
    assert not v.promote


def test_mean_exactly_at_threshold_counts() -> None:
    v = verdict_for(-0.01, 0.0)
    assert v.mean_at_most_min_gap
    assert v.promote


def test_deterministic_with_fixed_seed() -> None:
    diff = np.linspace(-0.2, 0.1, 57)
    assert bootstrap_ci(diff) == bootstrap_ci(diff)
    assert bootstrap_ci(diff) != bootstrap_ci(diff, seed=1)
    assert verdict_for(-0.03, 0.1) == verdict_for(-0.03, 0.1)


def test_needs_paired_games() -> None:
    kwargs = {
        "competition": "gbl",
        "season": SEASON,
        "look": 1,
        "checkpoint": "t",
        "flagship_version": "v",
        "elo_versions": ["e"],
        "first_round": 1,
    }
    with pytest.raises(ValueError, match="same games"):
        promotion_verdict(np.zeros(3), np.zeros(4), **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at least 2"):
        promotion_verdict(np.zeros(1), np.zeros(1), **kwargs)  # type: ignore[arg-type]


# ---- pairing and the guard: round r has one game, tipping off on day r of October 2026


def tip(rnd: int) -> pd.Timestamp:
    return pd.Timestamp("2026-10-01T18:00:00Z") + pd.Timedelta(days=rnd)


def games(played_through: int, rounds: int = 22, playoffs: int = 0) -> pd.DataFrame:
    rows = []
    for r in range(1, rounds + playoffs + 1):
        done = r <= played_through
        rows.append(
            {
                "game_id": f"G{r}",
                "season": SEASON,
                "round": r if r <= rounds else r - rounds,
                "phase": "RS" if r <= rounds else "PO",
                "tipoff_utc": tip(r),
                "home": "H",
                "away": "A",
                "home_score": 90 if done else None,
                "away_score": 80 if done else None,
                "played": done,
                "forfeit": False,
                "neutral": False,
            }
        )
    return pd.DataFrame(rows)


def write_logs(
    tmp_path: Path, flagship_from: int = 4, new_version_from: int | None = None
) -> tuple[Path, Path]:
    """Elo logs rounds 1-22 (home wins always, p=0.6); the flagship p=0.8 from ``flagship_from``."""

    def rows(columns: tuple[str, ...], name: str, p: float, first: int) -> pd.DataFrame:
        out = []
        for r in range(first, 23):
            version = "v2" if new_version_from and r >= new_version_from else "v1"
            out.append(
                {
                    "game_id": f"G{r}",
                    "season": SEASON,
                    "round": r,
                    "phase": "RS",
                    "tipoff_utc": tip(r).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "home": "H",
                    "away": "A",
                    "p_home": p,
                    "exp_margin": 5.0,
                    "model": name,
                    "model_version": version,
                    "predicted_at_utc": (tip(r) - pd.Timedelta(hours=10)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                }
            )
        return pd.DataFrame(out).reindex(columns=list(columns))

    elo, flagship = tmp_path / "elo.csv", tmp_path / "m5.csv"
    rows(LOG_COLUMNS, "elo", 0.6, 1).to_csv(elo, index=False)
    rows(M1_LOG_COLUMNS, "m5", 0.8, flagship_from).to_csv(flagship, index=False)
    return flagship, elo


def test_pairing_starts_at_the_flagships_first_round(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path)
    f, e, first, version, elo_versions = paired_log_losses(
        flagship, elo, games(19), SEASON, (), last_round=19
    )
    assert len(f) == len(e) == 16  # rounds 4-19
    assert (first, version, elo_versions) == (4, "v1", ["v1"])
    assert f[0] == pytest.approx(-np.log(0.8))
    assert e[0] == pytest.approx(-np.log(0.6))


def test_look_one_ignores_games_after_the_checkpoint_round(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path)
    f, _, _, _, _ = paired_log_losses(flagship, elo, games(21), SEASON, (), last_round=19)
    assert len(f) == 16  # rounds 20-21 are played but not part of look 1
    f2, _, _, _, _ = paired_log_losses(flagship, elo, games(21), SEASON, (), last_round=None)
    assert len(f2) == 18


def test_new_flagship_version_restarts_the_count(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path, new_version_from=11)
    f, _, first, version, _ = paired_log_losses(flagship, elo, games(19), SEASON, (), last_round=19)
    assert (len(f), first, version) == (9, 11, "v2")  # rounds 11-19 only


def test_late_flagship_rows_do_not_count(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path)
    frame = pd.read_csv(flagship)
    frame.loc[frame["round"] == 10, "predicted_at_utc"] = tip(10).strftime("%Y-%m-%dT%H:%M:%SZ")
    frame.to_csv(flagship, index=False)
    f, _, _, _, _ = paired_log_losses(flagship, elo, games(19), SEASON, (), last_round=19)
    assert len(f) == 15  # round 10 was stamped at tip-off


def test_checkpoint_guard() -> None:
    assert checkpoint_status(games(19), SEASON, 1, 19) == (True, "regular-season round 19 complete")
    done, why = checkpoint_status(games(18), SEASON, 1, 19)
    assert not done
    assert "not played" in why
    assert not checkpoint_status(games(19, rounds=18), SEASON, 1, 19)[0]  # round 19 unscheduled
    postponed = games(19)
    postponed.loc[postponed["round"] == 7, ["played"]] = False  # a postponed earlier game
    assert not checkpoint_status(postponed, SEASON, 1, 19)[0]
    assert checkpoint_status(games(22), SEASON, 2, 19)[0]
    assert not checkpoint_status(games(22, playoffs=3), SEASON, 2, 19)[0]  # playoffs still open
    assert not checkpoint_status(games(19), SEASON, 2, 19)[0]


def test_run_refuses_before_the_checkpoint_and_reads_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flagship, elo = write_logs(tmp_path)

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("the statistic was computed before the checkpoint")

    monkeypatch.setattr(promotion, "paired_log_losses", boom)
    monkeypatch.setattr(promotion, "promotion_verdict", boom)
    for look, g in ((1, games(18)), (2, games(21))):
        with pytest.raises(LookNotDueError, match="not due"):
            run_look("euroleague", look, g, SEASON, flagship, elo, (), tmp_path)
    assert not list(tmp_path.glob("promotion_*.json"))


def test_run_writes_the_verdict_once(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path)
    verdict, out = run_look("euroleague", 1, games(19), SEASON, flagship, elo, (), tmp_path)
    assert out.name == "promotion_euroleague_2026_look1.json"
    payload = json.loads(out.read_text())
    assert {k: payload[k] for k in verdict.as_dict()} == verdict.as_dict()
    assert set(payload) - set(verdict.as_dict()) == {"sensitivity_round_clustered"}
    assert verdict.n_games == 16
    assert verdict.promote  # p=0.8 vs 0.6 on home wins: -0.288 every game
    assert verdict.flagship == "M5"
    with pytest.raises(LookNotDueError, match="exists"):
        run_look("euroleague", 1, games(19), SEASON, flagship, elo, (), tmp_path)


def test_gbl_uses_round_13(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path, flagship_from=1)
    with pytest.raises(LookNotDueError):
        run_look("gbl", 1, games(12), SEASON, flagship, elo, (), tmp_path)
    verdict, _ = run_look("gbl", 1, games(13), SEASON, flagship, elo, (), tmp_path)
    assert (verdict.n_games, verdict.flagship, verdict.first_round) == (13, "M1", 1)


def write_elor(tmp_path: Path, p: float = 0.7) -> Path:
    """ELOR's shadow log: every round 1-22, home wins always, stamped 10 h before tip-off."""
    rows = []
    for r in range(1, 23):
        rows.append(
            {
                "game_id": f"G{r}",
                "season": SEASON,
                "round": r,
                "phase": "RS",
                "tipoff_utc": tip(r).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "home": "H",
                "away": "A",
                "p_home": p,
                "exp_margin": 5.0,
                "model": "elor",
                "model_version": "0.2.0+elor.test",
                "predicted_at_utc": (tip(r) - pd.Timedelta(hours=10)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            }
        )
    path = tmp_path / "elor.csv"
    pd.DataFrame(rows).reindex(columns=list(LOG_COLUMNS)).to_csv(path, index=False)
    return path


def test_reported_blocks_do_not_change_the_decision(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path)
    elor = write_elor(tmp_path)
    plain_dir, full_dir = tmp_path / "plain", tmp_path / "full"
    plain, plain_out = run_look("euroleague", 1, games(19), SEASON, flagship, elo, (), plain_dir)
    full, full_out = run_look(
        "euroleague", 1, games(19), SEASON, flagship, elo, (), full_dir, elor_log=elor
    )
    assert full.as_dict() == plain.as_dict()
    assert full.promote is plain.promote is True
    with_blocks = json.loads(full_out.read_text())
    without = json.loads(plain_out.read_text())
    assert "reported_only" not in without
    for key in plain.as_dict():
        assert with_blocks[key] == without[key]
    assert with_blocks["promote"] is True


def test_reported_blocks_hold_their_games_and_gaps(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path)  # M5 (0.8) from round 4; Elo (0.6) from round 1
    elor = write_elor(tmp_path)  # ELOR (0.7) from round 1, capped at round 19 for look 1
    verdict, out = run_look(
        "euroleague", 1, games(19), SEASON, flagship, elo, (), tmp_path, elor_log=elor
    )
    payload = json.loads(out.read_text())
    blocks = payload["reported_only"]
    # ELOR vs Elo: rounds 1-19 are logged by both; ELOR vs M5: rounds 4-19 (M5's first round).
    assert blocks["elor_vs_elo"]["n"] == 19
    assert blocks["elor_vs_elo"]["mean_diff"] == pytest.approx(
        -np.log(0.7) - (-np.log(0.6)), abs=1e-6
    )
    assert blocks["elor_vs_elo"]["elor_log_loss"] == pytest.approx(-np.log(0.7), abs=1e-6)
    assert blocks["elor_vs_elo"]["elo_log_loss"] == pytest.approx(-np.log(0.6), abs=1e-6)
    assert blocks["elor_vs_flagship"]["n"] == 16
    assert blocks["elor_vs_flagship"]["mean_diff"] == pytest.approx(
        -np.log(0.7) - (-np.log(0.8)), abs=1e-6
    )
    assert blocks["elor_vs_flagship"]["m5_log_loss"] == pytest.approx(-np.log(0.8), abs=1e-6)
    assert blocks["elor_vs_flagship"]["ci_level"] == 0.975
    assert blocks["elor_vs_flagship"]["resamples"] == promotion.RESAMPLES
    assert blocks["elor_vs_flagship"]["seed"] == promotion.SEED
    # R1's own numbers stay the same: M5 vs Elo on rounds 4-19.
    assert verdict.n_games == 16


def test_round_clustered_sensitivity_is_reported_with_r1_settings(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path)
    verdict, out = run_look("euroleague", 1, games(19), SEASON, flagship, elo, (), tmp_path)
    sens = json.loads(out.read_text())["sensitivity_round_clustered"]
    assert (sens["n_games"], sens["n_clusters"]) == (16, 16)  # one game per round
    assert sens["mean_diff"] == pytest.approx(verdict.mean_diff)
    assert (sens["resamples"], sens["seed"], sens["ci_level"]) == (10_000, promotion.SEED, 0.975)
    # the gap is the same in every game, so both intervals collapse to the mean
    assert sens["ci_lo"] == pytest.approx(verdict.mean_diff, abs=1e-9)
    assert sens["ci_hi"] == pytest.approx(verdict.mean_diff, abs=1e-9)


def test_gbl_look_has_no_elor_blocks(tmp_path: Path) -> None:
    flagship, elo = write_logs(tmp_path, flagship_from=1)
    elor = write_elor(tmp_path)
    _, out = run_look("gbl", 1, games(13), SEASON, flagship, elo, (), tmp_path, elor_log=elor)
    assert "reported_only" not in json.loads(out.read_text())
