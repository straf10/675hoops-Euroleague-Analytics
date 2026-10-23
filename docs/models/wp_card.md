# In-game win probability (WP) model card

Status: published (the game WP line uses this model, not the baseline). Player WPA is not computed or published.

## What it is
Version `0.2.0+wp.9702906e`, spec `docs/models/wp.md`. Built from the cached EuroLeague play-by-play for seasons 2007–2025. The 2026 partial season is not used.

- The chosen model is a logistic regression with time interactions (spec section 5a), calibrated by an isotonic map fitted on out-of-fold predictions of 2010–2022.
- It predicts the home team's win probability at any game state: score margin, time left, overtime, the pre-game Elo probability and the neutral-site flag.
- The baseline is the closed-form formula with the Elo margin scale.
- The tip-off line starts at the published pre-game probability (spec section 7).
- The model is never a pre-game forecaster. It writes nothing to `predictions/`. The fitted object lives in memory only, and `models/` is not written.

**Implementation notes**
1. The isotonic map is fitted on the out-of-fold scoring-event rows of 2010–2022. Each season is predicted by a model fitted on earlier seasons only.
2. The comparison is between the calibrated state probability and the closed-form baseline, both without the tip-off gap. The displayed line adds the gap.
3. The baseline's Elo margin scale for each evaluation season is fitted on the included games of earlier seasons only.
4. Gradient boosting uses the section 4 features without the margin-logit-time interaction and without `t` (for trees, `t` is a monotone copy of `tf`). `random_state` is 20261018. Settings G1 to G4 are chosen on validation raw log loss.
5. Calibration buckets use game weighting. Q1 is `t` above 1800; Q2 is 1200 to 1800; Q3 is 600 to 1200; Q4 is 0 to 600, with the boundary value in the later bucket. The last 2 minutes are `t` 0 to 120, inside Q4. Overtime is every overtime checkpoint.
6. The game-control formulas (spec section 8), written for the winner, are applied to each team's own WP. They are in `eurohoops.models.wp_control` and are not built into a page yet.
7. The regulation checkpoint at `t = 0` and the first overtime checkpoint at `t = 300` are the same game moment. Both are kept.
8. The backtest command refuses to run when `reports/backtest_wp.json` exists.
9. Assists and box data are not read. Under the 100/0 convention they change no WP value.
10. scikit-learn is a direct dependency, with a mypy override because it ships no stubs.

## Results
Every value below is read from `reports/backtest_wp.json`. Log loss and Brier are checkpoint-averaged within each game, then averaged over games. Intervals are 95% paired bootstrap intervals over whole games (10,000 resamples, seed 20261018).

### Counts and exclusions

| Quantity | Value | Source |
|---|---|---|
| Mart games 2007-2025 | 5122 | `backtest_wp.json:counts/mart_games_2007_2025` |
| Included games | 4861 | `backtest_wp.json:counts/included_games` |
| Excluded games | 261 | `backtest_wp.json:counts/excluded_games` |
| Excluded: not played | 82 | `backtest_wp.json:counts/exclusion_reasons/not_played` |
| Excluded: code mismatch | 1 | `backtest_wp.json:counts/exclusion_reasons/code_mismatch` |
| Excluded: bad clock (ND or sentinel) | 178 | `backtest_wp.json:counts/exclusion_reasons/bad_clock` |
| Excluded: no file | 0 | `backtest_wp.json:counts/exclusion_reasons/no_file` |
| Excluded: score mismatch | 0 | `backtest_wp.json:counts/exclusion_reasons/score_mismatch` |
| Training games (2007-2022) | 3803 | `backtest_wp.json:counts/train_games` |
| Validation games (2023) | 328 | `backtest_wp.json:counts/validation_games` |
| Test games (2024-2025) | 730 | `backtest_wp.json:counts/test_games` |
| Scoring-event training rows | 317665 | `backtest_wp.json:train_rows/scoring_rows` |

Not played: 82 (54 in 2019, 28 in 2021). Code mismatch: 1 (2018, `E2018_21`). The excluded bad-clock games are 157 in 2016, 16 in 2017–2022 and 5 in 2023–2025. A blank clock on a play event that is not a marker is also excluded under the same rule; none were found.

### Families and the validation choice (2023)

| Quantity | Value | Source |
|---|---|---|
| GBM G1 raw log loss | 0.4528 | `backtest_wp.json:gbm_grid/0/validation_logloss_raw` |
| GBM G2 raw log loss | 0.4539 | `backtest_wp.json:gbm_grid/1/validation_logloss_raw` |
| GBM G3 raw log loss | 0.4517 | `backtest_wp.json:gbm_grid/2/validation_logloss_raw` |
| GBM G4 raw log loss | 0.4626 | `backtest_wp.json:gbm_grid/3/validation_logloss_raw` |
| Logit raw log loss | 0.4470 | `backtest_wp.json:families/logit/raw/logloss` |
| Logit calibrated log loss | 0.4486 | `backtest_wp.json:families/logit/calibrated/logloss` |
| Logit raw Brier | 0.1485 | `backtest_wp.json:families/logit/raw/brier` |
| Logit calibrated Brier | 0.1491 | `backtest_wp.json:families/logit/calibrated/brier` |
| GBM (G3) raw log loss | 0.4517 | `backtest_wp.json:families/gbm/raw/logloss` |
| GBM (G3) calibrated log loss | 0.4555 | `backtest_wp.json:families/gbm/calibrated/logloss` |
| GBM (G3) raw Brier | 0.1493 | `backtest_wp.json:families/gbm/raw/brier` |
| GBM (G3) calibrated Brier | 0.1511 | `backtest_wp.json:families/gbm/calibrated/brier` |
| Chosen family | logit | `backtest_wp.json:chosen/family` |
| Elo margin scale 2023 | 20.49 | `backtest_wp.json:margin_scale_by_season/2023` |
| Elo margin scale 2024 | 20.82 | `backtest_wp.json:margin_scale_by_season/2024` |
| Elo margin scale 2025 | 21.12 | `backtest_wp.json:margin_scale_by_season/2025` |

### Test seasons 2024-2025: model minus baseline

| Quantity | Value | Source |
|---|---|---|
| Passes the paired-bootstrap comparison (CI entirely below zero and mean negative) | True | `backtest_wp.json:gate/passes` |
| Mean delta log loss (model minus baseline) | -0.0177 | `backtest_wp.json:gate/delta_logloss_mean` |
| Delta 95% interval, lower | -0.0317 | `backtest_wp.json:gate/delta_logloss_ci95/0` |
| Delta 95% interval, upper | -0.0049 | `backtest_wp.json:gate/delta_logloss_ci95/1` |
| Test games | 730 | `backtest_wp.json:test/games` |
| Test checkpoints | 29416 | `backtest_wp.json:test/checkpoints` |

### Test log loss and Brier (2024-2025)

| Quantity | Value | Source |
|---|---|---|
| Model log loss | 0.4634 | `backtest_wp.json:test/model/logloss` |
| Model log loss 95% interval, lower | 0.4390 | `backtest_wp.json:test/model/logloss_ci95/0` |
| Model log loss 95% interval, upper | 0.4890 | `backtest_wp.json:test/model/logloss_ci95/1` |
| Baseline log loss | 0.4811 | `backtest_wp.json:test/baseline/logloss` |
| Baseline log loss 95% interval, lower | 0.4472 | `backtest_wp.json:test/baseline/logloss_ci95/0` |
| Baseline log loss 95% interval, upper | 0.5170 | `backtest_wp.json:test/baseline/logloss_ci95/1` |
| Model Brier | 0.1557 | `backtest_wp.json:test/model/brier` |
| Model Brier 95% interval, lower | 0.1460 | `backtest_wp.json:test/model/brier_ci95/0` |
| Model Brier 95% interval, upper | 0.1659 | `backtest_wp.json:test/model/brier_ci95/1` |
| Baseline Brier | 0.1585 | `backtest_wp.json:test/baseline/brier` |
| Baseline Brier 95% interval, lower | 0.1472 | `backtest_wp.json:test/baseline/brier_ci95/0` |
| Baseline Brier 95% interval, upper | 0.1702 | `backtest_wp.json:test/baseline/brier_ci95/1` |
| Delta log loss, 2024 only | -0.0202 | `backtest_wp.json:test/by_season/2024/delta_logloss/mean` |
| Delta log loss 2024 interval, lower | -0.0451 | `backtest_wp.json:test/by_season/2024/delta_logloss/ci95/0` |
| Delta log loss 2024 interval, upper | 0.0002 | `backtest_wp.json:test/by_season/2024/delta_logloss/ci95/1` |
| Delta log loss, 2025 only | -0.0156 | `backtest_wp.json:test/by_season/2025/delta_logloss/mean` |
| Delta log loss 2025 interval, lower | -0.0326 | `backtest_wp.json:test/by_season/2025/delta_logloss/ci95/0` |
| Delta log loss 2025 interval, upper | 0.0001 | `backtest_wp.json:test/by_season/2025/delta_logloss/ci95/1` |

The 2025 interval's upper end lies just above zero. The comparison uses the pooled test seasons, so the result rests on 2024–2025 together.

### Validation (2023)

| Quantity | Value | Source |
|---|---|---|
| Model log loss | 0.4486 | `backtest_wp.json:validation/model/logloss` |
| Model log loss 95% interval, lower | 0.4120 | `backtest_wp.json:validation/model/logloss_ci95/0` |
| Model log loss 95% interval, upper | 0.4883 | `backtest_wp.json:validation/model/logloss_ci95/1` |
| Baseline log loss | 0.4730 | `backtest_wp.json:validation/baseline/logloss` |
| Model Brier | 0.1491 | `backtest_wp.json:validation/model/brier` |
| Baseline Brier | 0.1561 | `backtest_wp.json:validation/baseline/brier` |
| Delta log loss (model minus baseline) | -0.0243 | `backtest_wp.json:validation/delta_logloss/mean` |
| Delta log loss 95% interval, lower | -0.0425 | `backtest_wp.json:validation/delta_logloss/ci95/0` |
| Delta log loss 95% interval, upper | -0.0073 | `backtest_wp.json:validation/delta_logloss/ci95/1` |

### Calibration by time bucket (test seasons, model)

Predicted and observed are game-weighted means. The gap is predicted minus observed. The tolerance is 0.02 in each bucket; the model is within it in every test bucket. The slope is the game-weighted regression of observed on predicted within the bucket.

| Quantity | Value | Source |
|---|---|---|
| Q1: mean predicted | 0.6185 | `backtest_wp.json:test/calibration/model/Q1/mean_predicted` |
| Q1: observed home win | 0.6274 | `backtest_wp.json:test/calibration/model/Q1/observed_home_win` |
| Q1: gap | -0.0089 | `backtest_wp.json:test/calibration/model/Q1/gap` |
| Q1: slope | 1.0875 | `backtest_wp.json:test/calibration/model/Q1/slope` |
| Q2: mean predicted | 0.6188 | `backtest_wp.json:test/calibration/model/Q2/mean_predicted` |
| Q2: observed home win | 0.6274 | `backtest_wp.json:test/calibration/model/Q2/observed_home_win` |
| Q2: gap | -0.0086 | `backtest_wp.json:test/calibration/model/Q2/gap` |
| Q2: slope | 1.0978 | `backtest_wp.json:test/calibration/model/Q2/slope` |
| Q3: mean predicted | 0.6182 | `backtest_wp.json:test/calibration/model/Q3/mean_predicted` |
| Q3: observed home win | 0.6274 | `backtest_wp.json:test/calibration/model/Q3/observed_home_win` |
| Q3: gap | -0.0092 | `backtest_wp.json:test/calibration/model/Q3/gap` |
| Q3: slope | 0.9736 | `backtest_wp.json:test/calibration/model/Q3/slope` |
| Q4: mean predicted | 0.6241 | `backtest_wp.json:test/calibration/model/Q4/mean_predicted` |
| Q4: observed home win | 0.6274 | `backtest_wp.json:test/calibration/model/Q4/observed_home_win` |
| Q4: gap | -0.0033 | `backtest_wp.json:test/calibration/model/Q4/gap` |
| Q4: slope | 0.9989 | `backtest_wp.json:test/calibration/model/Q4/slope` |
| last 2 minutes: mean predicted | 0.6256 | `backtest_wp.json:test/calibration/model/last_2_min/mean_predicted` |
| last 2 minutes: observed home win | 0.6274 | `backtest_wp.json:test/calibration/model/last_2_min/observed_home_win` |
| last 2 minutes: gap | -0.0018 | `backtest_wp.json:test/calibration/model/last_2_min/gap` |
| last 2 minutes: slope | 1.0071 | `backtest_wp.json:test/calibration/model/last_2_min/slope` |
| overtime: mean predicted | 0.5507 | `backtest_wp.json:test/calibration/model/OT/mean_predicted` |
| overtime: observed home win | 0.5517 | `backtest_wp.json:test/calibration/model/OT/observed_home_win` |
| overtime: gap | -0.0010 | `backtest_wp.json:test/calibration/model/OT/gap` |
| overtime: slope | 0.9957 | `backtest_wp.json:test/calibration/model/OT/slope` |

Baseline gap by bucket, for comparison:

| Quantity | Value | Source |
|---|---|---|
| Q1: baseline gap | 0.0034 | `backtest_wp.json:test/calibration/baseline/Q1/gap` |
| Q2: baseline gap | -0.0048 | `backtest_wp.json:test/calibration/baseline/Q2/gap` |
| Q3: baseline gap | -0.0125 | `backtest_wp.json:test/calibration/baseline/Q3/gap` |
| Q4: baseline gap | -0.0113 | `backtest_wp.json:test/calibration/baseline/Q4/gap` |
| last 2 minutes: baseline gap | -0.0089 | `backtest_wp.json:test/calibration/baseline/last_2_min/gap` |
| overtime: baseline gap | -0.0051 | `backtest_wp.json:test/calibration/baseline/OT/gap` |

### Tip-off gap (test games)

The gap is the pre-game probability minus the model's probability at tip-off.

| Quantity | Value | Source |
|---|---|---|
| Mean gap | -0.0027 | `backtest_wp.json:tipoff_gap_test_games/mean` |
| Mean absolute gap | 0.0114 | `backtest_wp.json:tipoff_gap_test_games/mean_abs` |
| 95th percentile of absolute gap | 0.0317 | `backtest_wp.json:tipoff_gap_test_games/p95_abs` |

### Run

| Quantity | Value | Source |
|---|---|---|
| Runtime seconds | 1712.2 | `backtest_wp.json:runtime_seconds` |

## Files
- Spec: `docs/models/wp.md`.
- Report: `reports/backtest_wp.json`, `reports/backtest_wp_games.csv`.
- Code: `src/eurohoops/models/wp.py`, `src/eurohoops/models/wp_control.py`, `src/eurohoops/eval/wp_backtest.py`.
- Command: `eurohoops backtest --model wp`.
