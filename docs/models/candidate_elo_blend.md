# Candidate: Elo + ridge margin blend (`blend`)

**Status: candidate only. Not live.** The live EuroLeague forecast is still Elo (`docs/models/elo.md`,
`predictions/euroleague_2026-27.csv`). Nothing in `predict`, `publish` or the site reads this model,
and no `predictions/` or `odds/` file is written by it. It was built to answer one question: can a
margin-based forecast beat live Elo on points (margin) error and on win-probability log loss, scored
honestly out of sample?

Code: `src/eurohoops/models/ridge_margin.py` (the ridge margin model),
`src/eurohoops/eval/blend_backtest.py` (the candidate and its walk-forward scoring),
`eurohoops backtest --model blend` (writes `reports/backtest_blend.json`).

## Method
Two margin forecasts, averaged, then turned into a win probability with a Normal link.

- **Elo margin (live Elo, unchanged):** the live rating difference `d` (k 20, hca 90, reversion 0.25,
  `config.ELOR_ELO_PARAMS`) divided by a margin scale `s`. `s` is the least-squares fit of margin on
  `d` through the origin on seasons 2009 to s-1. Elo ratings are a single chronological replay, so
  each game's `d` uses only earlier games.
- **Ridge margin:** each team has a rating; the expected home margin is
  `rating[home] - rating[away] + hca` (`hca` only at a non-neutral venue). Ratings and `hca` are fitted
  by ridge regression (`lam` 8 on each rating, `lam / 10` on `hca`) to the margins of the rated games,
  weighted by `0.5 ** (age / half-life)` with a half-life of 480 days. The model is refitted once per
  calendar day, on the games that tipped off on earlier days, so a forecast never sees its own day's
  results or anything later.
- **Blend:** `mu = 0.5 * mu_elo + 0.5 * mu_ridge`.
- **Win probability:** `P(home win) = Phi(mu / sigma)`, with `sigma` the RMS residual of the blended
  margin on the previous four seasons (walk-forward residuals, so out of sample too).
- **Margin error:** `|mu - actual margin|`, mean over games. Totals are not modelled.

Hyperparameters: the ridge half-life and penalty were chosen on the warm-up seasons 2010 to 2014 (a
20-point grid, log loss, before any fold was scored). Their values were 480 days and `lam` 8. The
blend weight 0.5 is the midpoint of the candidates {0.25, 0.5, 0.75}, and it was looked at on the
scored folds (see Tried and rejected), so the scored folds are not a fully clean test of it.

## Protocol
- **Scored folds:** 2015 to 2025, every played, non-forfeit EuroLeague game (3,299 games). The 2026
  season is live and is not scored here. Season 2020 and 2021 (COVID) are kept, as in the other
  EuroLeague backtests.
- **Walk-forward:** every fold uses only data before it (fit seasons, sigma window, ridge history).
  The Elo ratings are replayed from 2007, which matches the other backtests.
- **Baseline:** the live Elo (logistic link on `d`, scale fitted on the same walk-forward window). The
  same games and the same margin scale are used for both arms.
- **Second look:** the same protocol on the warm-up folds 2010 to 2014 (1,134 games). It is reported
  but it was used to choose the ridge hyperparameters, so it is not an independent test.
- **Uncertainty:** the paired difference (candidate minus live) per game, with a 95% percentile CI from
  10,000 resamples of whole seasons (`paired_bootstrap_ci_clustered`, seed 20261019).
- **Caveat on the baseline:** the live Elo parameters were tuned on 2024, which is inside the scored
  folds 2024 and 2025. That gives live Elo a small in-sample advantage on those two seasons. Walk-
  forward re-selection of Elo's parameters did worse (below), so the advantage does not change the
  verdict.

## Results
Log loss and Brier are lower-is-better, accuracy higher-is-better, margin error is points.
Source: `reports/backtest_blend.json` (`folds` block for 2015 to 2025, `warmup` block for 2010 to 2014).

Pooled, 2015 to 2025 (3,299 games):

| Model | Log loss | Brier | Accuracy | Margin MAE (pts) |
|---|---|---|---|---|
| Live Elo (logistic) | 0.610401 | 0.211438 | 0.663231 | 9.300409 |
| Blend (candidate) | 0.609162 | 0.210946 | 0.665353 | 9.255311 |
| B0 (home base rate) | 0.660740 | 0.233971 | 0.625946 | 9.951787 |

Paired, candidate minus live (pooled, season-cluster bootstrap, 95% CI):

| Quantity | Mean | 95% CI |
|---|---|---|
| Log loss | -0.001239 | [-0.003340, +0.000798] |
| Margin MAE | -0.045098 | [-0.065530, -0.026206] |

Per season (live / candidate):

| Season | Games | Log loss | Brier | Accuracy | Margin MAE |
|---|---|---|---|---|---|
| 2015 | 250 | 0.5890 / 0.5844 | 0.2018 / 0.2002 | 0.676 / 0.684 | 10.13 / 10.05 |
| 2016 | 259 | 0.6108 / 0.6099 | 0.2116 / 0.2117 | 0.660 / 0.676 | 8.79 / 8.70 |
| 2017 | 260 | 0.6060 / 0.6070 | 0.2089 / 0.2094 | 0.673 / 0.677 | 9.19 / 9.11 |
| 2018 | 260 | 0.5713 / 0.5616 | 0.1937 / 0.1901 | 0.696 / 0.712 | 9.02 / 8.92 |
| 2019 | 252 | 0.5876 / 0.5895 | 0.2018 / 0.2029 | 0.675 / 0.667 | 9.41 / 9.39 |
| 2020 | 328 | 0.6550 / 0.6605 | 0.2301 / 0.2320 | 0.643 / 0.634 | 9.87 / 9.87 |
| 2021 | 299 | 0.6089 / 0.6078 | 0.2111 / 0.2107 | 0.656 / 0.649 | 9.63 / 9.60 |
| 2022 | 328 | 0.6257 / 0.6230 | 0.2185 / 0.2170 | 0.649 / 0.659 | 9.08 / 9.04 |
| 2023 | 331 | 0.5885 / 0.5883 | 0.2014 / 0.2014 | 0.710 / 0.704 | 9.02 / 9.02 |
| 2024 | 330 | 0.6184 / 0.6166 | 0.2161 / 0.2150 | 0.642 / 0.648 | 9.11 / 9.05 |
| 2025 | 402 | 0.6296 / 0.6275 | 0.2202 / 0.2193 | 0.634 / 0.634 | 9.16 / 9.13 |

The candidate has the lower log loss in 8 of 11 seasons, the lower margin error in 10 of 11 (2020 is
the exception, by 0.003 points), and the lower Brier in 6 of 11 (2023 is a tie).

Warm-up, 2010 to 2014 (1,134 games, not independent: the ridge hyperparameters were chosen here):

| Model | Log loss | Brier | Accuracy | Margin MAE (pts) |
|---|---|---|---|---|
| Live Elo (logistic) | 0.567203 | 0.191626 | 0.716931 | 9.117562 |
| Blend (candidate) | 0.559911 | 0.188846 | 0.718695 | 9.081380 |

Paired, candidate minus live: log loss -0.007291 (CI [-0.011461, -0.004273]), margin MAE -0.036182
(CI [-0.086469, +0.011755]).

## Reading the results
- **Points (margin) error:** the candidate lowers the pooled margin MAE by 0.045 points on the scored
  folds, and the CI excludes zero. This is the clearest gain.
- **Log loss:** the pooled gain is -0.0012, and its CI spans zero. The point estimate is in the right
  direction, but it does not meet the usual bar on its own. The warm-up window shows a larger gain,
  but that window chose the hyperparameters.
- **Where the link matters:** a Normal link on live Elo's own margin (no ridge term) gives -0.00098 log
  loss against live (CI [-0.00306, +0.00149]), so most of the candidate's point gain on log loss is not
  from the link either.
- **Verdict:** the candidate is better on margin error (significant) and better on the point estimates
  of log loss, Brier and accuracy over 2015 to 2025. It is not a verdict to replace the live model.
  Replacing it would need a pre-registered promotion rule (none is declared here) and a live paired
  comparison, as in `docs/models/elo_roster_prior.md` and `docs/models/elo_calibrated.md`.

## Tried and rejected
Exploratory runs, walk-forward on the same folds, with the same metrics. They were not committed as
scripts; the numbers are rounded from those runs. The live Elo log loss in those runs is 0.6104.

| Idea | Pooled log loss | Margin MAE | Outcome |
|---|---|---|---|
| Platt recalibration of Elo's `d` (fit on prior seasons) | 0.6126 | 9.300 | Worse. Same family as the ELOC protocol (`elo_calibrated.md`) |
| Logistic on `d` + rest difference + back-to-back indicator | 0.6140 | 9.300 | Worse. Rest carries no signal on these folds |
| Logistic on `d` + rest difference | 0.6129 | 9.300 | Worse |
| Margin OLS on `d` (Normal link) | 0.6099 | 9.315 | Same as live within noise; no MAE gain |
| Margin OLS on `d` + rest + back-to-back (Normal link) | 0.6108 | 9.338 | Worse on both |
| Walk-forward Elo parameter choice (120-point grid on prior seasons) | 0.6131 | 9.288 | Worse log loss; MAE slightly better |
| Ridge margin alone, Normal link | 0.6125 | 9.282 | Worse log loss; MAE better |
| Blend, Elo weight 0.75 | 0.6090 | 9.299 | Close to 0.5; not chosen |
| Blend, Elo weight 0.25 | 0.6099 | 9.259 | Close on MAE; log loss not better than 0.5 |
| Blend, Elo weight 0.5, exploratory (one sigma for all folds) | 0.6088 | 9.266 | Superseded by the candidate |
| Blend, Elo weight 0.5 (candidate, per-fold sigma) | 0.6092 | 9.255 | Kept |

The blend rows for weights 0.25, 0.5 and 0.75 come from an exploratory version that used one sigma
for all folds. The candidate uses a per-fold sigma, so its numbers in the Results section are the ones
to quote.

Not tried here: a roster-based prior (the ELOR protocol covers it and is not run), and a totals model.

## Limitations
- One sample of 11 scored seasons (3,299 games). The season-cluster CIs are wide relative to the
  log-loss gain.
- The blend weight was chosen after looking at the scored folds. In the exploratory runs, weights 0.5
  and 0.75 differed by 0.0002 in pooled log loss, so the choice matters little for log loss but is still
  not independent of the folds.
- The ridge model fits on margins only and does not know about injuries, roster changes or rest. Its
  forecasts are only as good as the rated results.
- Margin error is the only points metric. Totals are not forecast.

## Reproduce
    uv run eurohoops backtest --model blend

It reads `data/marts/eurohoops.duckdb` and writes `reports/backtest_blend.json` (both folds and warm-up).
The run is deterministic (fixed bootstrap seed).

## Numbers
Each value below is in `reports/backtest_blend.json`. `tests/test_model_card_blend.py` checks every row.

| Quantity | Value | Report |
|---|---|---|
| Scored games, 2015 to 2025 | 3299 | `backtest_blend.json:folds.games` |
| Live Elo log loss, pooled | 0.610401 | `backtest_blend.json:folds.pooled.live_elo.log_loss` |
| Blend log loss, pooled | 0.609162 | `backtest_blend.json:folds.pooled.blend.log_loss` |
| Live Elo Brier, pooled | 0.211438 | `backtest_blend.json:folds.pooled.live_elo.brier` |
| Blend Brier, pooled | 0.210946 | `backtest_blend.json:folds.pooled.blend.brier` |
| Live Elo accuracy, pooled | 0.663231 | `backtest_blend.json:folds.pooled.live_elo.accuracy` |
| Blend accuracy, pooled | 0.665353 | `backtest_blend.json:folds.pooled.blend.accuracy` |
| Live Elo margin MAE, pooled | 9.300409 | `backtest_blend.json:folds.pooled.live_elo.margin_mae` |
| Blend margin MAE, pooled | 9.255311 | `backtest_blend.json:folds.pooled.blend.margin_mae` |
| B0 log loss, pooled | 0.660740 | `backtest_blend.json:folds.pooled.b0.log_loss` |
| Blend minus live, log loss | -0.001239 | `backtest_blend.json:folds.paired_blend_minus_live.log_loss.mean` |
| Blend minus live, log loss, CI low | -0.003340 | `backtest_blend.json:folds.paired_blend_minus_live.log_loss.ci95.0` |
| Blend minus live, log loss, CI high | 0.000798 | `backtest_blend.json:folds.paired_blend_minus_live.log_loss.ci95.1` |
| Blend minus live, margin MAE | -0.045098 | `backtest_blend.json:folds.paired_blend_minus_live.margin_mae.mean` |
| Blend minus live, margin MAE, CI low | -0.065530 | `backtest_blend.json:folds.paired_blend_minus_live.margin_mae.ci95.0` |
| Blend minus live, margin MAE, CI high | -0.026206 | `backtest_blend.json:folds.paired_blend_minus_live.margin_mae.ci95.1` |
| Warm-up live Elo log loss, pooled | 0.567203 | `backtest_blend.json:warmup.pooled.live_elo.log_loss` |
| Warm-up blend log loss, pooled | 0.559911 | `backtest_blend.json:warmup.pooled.blend.log_loss` |
| Warm-up blend minus live, log loss | -0.007291 | `backtest_blend.json:warmup.paired_blend_minus_live.log_loss.mean` |
| Warm-up blend minus live, margin MAE | -0.036182 | `backtest_blend.json:warmup.paired_blend_minus_live.margin_mae.mean` |
