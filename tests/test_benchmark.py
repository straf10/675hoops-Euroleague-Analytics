import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from eurohoops.eval.benchmark import (
    benchmark,
    encompassing,
    lead_bucket,
    logit_fit,
    paired_gap_ci,
)
from eurohoops.eval.forecasts import build_forecasts
from eurohoops.predict import LOG_COLUMNS

LABELS = {"elo": "Elo", "mkt": "MKT"}
T1, T2, T3 = "2026-10-01T18:00:00Z", "2026-10-08T18:00:00Z", "2026-10-15T18:00:00Z"
# game, round, tip-off, home score, away score (G4 is still to play)
GAMES = [
    ("G1", 1, T1, 90, 80),  # home won
    ("G2", 2, T2, 70, 75),  # away won
    ("G3", 3, T3, 80, 70),  # home won; no odds at all
    ("G4", 4, "2026-10-22T18:00:00Z", None, None),
]


def games() -> pd.DataFrame:
    rows = [
        {
            "game_id": g,
            "season": 2026,
            "round": r,
            "phase": "RS",
            "tipoff_utc": pd.Timestamp(t),
            "home": f"H{g}",
            "away": f"A{g}",
            "home_score": hs,
            "away_score": a,
            "played": hs is not None,
            "forfeit": False,
            "neutral": False,
        }
        for g, r, t, hs, a in GAMES
    ]
    return pd.DataFrame(rows)


def elo_log(path: Path) -> Path:
    tips = {g: (r, t) for g, r, t, _, _ in GAMES}
    # (game, p_home, exp_margin): stamped the day before each tip-off
    calls = [("G1", 0.8, 5.0), ("G2", 0.6, 1.0), ("G3", 0.7, 3.0)]
    rows = []
    for g, p, m in calls:
        r, t = tips[g]
        stamp = (pd.Timestamp(t) - pd.Timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append([g, 2026, r, "RS", t, f"H{g}", f"A{g}", p, m, "elo", "v1", stamp])
    pd.DataFrame(rows, columns=list(LOG_COLUMNS)).to_csv(path, index=False)
    return path


def odds_csv(path: Path) -> Path:
    """Snapshots: G1 at 12:00 (6 h before tip-off) and 17:30 (0.5 h, the latest before tip-off);
    G2 at 12:00 on 07 Oct (30 h), then two snapshots at and after its tip-off (ignored); G3 has
    none; G4 is unplayed."""
    cols = ["game_id", "season", "round", "tipoff_utc", "fetched_at_utc", "p_home"]
    rows = [
        ["G1", 2026, 1, T1, "2026-10-01T12:00:00Z", 0.60],
        ["G1", 2026, 1, T1, "2026-10-01T17:30:00Z", 0.90],
        ["G2", 2026, 2, T2, "2026-10-07T12:00:00Z", 0.50],
        ["G2", 2026, 2, T2, "2026-10-08T18:00:00Z", 0.10],  # at tip-off: ignored
        ["G2", 2026, 2, T2, "2026-10-08T19:00:00Z", 0.10],  # after tip-off: ignored
        ["G4", 2026, 4, "2026-10-22T18:00:00Z", "2026-10-21T12:00:00Z", 0.40],
    ]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    return path


def ll(*probs: float) -> float:
    return -sum(math.log(p) for p in probs) / len(probs)


def test_lead_buckets_are_declared_and_half_open() -> None:
    assert lead_bucket(0.5) == "<3 h"
    assert lead_bucket(2.999) == "<3 h"
    assert lead_bucket(3.0) == "3-24 h"
    assert lead_bucket(23.9) == "3-24 h"
    assert lead_bucket(24.0) == ">=24 h"
    assert lead_bucket(172.0) == ">=24 h"
    with pytest.raises(ValueError):
        lead_bucket(-1.0)


def test_intercept_only_fit_is_the_logit_of_the_win_rate() -> None:
    y = np.array([1.0] * 7 + [0.0] * 3)
    beta, se = logit_fit(np.ones((10, 1)), y)
    assert beta[0] == pytest.approx(math.log(7 / 3), abs=1e-8)
    assert se[0] == pytest.approx(math.sqrt(1 / (10 * 0.7 * 0.3)), abs=1e-8)


def test_encompassing_recovers_the_informative_predictor() -> None:
    rng = np.random.default_rng(1)
    n = 3000
    p_mkt = rng.uniform(0.2, 0.8, n)
    p_model = rng.uniform(0.2, 0.8, n)
    home_won = (rng.uniform(size=n) < expit(np.log(p_mkt / (1 - p_mkt)))).astype(np.float64)
    out = encompassing(home_won, p_mkt, p_model)
    assert out["mkt"]["lo"] < 1.0 < out["mkt"]["hi"]
    assert out["model"]["lo"] < 0.0 < out["model"]["hi"]  # the model adds nothing
    assert out["model_adds_information"] is False


def test_encompassing_declares_information_when_the_model_carries_it() -> None:
    rng = np.random.default_rng(2)
    n = 3000
    p_mkt = rng.uniform(0.2, 0.8, n)
    p_model = rng.uniform(0.2, 0.8, n)
    home_won = (rng.uniform(size=n) < p_model).astype(np.float64)
    out = encompassing(home_won, p_mkt, p_model)
    assert out["model"]["lo"] > 0.0  # CI excludes 0
    assert out["model_adds_information"] is True
    assert out["n"] == n


def test_paired_gap_ci_is_zero_when_the_forecasts_are_identical() -> None:
    loss = np.array([0.2, 0.5, 0.9, 0.4])
    assert paired_gap_ci(loss, loss.copy()) == [0.0, 0.0]


def test_mkt_is_the_latest_pre_tip_snapshot_and_ignores_later_ones(tmp_path: Path) -> None:
    fc = build_forecasts(
        {"elo": elo_log(tmp_path / "elo.csv")},
        LABELS,
        games(),
        2026,
        odds_log=odds_csv(tmp_path / "odds.csv"),
    )
    mkt = next(m for m in fc["season"] if m["model"] == "mkt")
    # G1 (0.90, the 17:30 snapshot) and G2 (0.50, the 07 Oct snapshot); G3 has no odds, G4 is open.
    assert mkt["n"] == 2
    assert mkt["log_loss"] == pytest.approx(ll(0.9, 0.5), abs=1e-6)
    assert mkt["brier"] == pytest.approx((0.01 + 0.25) / 2, abs=1e-6)
    assert mkt["margin_mae"] is None and mkt["totals_mae"] is None  # no margin forecast
    assert {g["game_id"] for g in fc["games"] if "mkt" in g["models"]} == {"G1", "G2"}


def test_mkt_is_scored_on_the_shared_games(tmp_path: Path) -> None:
    fc = build_forecasts(
        {"elo": elo_log(tmp_path / "elo.csv")},
        LABELS,
        games(),
        2026,
        odds_log=odds_csv(tmp_path / "odds.csv"),
    )
    assert [(m["key"], m["first_round"]) for m in fc["models"]] == [("elo", 1), ("mkt", 1)]
    # Elo logged G1-G3; MKT has G1 and G2, so the shared games are G1 and G2.
    assert fc["shared"]["n"] == 2
    shared = {r["model"]: r for r in fc["shared"]["rows"]}
    assert shared["elo"]["log_loss"] == pytest.approx(ll(0.8, 0.4), abs=1e-6)
    assert shared["mkt"]["log_loss"] == pytest.approx(ll(0.9, 0.5), abs=1e-6)
    assert shared["elo"]["margin_mae"] == pytest.approx((5 + 6) / 2)  # |5 - 10|, |1 + 5|
    assert shared["mkt"]["margin_mae"] is None


def test_mkt_absent_without_odds_or_without_its_label(tmp_path: Path) -> None:
    log = elo_log(tmp_path / "elo.csv")
    no_odds = build_forecasts({"elo": log}, LABELS, games(), 2026)
    assert [m["key"] for m in no_odds["models"]] == ["elo"]
    missing = build_forecasts(
        {"elo": log}, LABELS, games(), 2026, odds_log=tmp_path / "missing.csv"
    )
    assert [m["key"] for m in missing["models"]] == ["elo"]
    # GBL has no odds log, so MKT never appears in its record.
    gbl = build_forecasts({"elo": log}, LABELS, games(), 2026, odds_log=None)
    assert all(m["model"] != "mkt" for m in gbl["season"])


def test_mkt_does_not_lead_the_page_by_default(tmp_path: Path) -> None:
    # MKT is listed last, so the page's default lead falls to the first model, not the benchmark.
    fc = build_forecasts(
        {"elo": elo_log(tmp_path / "elo.csv")},
        LABELS,
        games(),
        2026,
        odds_log=odds_csv(tmp_path / "odds.csv"),
    )
    assert fc["published"] == "elo"
    assert {s["model"] for s in fc["season"]} == {"elo", "mkt"}


def test_benchmark_by_lead_time_and_pairing(tmp_path: Path) -> None:
    report = benchmark(
        {"elo": elo_log(tmp_path / "elo.csv"), "m1": None},
        games(),
        odds_csv(tmp_path / "odds.csv"),
        2026,
    )
    assert report["market_games"] == 2
    assert [b["label"] for b in report["buckets"]] == ["<3 h", "3-24 h", ">=24 h"]
    assert list(report["models"]) == ["elo"]  # m1 has no log
    elo = report["models"]["elo"]
    # Paired on G1 and G2 only (G3 has no MKT row).
    assert elo["n"] == 2
    assert "encompassing" not in elo  # two games are too few for three coefficients
    assert elo["log_loss"]["model"] == pytest.approx(ll(0.8, 0.4), abs=1e-6)
    assert elo["log_loss"]["mkt"] == pytest.approx(ll(0.9, 0.5), abs=1e-6)
    assert elo["log_loss"]["model"] - elo["log_loss"]["mkt"] == pytest.approx(
        ll(0.8, 0.4) - ll(0.9, 0.5), abs=1e-6
    )
    lo, hi = elo["gap_ci95"]["log_loss"]
    assert lo <= elo["log_loss"]["model"] - elo["log_loss"]["mkt"] <= hi
    # G1 snapshot 0.5 h before tip-off; G2 snapshot 30 h before.
    by_lead = {b["bucket"]: b for b in elo["by_lead"]}
    assert by_lead["<3 h"]["n"] == 1
    assert by_lead["<3 h"]["log_loss"]["mkt"] == pytest.approx(-math.log(0.9), abs=1e-6)
    assert by_lead["3-24 h"]["n"] == 0 and by_lead["3-24 h"]["log_loss"] is None
    assert by_lead[">=24 h"]["n"] == 1
    assert by_lead[">=24 h"]["brier"]["mkt"] == pytest.approx(0.25, abs=1e-6)


def test_benchmark_without_odds_is_empty(tmp_path: Path) -> None:
    report = benchmark({"elo": elo_log(tmp_path / "elo.csv")}, games(), tmp_path / "none.csv", 2026)
    assert report["market_games"] == 0
    assert report["models"]["elo"]["n"] == 0
    assert "encompassing" not in report["models"]["elo"]


def test_no_model_imports_the_benchmark_or_the_odds_recorder() -> None:
    src = Path(__file__).resolve().parents[1] / "src" / "eurohoops"
    files = [*(src / "models").rglob("*.py"), src / "predict.py", src / "live_m1.py"]
    banned = ("eurohoops.odds", "eurohoops.eval.benchmark", "eurohoops.eval.forecasts")
    offenders = [p.name for p in files if any(b in p.read_text(encoding="utf-8") for b in banned)]
    assert offenders == []
