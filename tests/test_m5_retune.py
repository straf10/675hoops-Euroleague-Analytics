from eurohoops.config import M5_RETUNE
from eurohoops.eval.m5_retune import (
    RetuneSetting,
    _select_setting,
    grid_settings,
    retune_backtest_spec,
)


def test_retune_grid_has_twelve_settings() -> None:
    assert len(grid_settings(M5_RETUNE)) == 12


def test_retune_spec_frame_spans_warmup_to_last_fold() -> None:
    spec = retune_backtest_spec(M5_RETUNE)
    assert spec.warmup[0] == M5_RETUNE.warmup[0]
    assert spec.test[-1] == M5_RETUNE.folds[-1]


def test_one_se_rule_prefers_simpler_setting() -> None:
    baseline = RetuneSetting("proj_hc", None, False, 180.0)
    complex_ = RetuneSetting("proj_avail", 1.0, True, 120.0)
    table = [(baseline, 0.60), (complex_, 0.599)]
    se = {baseline.key(): 0.01, complex_.key(): 0.01}
    assert _select_setting(table, se).key() == baseline.key()
