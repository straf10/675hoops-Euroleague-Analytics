# In-game win probability (WP) model card

Version `0.2.0+wp.9702906e`, protocol `docs/models/wp.md` (v1, approved 2026-10-18). Built from the cached
EuroLeague play-by-play for seasons 2007-2025. The 2026 partial season is not used.

## What the model is

The chosen model is a logistic regression with time interactions (protocol section 5a), calibrated
by an isotonic map fitted on out-of-fold predictions of 2010-2022. It predicts the home team's win
probability at any game state: the score margin, the time left, overtime, the pre-game Elo
probability and the neutral-site flag. The closed-form baseline is the protocol's section 1 formula
with the Elo margin scale.

The gate passed. On the test seasons 2024 and 2025 the model's mean log loss per game is lower than
the baseline's, and the 95% paired bootstrap interval over games lies below zero. The game WP line
therefore uses the model, not the baseline. Player WPA is not computed and not published.

The in-game model is never a pre-game forecaster, and it writes nothing to `predictions/`. The
tip-off line starts at the published pre-game probability (section 7). The model is not committed:
`models/` is never written, and the fitted object lives in memory only.

## Data and exclusions

Of 5,122 mart games in 2007-2025, 4,861 are included. 261 are excluded: 82 not played (54 in 2019,
28 in 2021), 1 with an unusable team code (2018, `E2018_21`), 0 with no file, 0 score mismatches,
and 178 with an `ND` or sentinel clock (157 in 2016, 16 in 2017-2022, 5 in 2023-2025). The protocol's
173 counts the 2007-2022 games only; this run adds the 5 in 2023-2025. A blank clock on a play event
that is not a marker is also excluded under the same rule, and none were found. The 3,803 training
games, 328 validation games (2023) and 730 test games (2024-2025) are in the Numbers below.

## Readings of the protocol

Where the text was open, the reading below is the one used. The owner should check these.

1. **Isotonic rows.** The isotonic map is fitted on the out-of-fold scoring-event rows of 2010-2022
   (the training rows), not on checkpoints. Each season is predicted by a model fitted on earlier
   seasons only.
2. **Gate scope.** The gate compares the calibrated model's state probability with the closed-form
   baseline, both without the tip-off gap. The displayed line adds the gap; the gate does not.
3. **Baseline scale.** The Elo margin scale for each evaluation season is fitted on the included
   games (the exclusions apply) of earlier seasons only.
4. **GBM inputs.** Gradient boosting uses the section 4 features without the m-logit-tf interaction
   and without `t` (for trees `t` is a monotone copy of `tf`). `random_state` is fixed at 20261018,
   the only change from defaults. Settings G1 to G4 are chosen on validation raw log loss.
5. **Calibration buckets.** Each game's checkpoints in a bucket share weight 1 (game weighting).
   Q1 is `t` above 1800; Q2 is 1200 to 1800; Q3 is 600 to 1200; Q4 is 0 to 600, with the boundary
   value in the later bucket. The last 2 minutes are `t` 0 to 120, inside Q4. Overtime is every
   overtime checkpoint.
6. **Per-team control view.** The section 8 game-control formulas, written for the winner, are
   applied to each team's own WP. The parts are in `eurohoops.models.wp_control` and are not built
   into a page yet.
7. **Checkpoints at the period joins.** The regulation checkpoint at `t = 0` and the first overtime
   checkpoint at `t = 300` are the same game moment. Both are kept, as section 6 lists them.
8. **Rerun guard.** The backtest command refuses to run if `reports/backtest_wp.json` exists, so the
   gate is reported once.
9. **Assists and box data.** Not read. Under the 100/0 convention they change no WP value, and
   player WPA is not published.
10. **Dependency.** scikit-learn is declared as a direct dependency (it was only transitive before),
    with a mypy override because it ships no stubs.

## Numbers

Every value below is read from `reports/backtest_wp.json` by the test in
`tests/test_model_card_wp.py`. Log loss and Brier are checkpoint-averaged within each game, then
averaged over games. Intervals are 95% paired bootstrap intervals over whole games (10,000
resamples, seed 20261018).

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

### Gate (test seasons 2024-2025)

The gate passes if the 95% interval of the mean delta lies below zero and the mean delta is negative.

| Quantity | Value | Source |
|---|---|---|
| Gate passes | True | `backtest_wp.json:gate/passes` |
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

The 2025 interval's upper end lies just above zero. The gate uses the pooled test seasons, as the
protocol says, so the pass rests on 2024-2025 together.

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

Predicted and observed are game-weighted means. The gap is predicted minus observed. The protocol's
tolerance is 0.02 in each bucket; the model is within it in every test bucket. The slope is the
game-weighted regression of observed on predicted within the bucket.

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

For comparison, the baseline's gap by bucket:

| Quantity | Value | Source |
|---|---|---|
| Q1: baseline gap | 0.0034 | `backtest_wp.json:test/calibration/baseline/Q1/gap` |
| Q2: baseline gap | -0.0048 | `backtest_wp.json:test/calibration/baseline/Q2/gap` |
| Q3: baseline gap | -0.0125 | `backtest_wp.json:test/calibration/baseline/Q3/gap` |
| Q4: baseline gap | -0.0113 | `backtest_wp.json:test/calibration/baseline/Q4/gap` |
| last 2 minutes: baseline gap | -0.0089 | `backtest_wp.json:test/calibration/baseline/last_2_min/gap` |
| overtime: baseline gap | -0.0051 | `backtest_wp.json:test/calibration/baseline/OT/gap` |

### Tip-off gap (test games)

The gap is the pre-game probability minus the model's probability at tip-off (section 7).

| Quantity | Value | Source |
|---|---|---|
| Mean gap | -0.0027 | `backtest_wp.json:tipoff_gap_test_games/mean` |
| Mean absolute gap | 0.0114 | `backtest_wp.json:tipoff_gap_test_games/mean_abs` |
| 95th percentile of absolute gap | 0.0317 | `backtest_wp.json:tipoff_gap_test_games/p95_abs` |

### Run

| Quantity | Value | Source |
|---|---|---|
| Runtime seconds | 1712.2 | `backtest_wp.json:runtime_seconds` |
