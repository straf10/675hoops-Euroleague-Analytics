"""Shadow promotion test (rule 4): the statistic, the pairing, the guard and the per-shadow look.

Synthetic data only. Never run the command on the real logs before a look is due.
"""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eurohoops.config import EUROLEAGUE
from eurohoops.eval import promotion
from eurohoops.eval.promotion import (
    LookNotDueError,
    NotTestableError,
    bootstrap_ci,
    checkpoint_status,
    latest_version_rows,
    pair_logs,
    promotion_verdict,
    run_look,
)
from eurohoops.live_m1 import M1_LOG_COLUMNS
from eurohoops.model_catalog import LiveModel, active_shadows
from eurohoops.predict import LOG_COLUMNS

SEASON = 2026
ELO_LOSS = 0.65


def verdict_for(gap: float, spread: float, n: int = 100) -> promotion.Verdict:
    """A verdict on games whose gap (shadow - Elo) is ``gap`` +/- ``spread`` alternately."""
    sign = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    elo = np.full(n, ELO_LOSS)
    return promotion_verdict(
        elo + gap + spread * sign,
        elo,
        competition="euroleague",
        season=SEASON,
        look=1,
        checkpoint="test",
        shadow="m5",
        shadow_version="v1",
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
        "competition": "euroleague",
        "season": SEASON,
        "look": 1,
        "checkpoint": "t",
        "shadow": "m5",
        "shadow_version": "v",
        "elo_versions": ["e"],
        "first_round": 1,
    }
    with pytest.raises(ValueError, match="same games"):
        promotion_verdict(np.zeros(3), np.zeros(4), **kwargs)  # type: ignore[arg-type]
    with pytest.raises(NotTestableError, match="at least 2"):
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


def log_rows(
    columns: tuple[str, ...], name: str, p: float, first: int, new_version_from: int | None = None
) -> pd.DataFrame:
    """One row per round from ``first`` to 22, stamped 10 h before tip-off; version ``v2`` from
    round ``new_version_from``."""
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


def write_logs(
    tmp_path: Path, shadow_from: int = 4, new_version_from: int | None = None, p: float = 0.8
) -> tuple[Path, Path]:
    """Elo logs rounds 1-22 (home wins always, p=0.6); the shadow ``p`` from ``shadow_from``."""
    elo, shadow = tmp_path / "elo.csv", tmp_path / "m5.csv"
    log_rows(LOG_COLUMNS, "elo", 0.6, 1).to_csv(elo, index=False)
    log_rows(M1_LOG_COLUMNS, "m5", p, shadow_from, new_version_from).to_csv(shadow, index=False)
    return shadow, elo


def test_pairing_starts_at_the_shadows_first_round(tmp_path: Path) -> None:
    shadow, elo = write_logs(tmp_path)
    pairing = pair_logs(shadow, elo, games(19), SEASON, (), last_round=19)
    assert len(pairing.shadow_loss) == len(pairing.elo_loss) == 16  # rounds 4-19
    assert (pairing.first_round, pairing.version, pairing.elo_versions) == (4, "v1", ["v1"])
    assert pairing.shadow_loss[0] == pytest.approx(-np.log(0.8))
    assert pairing.elo_loss[0] == pytest.approx(-np.log(0.6))
    assert list(pairing.games["round"]) == list(range(4, 20))


def test_look_one_ignores_games_after_the_checkpoint_round(tmp_path: Path) -> None:
    shadow, elo = write_logs(tmp_path)
    capped = pair_logs(shadow, elo, games(21), SEASON, (), last_round=19)
    assert len(capped.shadow_loss) == 16  # rounds 20-21 are played but not part of look 1
    whole = pair_logs(shadow, elo, games(21), SEASON, (), last_round=None)
    assert len(whole.shadow_loss) == 18


def test_new_shadow_version_restarts_the_count(tmp_path: Path) -> None:
    shadow, elo = write_logs(tmp_path, new_version_from=11)
    pairing = pair_logs(shadow, elo, games(19), SEASON, (), last_round=19)
    assert (len(pairing.shadow_loss), pairing.first_round, pairing.version) == (9, 11, "v2")


def test_latest_version_is_read_from_utc_times_not_text() -> None:
    # As text "2026-10-05T09:00:00+00:00" sorts after "2026-10-05T10:00:00Z"; as times it is
    # earlier, so v2 (stamped 10:00 UTC) is the latest version.
    log = pd.DataFrame(
        {
            "model_version": ["v1", "v2", "v1"],
            "predicted_at_utc": [
                "2026-10-04T12:00:00Z",
                "2026-10-05T10:00:00Z",
                "2026-10-05T09:00:00+00:00",
            ],
        }
    )
    rows, version = latest_version_rows(log)
    assert version == "v2"
    assert list(rows.index) == [1]
    # an offset stamp is converted to UTC: 12:30+02:00 is 10:30 UTC, after v2's 10:00
    v3 = pd.DataFrame({"model_version": ["v3"], "predicted_at_utc": ["2026-10-05T12:30:00+02:00"]})
    assert latest_version_rows(pd.concat([log, v3], ignore_index=True))[1] == "v3"


def test_late_shadow_rows_do_not_count(tmp_path: Path) -> None:
    shadow, elo = write_logs(tmp_path)
    frame = pd.read_csv(shadow)
    frame.loc[frame["round"] == 10, "predicted_at_utc"] = tip(10).strftime("%Y-%m-%dT%H:%M:%SZ")
    frame.to_csv(shadow, index=False)
    pairing = pair_logs(shadow, elo, games(19), SEASON, (), last_round=19)
    assert len(pairing.shadow_loss) == 15  # round 10 was stamped at tip-off


def test_a_shadow_without_paired_games_is_not_testable(tmp_path: Path) -> None:
    shadow, elo = write_logs(tmp_path, shadow_from=20)
    with pytest.raises(NotTestableError, match="no game"):
        pair_logs(shadow, elo, games(19), SEASON, (), last_round=19)
    with pytest.raises(NotTestableError, match="no logged games"):
        pair_logs(tmp_path / "missing.csv", elo, games(19), SEASON, (), last_round=19)


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
    shadow, elo = write_logs(tmp_path)

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("the statistic was computed before the checkpoint")

    monkeypatch.setattr(promotion, "pair_logs", boom)
    monkeypatch.setattr(promotion, "promotion_verdict", boom)
    for look, g in ((1, games(18)), (2, games(21))):
        with pytest.raises(LookNotDueError, match="not due"):
            run_look("euroleague", look, g, SEASON, {"m5": shadow}, elo, (), tmp_path)
    assert not list(tmp_path.glob("promotion_*.json"))


def test_run_writes_the_verdict_once(tmp_path: Path) -> None:
    shadow, elo = write_logs(tmp_path)
    result = run_look("euroleague", 1, games(19), SEASON, {"m5": shadow}, elo, (), tmp_path)
    verdict, out = result.verdicts["m5"]
    assert out.name == "promotion_euroleague_2026_m5_look1.json"
    payload = json.loads(out.read_text())
    assert {k: payload[k] for k in verdict.as_dict()} == verdict.as_dict()
    assert set(payload) - set(verdict.as_dict()) == {"sensitivity_round_clustered"}
    assert verdict.n_games == 16
    assert verdict.promote  # p=0.8 vs 0.6 on home wins: -0.288 every game
    assert verdict.shadow == "m5"
    with pytest.raises(LookNotDueError, match="exists"):
        run_look("euroleague", 1, games(19), SEASON, {"m5": shadow}, elo, (), tmp_path)
    # look 2 is a look of its own
    look2 = run_look("euroleague", 2, games(22), SEASON, {"m5": shadow}, elo, (), tmp_path)
    assert look2.verdicts["m5"][0].n_games == 19


def test_round_clustered_sensitivity_is_reported_with_r1_settings(tmp_path: Path) -> None:
    shadow, elo = write_logs(tmp_path)
    result = run_look("euroleague", 1, games(19), SEASON, {"m5": shadow}, elo, (), tmp_path)
    verdict, out = result.verdicts["m5"]
    sens = json.loads(out.read_text())["sensitivity_round_clustered"]
    assert (sens["n_games"], sens["n_clusters"]) == (16, 16)  # one game per round
    assert sens["mean_diff"] == pytest.approx(verdict.mean_diff)
    assert (sens["resamples"], sens["seed"], sens["ci_level"]) == (10_000, promotion.SEED, 0.975)
    # the gap is the same in every game, so both intervals collapse to the mean
    assert sens["ci_lo"] == pytest.approx(verdict.mean_diff, abs=1e-9)
    assert sens["ci_hi"] == pytest.approx(verdict.mean_diff, abs=1e-9)


# ---- every active shadow of a catalog gets its own verdict


def test_every_active_shadow_gets_its_own_verdict(tmp_path: Path) -> None:
    comp = replace(EUROLEAGUE, log_dir=tmp_path / "logs")
    comp.log_dir.mkdir()
    log_rows(LOG_COLUMNS, "elo", 0.6, 1).to_csv(comp.prediction_log, index=False)
    catalog = (
        LiveModel("good", "GOOD", None, "trial"),  # p=0.8 on home wins: passes
        LiveModel("bad", "BAD", None, "trial"),  # p=0.5: worse than Elo, fails
        LiveModel("off", "OFF", None, "trial", lambda: False),  # inactive: skipped
        LiveModel("new", "NEW", None, "trial"),  # logs from round 20: nothing to test at look 1
    )
    for tag, p, first in (("good", 0.8, 4), ("bad", 0.5, 2), ("off", 0.9, 1), ("new", 0.8, 20)):
        log_rows(M1_LOG_COLUMNS, tag, p, first).to_csv(comp.log_path(tag), index=False)
    shadows = active_shadows(comp, catalog)
    assert list(shadows) == ["good", "bad", "new"]
    out_dir = tmp_path / "reports"
    result = run_look("euroleague", 1, games(19), SEASON, shadows, comp.prediction_log, (), out_dir)
    assert set(result.verdicts) == {"good", "bad"}
    good, good_out = result.verdicts["good"]
    bad, bad_out = result.verdicts["bad"]
    assert (good.shadow, good.n_games, good.first_round, good.promote) == ("good", 16, 4, True)
    assert (bad.shadow, bad.n_games, bad.first_round, bad.promote) == ("bad", 18, 2, False)
    assert bad.mean_diff > 0
    assert "no game" in result.not_tested["new"]
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "promotion_euroleague_2026_bad_look1.json",
        "promotion_euroleague_2026_good_look1.json",
    ]
    assert json.loads(good_out.read_text())["shadow"] == "good"
    assert json.loads(bad_out.read_text())["promote"] is False
    # each verdict is the one a look of that shadow alone gives
    alone = {"good": shadows["good"]}
    solo = run_look(
        "euroleague", 1, games(19), SEASON, alone, comp.prediction_log, (), tmp_path / "solo"
    )
    assert solo.verdicts["good"][0] == good
