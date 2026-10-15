# Elo: the published forecast and the baseline

Weeks 0–3 (PLAN §5.1, "M0"). Code: `src/eurohoops/models/elo.py` (the rating replay),
`src/eurohoops/eval/backtest.py` (tuning and scoring), `src/eurohoops/predict.py` (the daily log).
Reports:
- `reports/backtest_elo.json` (EuroLeague, the live parameters);
- `reports/backtest_elo_history.json` (EuroLeague, long history, informational);
- `reports/backtest_elo_gbl.json` (GBL, the live parameters);
- `reports/live_scorecard.json` and `reports/live_scorecard_gbl.json` (2026-27 live score).

Every decimal below is in the Numbers table with its report path, checked by
`tests/test_model_card_elo.py`.

## What it does
A margin-of-victory-adjusted Elo in the style of FiveThirtyEight's NBA ratings (PLAN reference R5).
Each team has one rating per competition, starting at 1500. Ratings come from one chronological
pass over the games (`replay`); a game's prediction uses only games processed before it, so it can
never see its own result.
- **Win probability:** `1 / (1 + 10^(-d/400))`, where `d` is the home rating minus the away rating
  plus the home-court advantage `hca` (zero at a neutral venue).
- **Update:** after a played game both ratings move by `K * M * (result - p)`, home up and away
  down by the same amount. `M = (margin + 3)^0.8 / (7.5 + 6e-3 * w)` is the 538 margin multiplier,
  with `w` the winner's rating edge including home court. Forfeits (20-0 by decision) and unplayed
  games do not update ratings.
- **Season start:** each rating is pulled toward 1500 by the `reversion` weight, once per season.
- **Expected margin:** `d / s`, where the scale `s` is a least-squares fit of margin on `d`
  through the origin on the tuning seasons. The margin distribution is a normal with the residual
  RMS `sigma` of that fit on the tuning seasons (used for the margin CRPS).
- **Baseline B0:** the home team wins at the home-win rate, with the home margin, fit on the
  non-neutral games up to the last tuning season. Neutral games get 0.5 and 0.

## Parameters and how they were chosen
Three parameters per competition: `k`, `hca`, `reversion`. Each is found by grid search on the
tuning-season log loss, with the warm-up seasons only building ratings (`run_backtest`). The
test seasons are scored once and play no part in the choice. There is no separate validation split
for Elo.
- **EuroLeague (live):** warm-up 2023, tuning 2024, test 2025, 60 grid points. Tuned `k` 20,
  `hca` 90, `reversion` 0.25. The best `reversion` sits on the grid edge (`grid.best_on_edge`);
  the parameters were frozen before the 2026-27 start (PLAN decision D-a,
  `reports/week3_closeout.md`), so this is information only.
- **EuroLeague (history):** the same grid on a long window, warm-up 2007–2014, tuning
  2015–2023, test 2024–2025 (`backtest_elo_history.json`). It tunes to `k` 30, `hca` 110. It is
  informational and never used live (`history_backtests` in `config.py`).
- **GBL (live):** warm-up 2018–2021, tuning 2022–2023, test 2024–2025, on a wider 450-point grid.
  The grid best (`k` 50, `hca` 170, `reversion` 0) beat the live values on tuning but not on test:
  the CI of the log-loss gap on test spans 0. The live values were therefore **frozen** at `k` 40,
  `hca` 130, `reversion` 0.25 (`Backtest.frozen`, 2026-09-25, `reports/week3_closeout.md`), and
  the report's `tuned` block reads those, not the grid best.

## Competitions and what is shown
Both competitions are forecast daily and logged to `predictions/` (append-only). The site shows
the **EuroLeague** forecast only: the Forecasts page leads with Elo (`SITE_FORECAST_MODEL = "elo"`
in `config.py`). GBL Elo is logged and scored (`reports/live_scorecard_gbl.json`) but not shown.

## Results
Elo is scored on the tuning and test seasons against B0. Log loss, lower is better. Games are all
rated, played games of those seasons.
- **EuroLeague test (2025, 402 games):** log loss 0.629327, Brier 0.219998, accuracy 0.641791.
  B0 scores 0.655673 log loss. The paired difference Elo − B0 is −0.026346, 95% CI [−0.04878,
  −0.004545]: a real but modest gain.
- **EuroLeague test, long-history parameters (2024–2025, 732 games):** log loss 0.629221, almost the
  same as the live parameters; the difference to B0 is −0.030605, CI [−0.052174, −0.009555].
- **GBL test (2024–2025, 340 games):** log loss 0.484529, Brier 0.159803, accuracy 0.761765, against
  B0 at 0.667972. The paired difference is −0.183443, CI [−0.226229, −0.137582]. The GBL gain over
  the base rate is much larger than the EuroLeague's.
- **Margin:** on EuroLeague test the mean absolute error is 9.123502 points (B0 9.59143), a
  difference of −0.467929 points, CI [−0.807082, −0.13469].
- **Calibration:** the expected calibration error is 0.049364 on EuroLeague test and 0.050269 on
  GBL test, against 0.005338 and 0.025294 for the constant B0. Elo is sharper than B0 at the
  cost of some reliability.

## Role: the published forecast and the R1 baseline
Elo is baseline B1 (PLAN §5) and the model every other forecast is compared with. It stays the
published forecast until a flagship passes the pre-registered promotion rule (PLAN §8.1 R1).
The rule is committed in `m5.md` ("Flagship promotion rule", EuroLeague, M5) and `m1.md`
("Flagship promotion rule, GBL", M1): two looks per competition, a 97.5% paired-bootstrap CI of
the per-game log-loss gap (flagship − Elo) entirely below 0, and a mean gap of −0.01 or lower.

The Phase D models audit (`docs/models/audit_phase_d.md`) found that no model beats Elo on win
probability yet: on EuroLeague test M1 and M5 tie it within the CI, and their real gains are in
totals. The audit computed no live paired comparison; that belongs to the R1 looks.

## Live
The daily workflow (`.github/workflows/daily.yml`, 08:00 UTC) runs `eurohoops predict`. For each
competition it replays Elo from the live backtest's first warm-up season with the parameters in the
live backtest report, and appends one row per upcoming game before tip-off.
- **Logs:** `predictions/euroleague_2026-27.csv` and `predictions/gbl_2026-27.csv`, with
  `p_home` (four decimals), `exp_margin`, `model` (`elo`), `model_version` and `predicted_at_utc`.
  A row is never edited.
- **`model_version`:** the package version plus an 8-character hash of the tuned parameters and the
  margin scale (`TunedModel.version`). The EuroLeague log holds `0.1.0+4356d891` (first round) and
  `0.2.0+425e6393`; the GBL log holds `0.2.0+df05260c`. The latter two match the backtest reports'
  `model_version`.
- **Scoring:** `eurohoops score` writes the scorecards. Rows whose stamp is not provably before
  tip-off are excluded (two EuroLeague rows are not provable).

The live 2026-27 numbers change with every scored game, so this card does not quote them: they are
in `reports/live_scorecard.json` and `reports/live_scorecard_gbl.json` under `elo` and `b0`
(descriptive only, a small sample; Elo is scored on the games it logged before tip-off).

## Limitations
- One rating per team: no roster, injuries, rest or travel. It cannot see a trade, an injury or a
  rebuilt squad until results arrive; the season-start reversion is the only preseason adjustment.
- The EuroLeague live parameters were tuned on a single season (2024), a short window; the
  long-history run tunes to different values. The `reversion` optimum sits on the grid edge.
- The EuroLeague gain over B0 is modest, and calibration error is larger than B0's in both
  competitions.
- The GBL parameters are frozen at values that are not the tuning optimum, by a deliberate choice
  described above.
- Elo has no total-points model: the totals error in the reports uses a baseline of the previous
  two seasons' mean total, not a rating.
- Live samples are small. The live scorecards are not a verdict.

## Numbers
| Quantity | Value | Report |
|---|---|---|
| EuroLeague live: warm-up season | 2023 | `backtest_elo.json:seasons.warmup.0` |
| EuroLeague live: tuning season | 2024 | `backtest_elo.json:seasons.tuning.0` |
| EuroLeague live: test season | 2025 | `backtest_elo.json:seasons.test.0` |
| EuroLeague live: grid points | 60 | `backtest_elo.json:grid.size` |
| EuroLeague live: tuned k | 20 | `backtest_elo.json:tuned.k` |
| EuroLeague live: tuned hca | 90 | `backtest_elo.json:tuned.hca` |
| EuroLeague live: tuned reversion | 0.25 | `backtest_elo.json:tuned.reversion` |
| EuroLeague live: margin scale | 24.53358 | `backtest_elo.json:tuned.margin_scale` |
| EuroLeague live: margin sigma | 11.737523 | `backtest_elo.json:tuned.margin_sigma` |
| EuroLeague live: home win probability at equal ratings | 0.626699 | `backtest_elo.json:tuned.home_win_prob_equal_ratings` |
| EuroLeague live: tuning log loss | 0.618331 | `backtest_elo.json:metrics.tuning.elo.log_loss` |
| EuroLeague live: test games | 402 | `backtest_elo.json:metrics.test.elo.n` |
| EuroLeague live: test log loss | 0.629327 | `backtest_elo.json:metrics.test.elo.log_loss` |
| EuroLeague live: test Brier | 0.219998 | `backtest_elo.json:metrics.test.elo.brier` |
| EuroLeague live: test accuracy | 0.641791 | `backtest_elo.json:metrics.test.elo.accuracy` |
| EuroLeague live: test margin MAE | 9.123502 | `backtest_elo.json:metrics.test.elo.margin_mae` |
| EuroLeague live: test ECE | 0.049364 | `backtest_elo.json:metrics.test.elo.ece` |
| EuroLeague live: test log loss, B0 | 0.655673 | `backtest_elo.json:metrics.test.b0.log_loss` |
| EuroLeague live: test margin MAE, B0 | 9.59143 | `backtest_elo.json:metrics.test.b0.margin_mae` |
| EuroLeague live: test ECE, B0 | 0.005338 | `backtest_elo.json:metrics.test.b0.ece` |
| EuroLeague live: test log loss, Elo minus B0 | -0.026346 | `backtest_elo.json:test_log_loss_diff_elo_minus_b0.mean` |
| EuroLeague live: test log loss, Elo minus B0, CI low | -0.04878 | `backtest_elo.json:test_log_loss_diff_elo_minus_b0.ci95.0` |
| EuroLeague live: test log loss, Elo minus B0, CI high | -0.004545 | `backtest_elo.json:test_log_loss_diff_elo_minus_b0.ci95.1` |
| EuroLeague live: test margin error, Elo minus B0 | -0.467929 | `backtest_elo.json:test_margin_abs_error_diff_elo_minus_b0.mean` |
| EuroLeague live: test margin error, Elo minus B0, CI low | -0.807082 | `backtest_elo.json:test_margin_abs_error_diff_elo_minus_b0.ci95.0` |
| EuroLeague live: test margin error, Elo minus B0, CI high | -0.13469 | `backtest_elo.json:test_margin_abs_error_diff_elo_minus_b0.ci95.1` |
| EuroLeague history: tuned k | 30 | `backtest_elo_history.json:tuned.k` |
| EuroLeague history: tuned hca | 110 | `backtest_elo_history.json:tuned.hca` |
| EuroLeague history: tuning games | 2567 | `backtest_elo_history.json:metrics.tuning.elo.n` |
| EuroLeague history: tuning log loss | 0.606116 | `backtest_elo_history.json:metrics.tuning.elo.log_loss` |
| EuroLeague history: test games | 732 | `backtest_elo_history.json:metrics.test.elo.n` |
| EuroLeague history: test log loss | 0.629221 | `backtest_elo_history.json:metrics.test.elo.log_loss` |
| EuroLeague history: test log loss, Elo minus B0 | -0.030605 | `backtest_elo_history.json:test_log_loss_diff_elo_minus_b0.mean` |
| EuroLeague history: test log loss, Elo minus B0, CI low | -0.052174 | `backtest_elo_history.json:test_log_loss_diff_elo_minus_b0.ci95.0` |
| EuroLeague history: test log loss, Elo minus B0, CI high | -0.009555 | `backtest_elo_history.json:test_log_loss_diff_elo_minus_b0.ci95.1` |
| GBL live: grid points | 450 | `backtest_elo_gbl.json:grid.size` |
| GBL grid best: k | 50 | `backtest_elo_gbl.json:grid.best.k` |
| GBL grid best: hca | 170 | `backtest_elo_gbl.json:grid.best.hca` |
| GBL grid best: reversion | 0 | `backtest_elo_gbl.json:grid.best.reversion` |
| GBL grid best minus live, test log loss | 0.000535 | `backtest_elo_gbl.json:grid.best_minus_tuned_log_loss.test.mean` |
| GBL grid best minus live, test, CI low | -0.019354 | `backtest_elo_gbl.json:grid.best_minus_tuned_log_loss.test.ci95.0` |
| GBL grid best minus live, test, CI high | 0.023376 | `backtest_elo_gbl.json:grid.best_minus_tuned_log_loss.test.ci95.1` |
| GBL live: tuned k | 40 | `backtest_elo_gbl.json:tuned.k` |
| GBL live: tuned hca | 130 | `backtest_elo_gbl.json:tuned.hca` |
| GBL live: tuned reversion | 0.25 | `backtest_elo_gbl.json:tuned.reversion` |
| GBL live: tuning log loss | 0.43133 | `backtest_elo_gbl.json:metrics.tuning.elo.log_loss` |
| GBL live: test games | 340 | `backtest_elo_gbl.json:metrics.test.elo.n` |
| GBL live: test log loss | 0.484529 | `backtest_elo_gbl.json:metrics.test.elo.log_loss` |
| GBL live: test Brier | 0.159803 | `backtest_elo_gbl.json:metrics.test.elo.brier` |
| GBL live: test accuracy | 0.761765 | `backtest_elo_gbl.json:metrics.test.elo.accuracy` |
| GBL live: test ECE | 0.050269 | `backtest_elo_gbl.json:metrics.test.elo.ece` |
| GBL live: test log loss, B0 | 0.667972 | `backtest_elo_gbl.json:metrics.test.b0.log_loss` |
| GBL live: test ECE, B0 | 0.025294 | `backtest_elo_gbl.json:metrics.test.b0.ece` |
| GBL live: test log loss, Elo minus B0 | -0.183443 | `backtest_elo_gbl.json:test_log_loss_diff_elo_minus_b0.mean` |
| GBL live: test log loss, Elo minus B0, CI low | -0.226229 | `backtest_elo_gbl.json:test_log_loss_diff_elo_minus_b0.ci95.0` |
| GBL live: test log loss, Elo minus B0, CI high | -0.137582 | `backtest_elo_gbl.json:test_log_loss_diff_elo_minus_b0.ci95.1` |
