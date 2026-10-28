"""In-game win probability (docs/models/wp.md, protocol v1): the closed-form baseline, the two
model families, the isotonic calibration and the tip-off chain start.

Everything here is a function of a state ``(m, t, ot, logit_pre, neutral)`` or of a fitted model.
Nothing reads files. The data build and the gate live in ``eurohoops.eval.wp_backtest``.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.special import ndtr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FloatArray = np.ndarray[Any, np.dtype[np.float64]]

GAME_SECONDS = 2400.0
FLOOR_SECONDS = 60.0  # t is floored at 60 s in every formula that divides by t
NOISE_CONSTANT = 11.0  # not tuned
PROB_CLIP = 1e-6  # log-loss clip
LINE_CLIP = (0.001, 0.999)  # displayed WP line clip (section 7)

# Section 5(b): the whole grid. Setting order is the tie-break order.
GBM_GRID: dict[str, tuple[int, int, float]] = {
    "G1": (200, 3, 0.05),
    "G2": (200, 4, 0.05),
    "G3": (400, 3, 0.05),
    "G4": (400, 4, 0.05),
}
LOGIT_C = 1.0
GBM_RANDOM_STATE = 20261018  # the only deviation from defaults: fixes the tree tie-breaking seed
GATE_SEED = 20261018
GATE_RESAMPLES = 10_000
CONTROL_THRESHOLD = 0.6
CRUNCH_SECONDS = 300.0

SPEC: dict[str, Any] = {
    "protocol": "docs/models/wp.md (protocol v1, approved 2026-10-18)",
    "question": "fitted in-game WP beats the closed-form baseline on the test seasons",
    "baseline": {"noise_constant": NOISE_CONSTANT, "floor_seconds": FLOOR_SECONDS},
    "features": ["m", "tf", "ot", "m_tf", "z", "logit_pre", "neutral"],
    "logit": {
        "inputs": "features + m*logit_pre*tf",
        "C": LOGIT_C,
        "penalty": "l2",
        "standardise": "training seasons",
    },
    "gbm": {
        "grid": {k: list(v) for k, v in GBM_GRID.items()},
        "subsample": 1.0,
        "inputs": "features (no interaction term)",
        "random_state": GBM_RANDOM_STATE,
    },
    "isotonic": {
        "fit_rows": "scoring-event rows of out-of-fold predictions, seasons 2010-2022",
        "expanding_window": True,
        "out_of_bounds": "clip",
    },
    "splits": {"train": [2007, 2022], "validation": [2023], "test": [2024, 2025]},
    "checkpoints": {"regulation_step_s": 60, "ot_step_s": 60, "ot_start_s": 300},
    "gate": {
        "resamples": GATE_RESAMPLES,
        "seed": GATE_SEED,
        "ci": 0.95,
        "passes_if": "CI entirely below zero and mean delta negative",
    },
    "tipoff_gap": {"form": "linear in tf", "clip": list(LINE_CLIP)},
    "control": {"threshold": CONTROL_THRESHOLD, "crunch_seconds": CRUNCH_SECONDS},
    "tolerance": 0.02,
}
SPEC_SHA256 = hashlib.sha256(
    json.dumps(SPEC, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
VERSION = f"0.2.0+wp.{SPEC_SHA256[:8]}"

FEATURES = tuple(SPEC["features"])


def time_fraction(t: FloatArray) -> FloatArray:
    return t / GAME_SECONDS


def baseline_mu(diff: FloatArray, scale: float | FloatArray) -> FloatArray:
    """Pre-game expected home margin: the Elo difference over the margin scale ``s``."""
    return diff / scale


def baseline_wp(m: FloatArray, t: FloatArray, mu_pre: FloatArray) -> FloatArray:
    """WP_base(t, m) = Phi((m + mu_pre * t/2400) / (11 * sqrt(max(t, 60) / 2400)))."""
    margin_adj = m + mu_pre * time_fraction(t)
    return ndtr(
        margin_adj / (NOISE_CONSTANT * np.sqrt(np.maximum(t, FLOOR_SECONDS) / GAME_SECONDS))
    )


def base_features(
    m: FloatArray, t: FloatArray, ot: FloatArray, logit_pre: FloatArray, neutral: FloatArray
) -> FloatArray:
    """The section 4 features in the order of ``FEATURES``."""
    tf = time_fraction(t)
    z = m / np.sqrt(np.maximum(t, FLOOR_SECONDS) / GAME_SECONDS)
    return np.column_stack([m, tf, ot, m * tf, z, logit_pre, neutral])


def logit_design(
    m: FloatArray, t: FloatArray, ot: FloatArray, logit_pre: FloatArray, neutral: FloatArray
) -> FloatArray:
    """Section 5(a): the base features plus the m * logit_pre * tf interaction."""
    base = base_features(m, t, ot, logit_pre, neutral)
    return np.column_stack([base, m * logit_pre * time_fraction(t)])


@dataclass(frozen=True)
class Family:
    """A fitted raw model: ``name`` is ``logit`` or ``gbm``; ``setting`` is a GBM grid key."""

    name: str
    setting: str | None
    estimator: Any

    def predict_raw(
        self,
        m: FloatArray,
        t: FloatArray,
        ot: FloatArray,
        logit_pre: FloatArray,
        neutral: FloatArray,
    ) -> FloatArray:
        if self.name == "logit":
            x = logit_design(m, t, ot, logit_pre, neutral)
        else:
            x = base_features(m, t, ot, logit_pre, neutral)
        return np.asarray(self.estimator.predict_proba(x)[:, 1], dtype=np.float64)


def fit_family(
    name: str, setting: str | None, state: tuple[FloatArray, ...], y: FloatArray
) -> Family:
    """Fit on scoring-event rows. ``state`` is (m, t, ot, logit_pre, neutral); ``setting`` picks
    the GBM grid row and is ignored for logit."""
    m, t, ot, logit_pre, neutral = state
    if name == "logit":
        model = make_pipeline(StandardScaler(), LogisticRegression(C=LOGIT_C, max_iter=5000))
        model.fit(logit_design(m, t, ot, logit_pre, neutral), y.astype(int))
        return Family("logit", None, model)
    if setting not in GBM_GRID:
        raise ValueError(f"unknown GBM setting {setting!r}")
    n_estimators, max_depth, learning_rate = GBM_GRID[setting]
    gbm = GradientBoostingClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=1.0,
        random_state=GBM_RANDOM_STATE,
    )
    gbm.fit(base_features(m, t, ot, logit_pre, neutral), y.astype(int))
    return Family("gbm", setting, gbm)


@dataclass(frozen=True)
class Calibrated:
    """A raw family with its isotonic map (section 5, calibration)."""

    family: Family
    isotonic: IsotonicRegression

    def predict(
        self,
        m: FloatArray,
        t: FloatArray,
        ot: FloatArray,
        logit_pre: FloatArray,
        neutral: FloatArray,
    ) -> FloatArray:
        raw = self.family.predict_raw(m, t, ot, logit_pre, neutral)
        return np.asarray(self.isotonic.predict(raw), dtype=np.float64)


def fit_isotonic(raw_oof: FloatArray, y: FloatArray) -> IsotonicRegression:
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(raw_oof, y)
    return iso


def tipoff_gap(p_pre: float, wp_model_tipoff: float) -> float:
    """g = P_pre - WP_model(t = 2400, m = 0) (section 7)."""
    return p_pre - wp_model_tipoff


def displayed_wp(wp_model: FloatArray, gap: float, t: FloatArray, ot: FloatArray) -> FloatArray:
    """WP(e) = clip(WP_model(e) + g * tf(e)); tf is 0 in overtime, so the gap is gone there."""
    tf = np.where(ot == 1, 0.0, time_fraction(t))
    return np.clip(wp_model + gap * tf, LINE_CLIP[0], LINE_CLIP[1])


def log_loss(y: FloatArray, p: FloatArray) -> FloatArray:
    clipped = np.clip(p, PROB_CLIP, 1.0 - PROB_CLIP)
    return -(y * np.log(clipped) + (1.0 - y) * np.log(1.0 - clipped))
