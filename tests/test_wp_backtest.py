"""WP backtest mechanics (docs/models/wp.md, sections 2, 3, 6) on synthetic games:
checkpoints, buckets, game weighting, the leakage rule, the paired bootstrap and the gate."""

import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.eval import wp_backtest as wb


def _events(rows: list[tuple[int, int, float, float, str, int]]) -> pd.DataFrame:
    """(period, ot, t, elapsed, ptype, m) rows as the builder produces them."""
    return pd.DataFrame(rows, columns=["period", "ot", "t", "elapsed", "ptype", "m"])


def test_checkpoints_show_the_last_play_at_or_before_each_time() -> None:
    ev = _events([(1, 0, 2300.0, 100.0, "2FGM", 2), (2, 0, 1500.0, 2000.0, "2FGM", -3)])
    ck = wb.checkpoint_states(ev).set_index("t")
    assert ck.loc[2340.0, "m"] == 0.0  # 60 s elapsed: nothing scored yet
    assert ck.loc[2280.0, "m"] == 2.0  # 120 s elapsed: the play at 100 s counts
    assert ck.loc[1920.0, "m"] == 2.0  # 480 s elapsed: the play at 2000 s is not yet in
    assert ck.loc[1860.0, "m"] == 2.0  # 540 s elapsed: still not in
    assert ck.loc[360.0, "m"] == -3.0  # 2040 s elapsed: the play at 2000 s is in
    assert ck.loc[0.0, "m"] == -3.0
    assert len(ck) == 40 and (ck["ot"] == 0).all()


def test_overtime_adds_six_checkpoints_per_period_on_the_overtime_clock() -> None:
    ev = _events(
        [
            (1, 0, 0.0, 2400.0, "EG", 0),
            (5, 1, 300.0, 2400.0, "2FGM", 1),
            (5, 1, 0.0, 2700.0, "2FGM", 4),
        ]
    )
    ck = wb.checkpoint_states(ev)
    ot = ck[ck["ot"] == 1]
    assert list(ot["t"]) == [300.0, 240.0, 180.0, 120.0, 60.0, 0.0]
    assert ot.set_index("t").loc[0.0, "m"] == 4.0


def test_leakage_rule_checkpoints_do_not_depend_on_later_plays() -> None:
    full = _events([(1, 0, 2300.0, 100.0, "2FGM", 2), (2, 0, 1000.0, 1400.0, "2FGM", 9)])
    cut = full.iloc[:1]
    a = wb.checkpoint_states(full)
    b = wb.checkpoint_states(cut)
    early = a["t"] >= 1400.0 - 1e-9  # checkpoints before the later play has elapsed
    aligned = b.set_index("t")["m"].reindex(a.loc[early, "t"]).to_numpy()
    assert np.allclose(a.loc[early, "m"].to_numpy(), aligned, equal_nan=True)


def test_buckets_follow_section_six_boundaries() -> None:
    ck = pd.DataFrame(
        {"t": [1860.0, 1800.0, 1200.0, 600.0, 120.0, 0.0, 300.0], "ot": [0, 0, 0, 0, 0, 0, 1]}
    )
    masks = wb.bucket_masks(ck)
    assert masks["Q1"].tolist() == [True, False, False, False, False, False, False]
    assert masks["Q2"].tolist() == [False, True, False, False, False, False, False]
    assert masks["Q3"].tolist() == [False, False, True, False, False, False, False]
    assert masks["Q4"].tolist() == [False, False, False, True, True, True, False]
    assert masks["last_2_min"].tolist() == [False, False, False, False, True, True, False]
    assert masks["OT"].tolist() == [False, False, False, False, False, False, True]


def test_calibration_weights_each_game_equally() -> None:
    # One long game predicted 0.2 (and lost) and one short game predicted 0.8 (and won).
    long_game = pd.DataFrame(
        {"gid": 0, "season": 2024, "phase": "RS", "t": 1500.0, "ot": 0, "y": 0, "p": 0.2},
        index=range(40),
    )
    short_game = pd.DataFrame(
        {"gid": 1, "season": 2024, "phase": "RS", "t": 1500.0, "ot": 0, "y": 1, "p": 0.8},
        index=range(1),
    )
    scored = pd.concat([long_game, short_game])
    q2 = wb.calibration(scored)["Q2"]
    assert q2["games"] == 2 and q2["checkpoints"] == 41
    assert abs(q2["mean_predicted"] - 0.5) < 1e-12
    assert abs(q2["observed_home_win"] - 0.5) < 1e-12
    assert abs(q2["gap"]) < 1e-12 and q2["within_tolerance"]


def test_a_clearly_better_model_passes_the_paired_gate() -> None:
    rng = np.random.default_rng(3)
    games = 300
    rows = []
    for gid in range(games):
        y = int(rng.uniform() < 0.5)
        for t in (2100.0, 1500.0, 900.0):
            rows.append(
                {
                    "gid": gid,
                    "season": 2024,
                    "phase": "RS",
                    "t": t,
                    "ot": 0,
                    "y": y,
                    "model_p": 0.9 if y else 0.1,
                    "base_p": 0.5,
                }
            )
    frame = pd.DataFrame(rows)
    model = wb._scored(frame, frame["model_p"].to_numpy(float))
    base = wb._scored(frame, frame["base_p"].to_numpy(float))
    result = wb.summarise(model, base, seed=20261018)
    assert result["delta_logloss"]["mean"] < 0
    assert result["delta_logloss"]["ci95"][1] < 0
    assert result["model"]["logloss"] < result["baseline"]["logloss"]


def test_bootstrap_is_seeded_and_resamples_whole_rows() -> None:
    mat = np.arange(20, dtype=float).reshape(10, 2)
    a = wb._bootstrap(mat, seed=7, resamples=50)
    b = wb._bootstrap(mat, seed=7, resamples=50)
    assert np.array_equal(a, b)
    assert a.shape == (50, 2)
    assert np.allclose(a[:, 1] - a[:, 0], 1.0)  # both columns resampled on the same games


def test_build_excludes_missing_files_and_score_mismatches(tmp_path: Path) -> None:
    def write(season: int, fnum: str, final: tuple[int, int]) -> None:
        names = ("FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter")
        obj: dict[str, Any] = {"CodeTeamA": "H", "CodeTeamB": "A", "ExtraTime": []}
        for name in names:
            obj[name] = []
        obj["ForthQuarter"] = [
            {
                "PLAYTYPE": "2FGM",
                "MARKERTIME": "00:00",
                "MINUTE": 31,
                "POINTS_A": str(final[0]),
                "POINTS_B": str(final[1]),
            }
        ]
        folder = tmp_path / "playbyplay" / f"E{season}"
        folder.mkdir(parents=True, exist_ok=True)
        with gzip.open(folder / f"{fnum}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(obj, fh)

    write(2010, "1", (80, 72))
    write(2010, "2", (60, 70))  # the mart says 80-72: a score mismatch
    games = pd.DataFrame(
        {
            "game_id": ["E2010_1", "E2010_2", "E2010_3"],
            "season": [2010, 2010, 2010],
            "phase": ["RS", "RS", "RS"],
            "tipoff_utc": pd.to_datetime(["2010-10-01", "2010-10-02", "2010-10-03"], utc=True),
            "home": ["H", "H", "H"],
            "away": ["A", "A", "A"],
            "home_score": [80, 80, 80],
            "away_score": [72, 72, 72],
            "played": [True, True, True],
            "forfeit": [False, False, False],
            "neutral": [False, False, False],
        }
    )
    g, training, states = wb.build(games, tmp_path)
    assert g["reason"].tolist() == [None, "score_mismatch", "no_file"]
    assert len(training) == 1 and training["m"].iloc[0] == 8.0 and training["y"].iloc[0] == 1
    assert set(states["gid"]) == {0}
    assert len(states) == 40
