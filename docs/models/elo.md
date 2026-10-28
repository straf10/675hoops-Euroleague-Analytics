# Elo: the published forecast and the baseline

Status: published (EuroLeague forecast page).

## What it is
A margin-adjusted Elo in the style of FiveThirtyEight's NBA ratings. Code: `src/eurohoops/models/elo.py`.

- One rating per team per competition, starting at 1500. Ratings come from one chronological pass over the games (`replay`). A game's prediction uses only earlier games.
- **Win probability:** `1 / (1 + 10^(-d/400))`, where `d` is the home rating minus the away rating plus the home-court advantage `hca` (zero at a neutral venue).
- **Update:** after a played game both ratings move by `K * M * (result - p)`, home up and away down by the same amount. `M = (margin + 3)^0.8 / (7.5 + 6e-3 * w)`, with `w` the winner's rating edge including home court. Forfeits (20-0 by decision) and unplayed games do not update ratings.
- **Season start:** each rating is pulled toward 1500 by the `reversion` weight, once per season.
- **Expected margin:** `d / s`. The scale `s` is a least-squares fit of margin on `d` through the origin, on the tuning seasons. The margin distribution is normal, with the residual RMS `sigma` of that fit (used for margin CRPS).
- **Baseline B0:** the home team wins at the home-win rate, with the home margin, fit on non-neutral games up to the last tuning season. Neutral games get 0.5 and 0.
- The model has one rating per team. It has no roster, injury, rest or travel input, and no totals model.

**Parameters** (`k`, `hca`, `reversion`) are grid-searched on tuning-season log loss. Warm-up seasons only build ratings. Test seasons are not used in the choice.

- **EuroLeague (live):** warm-up 2023, tuning 2024, test 2025, 60 grid points. `k` 20, `hca` 90, `reversion` 0.25. The best `reversion` sits on the grid edge.
- **EuroLeague history (not live):** warm-up 2007–2014, tuning 2015–2023, test 2024–2025, same grid. `k` 30, `hca` 110. Used only as `history_backtests` in `config.py`.

### Live logging
- Both competitions are forecast daily (`eurohoops predict`, run by `.github/workflows/daily.yml`). The forecasts are logged to `predictions/`.
- The site shows the EuroLeague forecast only (`SITE_FORECAST_MODEL = "elo"` in `config.py`).
- Each run replays Elo from the live backtest's first warm-up season, with the report's parameters. It writes one row per upcoming game: every game in rounds whose first tip-off is within 48 h of the run.
- Columns: `p_home` (four decimals), `exp_margin`, `model` (`elo`), `model_version`, `predicted_at_utc`.
- The scored row of a game is its latest row stamped before tip-off. Two EuroLeague rows are not provably before tip-off and are excluded.
- `model_version` is the package version plus an 8-character hash of the tuned parameters and the margin scale (`TunedModel.version`). The EuroLeague log holds `0.1.0+4356d891` (first round) and `0.2.0+425e6393`. The last two match the backtest reports.
- `eurohoops score` writes the scorecard `reports/live_scorecard.json`, under `elo` and `b0`.

## Results
Elo is scored on the tuning and test seasons against B0. Log loss and Brier: lower is better. Games are all rated, played games of the seasons shown.

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

## Files
- Code: `src/eurohoops/models/elo.py` (rating replay), `src/eurohoops/eval/backtest.py` (tuning and scoring), `src/eurohoops/predict.py` (daily log), `src/eurohoops/config.py` (`SITE_FORECAST_MODEL`, `history_backtests`).
- Reports: `reports/backtest_elo.json` (EuroLeague, live parameters), `reports/backtest_elo_history.json` (EuroLeague, long history), `reports/live_scorecard.json`.
- Logs: `predictions/euroleague_2026-27.csv`.
