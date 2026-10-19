# Candidate: Elo + ridge margin blend (`blend`), with a roster term (`blend_roster`)

**Status: candidate only. Not live.** The live EuroLeague forecast is still Elo (`docs/models/elo.md`,
`predictions/euroleague_2026-27.csv`). Nothing in `predict`, `publish` or the site reads this model,
and no `predictions/` or `odds/` file is written by it.

Code: `src/eurohoops/models/ridge_margin.py` (ridge margin model),
`src/eurohoops/eval/blend_backtest.py` (candidate, walk-forward choices, scoring),
`eurohoops backtest --model blend` (writes `reports/backtest_blend.json`).

## Method
Two margin forecasts, mixed, then turned into a win probability with a Normal link.

- **Elo margin (live Elo, unchanged):** `d / s`, where `d` is the live rating difference (k 20, hca 90,
  reversion 0.25, `config.ELOR_ELO_PARAMS`) and `s` is the least-squares scale of margin on `d` over
  seasons 2009 to s-1.
- **Ridge margin:** expected home margin `rating[home] - rating[away] + hca` (hca only at a non-neutral
  venue), ratings fitted by ridge regression (`lam` 8 on each rating, `lam / 10` on hca) to rated
  margins, weights `0.5 ** (age / 480 days)`. Refitted once per game day on earlier days only.
- **Blend:** `mu = w * mu_elo + (1 - w) * mu_ridge`, with `w` chosen walk-forward (below).
- **Win probability:** `P(home win) = Phi(mu / sigma)`, sigma the RMS residual of the blended margin
  over the previous four seasons.
- **Roster term (`blend_roster`):** `mu += beta * (share_home - share_away)` in regular-season rounds
  1 to 10 only. `share` is the club's returning-minutes share at season start: last season's minutes
  of players on this season's season-start roster, over last season's club minutes
  (`models/continuity.py`, roster lists from `data/raw/euroleague/people`). `beta` is the no-intercept
  least-squares slope of the early-round residuals of `blend` on the earlier seasons. Shares vary
  across clubs (standard deviation 0.09 to 0.16 in the seasons checked: 2015, 2020, 2025).

**This is not the ELOR protocol.** ELOR (`docs/models/elo_roster_prior.md`) blends a roster rating
built from the M3 player part into Elo's ratings, and fades it over rounds. That code is not built,
and the protocol has not been run. `blend_roster` is a simpler stand-in: a margin offset from
returning minutes, active only in rounds 1 to 10, with a fitted slope and no player ratings.

## Walk-forward choices (nothing is chosen on the games it forecasts)
For each scored season `s`, using only seasons before `s`:
- **Elo scale:** on seasons 2009 to s-1.
- **Blend weight `w`:** from the grid 0.0, 0.1, ..., 1.0, the value with the lowest log loss over
  seasons 2009 to s-1. Each grid value is scored with its own sigma (the window below).
- **Sigma:** RMS residual over seasons s-4 to s-1 of the chosen blend.
- **Roster slope `beta`:** least squares on seasons 2009 to s-1, early rounds only.
- **Ridge half-life and penalty:** chosen once on the warm-up seasons 2010 to 2014 (a 20-point grid),
  before any scored season was seen. They are not re-chosen per fold.

Earlier drafts fixed `w = 0.5` after looking at the scored folds. That is replaced by the walk-forward
choice above; the results below are from the walk-forward version only.

## Protocol
- **Scored folds:** 2015 to 2025, every played, non-forfeit EuroLeague game (3,299 games; 1,000 of them
  are regular-season rounds 1 to 10). 2026 is live and not scored here.
- **Baseline:** live Elo (logistic link on `d`, same games, same walk-forward scale).
- **Second look:** warm-up folds 2010 to 2014 (1,134 games; 600 early). Not independent: the ridge
  hyperparameters were chosen on those seasons.
- **Uncertainty:** paired per-game differences (candidate minus live), 95% percentile CI from 10,000
  resamples of whole seasons (`paired_bootstrap_ci_clustered`, seed 20261019).
- **Baseline caveat:** live Elo parameters were tuned on 2024, which sits inside the scored folds 2024
  and 2025. That gives live Elo a small in-sample advantage there.

## Results (from `reports/backtest_blend.json`)
Log loss and Brier: lower is better. Accuracy: higher is better. Margin error: points (MAE).

### All rounds, 2015 to 2025 (3,299 games)
| Model | Log loss | Brier | Accuracy | Margin MAE |
|---|---|---|---|---|
| Live Elo (logistic) | 0.610401 | 0.211438 | 0.663231 | 9.300409 |
| Blend (walk-forward w) | 0.608936 | 0.210896 | 0.663231 | 9.265360 |
| Blend + roster term | 0.608864 | 0.210777 | 0.666566 | 9.270085 |
| B0 (home base rate) | 0.660740 | 0.233971 | 0.625947 | 9.951787 |

Paired, candidate minus live (all rounds):
| Comparison | Log loss | 95% CI | Margin MAE | 95% CI |
|---|---|---|---|---|
| Blend minus live | -0.001465 | [-0.003423, +0.000603] | -0.035049 | [-0.046304, -0.024696] |
| Blend + roster minus live | -0.001538 | [-0.004232, +0.001400] | -0.030324 | [-0.050445, -0.011176] |
| Blend + roster minus blend | -0.000072 | [-0.001237, +0.001052] | +0.004725 | [-0.008838, +0.018227] |

### Early rounds 1 to 10, 2015 to 2025 (1,000 games)
| Model | Log loss | Brier | Accuracy | Margin MAE |
|---|---|---|---|---|
| Live Elo (logistic) | 0.629069 | 0.219923 | 0.635000 | 9.567206 |
| Blend (walk-forward w) | 0.628613 | 0.219739 | 0.635000 | 9.524454 |
| Blend + roster term | 0.628429 | 0.219366 | 0.646000 | 9.540041 |
| B0 (home base rate) | 0.667528 | 0.237287 | 0.614000 | 10.019991 |

Paired, candidate minus live (early):
| Comparison | Log loss | 95% CI | Margin MAE | 95% CI |
|---|---|---|---|---|
| Blend minus live | -0.000456 | [-0.002887, +0.002324] | -0.042751 | [-0.090857, +0.005643] |
| Blend + roster minus live | -0.000640 | [-0.006382, +0.005332] | -0.027164 | [-0.089945, +0.034233] |
| Blend + roster minus blend | -0.000184 | [-0.004144, +0.003529] | +0.015587 | [-0.028611, +0.061591] |

### Per season (log loss / margin MAE; live, blend, blend + roster)
| Season | All rounds: log loss | All rounds: MAE | Early: log loss | Early: MAE |
|---|---|---|---|---|
| 2015 | 0.5890 / 0.5840 / 0.5843 | 10.13 / 10.07 / 10.05 | 0.6196 / 0.6207 / 0.6218 | 10.96 / 10.88 / 10.82 |
| 2016 | 0.6108 / 0.6098 / 0.6099 | 8.79 / 8.74 / 8.77 | 0.6091 / 0.6041 / 0.6044 | 8.29 / 8.17 / 8.26 |
| 2017 | 0.6060 / 0.6060 / 0.6071 | 9.19 / 9.13 / 9.16 | 0.6320 / 0.6335 / 0.6372 | 10.13 / 10.10 / 10.18 |
| 2018 | 0.5713 / 0.5624 / 0.5602 | 9.02 / 8.95 / 8.94 | 0.6169 / 0.6094 / 0.6023 | 9.53 / 9.32 / 9.28 |
| 2019 | 0.5876 / 0.5877 / 0.5878 | 9.41 / 9.39 / 9.40 | 0.6315 / 0.6322 / 0.6325 | 10.94 / 10.92 / 10.95 |
| 2020 | 0.6550 / 0.6613 / 0.6641 | 9.87 / 9.85 / 9.89 | 0.7068 / 0.7181 / 0.7285 | 10.32 / 10.22 / 10.37 |
| 2021 | 0.6089 / 0.6070 / 0.6088 | 9.63 / 9.61 / 9.62 | 0.5882 / 0.5889 / 0.5952 | 10.16 / 10.26 / 10.30 |
| 2022 | 0.6257 / 0.6237 / 0.6252 | 9.08 / 9.05 / 9.07 | 0.6457 / 0.6433 / 0.6489 | 8.74 / 8.68 / 8.74 |
| 2023 | 0.5885 / 0.5868 / 0.5858 | 9.02 / 9.01 / 9.01 | 0.5804 / 0.5766 / 0.5730 | 8.83 / 8.90 / 8.92 |
| 2024 | 0.6184 / 0.6167 / 0.6127 | 9.11 / 9.06 / 9.03 | 0.6192 / 0.6168 / 0.6024 | 7.25 / 7.27 / 7.13 |
| 2025 | 0.6296 / 0.6278 / 0.6267 | 9.16 / 9.14 / 9.13 | 0.6663 / 0.6653 / 0.6607 | 9.54 / 9.50 / 9.46 |

Chosen walk-forward weight `w` on Elo: 0.7 in 10 of 11 seasons, 0.6 in 2019. Chosen roster slope
`beta` (margin points per unit of share difference): 6.6, 6.5, 5.9, 5.8, 5.7, 5.4, 4.7, 4.7, 4.6, 4.4,
4.5 for 2015 to 2025 (`chosen_by_season` in the report).

### Warm-up 2010 to 2014 (second look; not independent)
| Comparison | Log loss (all) | 95% CI | Log loss (early) | 95% CI |
|---|---|---|---|---|
| Live Elo, pooled | 0.567203 | | 0.573142 | |
| Blend minus live | -0.005582 | [-0.010968, -0.000976] | -0.007225 | [-0.017200, +0.001402] |
| Blend + roster minus live | -0.007509 | [-0.013758, +0.000324] | -0.010738 | [-0.021766, +0.002319] |

Margin MAE on the warm-up is unchanged within noise (all rounds: blend -0.019242, CI [-0.094118, +0.055502]).

## Reading the results
- **Walk-forward weight:** choosing `w` from the past keeps the point gains of the earlier fixed-weight
  version. Pooled log loss is -0.001465 (CI [-0.003423, +0.000603]), so the log-loss gain is still not
  significant. The margin-error gain is still significant (-0.035 points, CI excludes zero).
- **Roster term: no gain.** Against the walk-forward blend, the roster term changes pooled log loss by
  -0.000072 (CI spans zero) and early-round log loss by -0.000184 (CI spans zero). Its early-round margin
  error is slightly worse (+0.016 points, CI spans zero). On the warm-up it lowers log loss in point
  estimate, but that window chose the ridge hyperparameters and its CI spans zero too.
- **Early rounds:** the candidate's early-round point gains are smaller than the pooled gains
  (log loss -0.000456, CI spans zero). The early-round margin-error point estimate is -0.043, CI spans
  zero. Early rounds are where Elo is weakest, but this candidate does not fix that in a way the data can
  distinguish from noise.
- **Verdict:** the blend is better than live on margin error (significant, all rounds) and better in point
  estimate on log loss, Brier and accuracy. Log loss is not significant. The roster term is not
  supported. Nothing here is a reason to change the live model. Any use would need a pre-registered rule
  and a live paired comparison, as in `docs/models/elo_roster_prior.md` and `docs/models/elo_calibrated.md`.

## Tried and rejected (earlier exploration, same folds, fixed settings)
Exploratory runs, not committed as scripts; numbers rounded. The live Elo log loss in those runs is 0.6104.

| Idea | Pooled log loss | Margin MAE | Outcome |
|---|---|---|---|
| Platt recalibration of Elo `d` (fit on prior seasons) | 0.6126 | 9.300 | Worse. Same family as the ELOC protocol |
| Logistic on `d` + rest difference + back-to-back | 0.6140 | 9.300 | Worse. Rest carries no signal on these folds |
| Logistic on `d` + rest difference | 0.6129 | 9.300 | Worse |
| Margin OLS on `d` (Normal link) | 0.6099 | 9.315 | Same as live within noise |
| Margin OLS on `d` + rest + back-to-back | 0.6108 | 9.338 | Worse on both |
| Walk-forward Elo parameter choice (120-point grid on prior seasons) | 0.6131 | 9.288 | Worse log loss; MAE slightly better |
| Ridge margin alone, Normal link | 0.6125 | 9.282 | Worse log loss; MAE better |
| Fixed blend weight 0.5, one sigma for all folds (exploratory) | 0.6088 | 9.266 | Superseded by the walk-forward weight |
| Fixed blend weight 0.25 / 0.75 (exploratory) | 0.6099 / 0.6090 | 9.259 / 9.299 | Not chosen |

Not tried here: a full ELOR roster prior built from the M3 player ratings (the protocol is not run).

## Limitations
- 11 scored seasons (3,299 games). Season-cluster CIs on log loss are wide relative to the gain.
- The ridge hyperparameters came from the warm-up seasons, not the scored folds. Every other choice is
  walk-forward.
- The roster term is a margin offset with one fitted slope, not the ELOR design. Its null result says
  nothing about ELOR as specified.
- Margin error is the only points metric. Totals are not forecast.
- The live Elo baseline has the small in-sample advantage described under Protocol.

## Reproduce
    uv run eurohoops backtest --model blend

Reads `data/marts/eurohoops.duckdb`, the cached box scores and roster lists, and writes
`reports/backtest_blend.json` (scored folds and warm-up). Deterministic (fixed bootstrap seed).

## Numbers
Each value below is in `reports/backtest_blend.json`. `tests/test_model_card_blend.py` checks every row.

| Quantity | Value | Report |
|---|---|---|
| Scored games, all rounds, 2015 to 2025 | 3299 | `backtest_blend.json:folds.all.games` |
| Scored games, rounds 1 to 10 | 1000 | `backtest_blend.json:folds.early.games` |
| Live Elo log loss, all rounds | 0.610401 | `backtest_blend.json:folds.all.pooled.live_elo.log_loss` |
| Blend log loss, all rounds | 0.608936 | `backtest_blend.json:folds.all.pooled.blend.log_loss` |
| Blend + roster log loss, all rounds | 0.608864 | `backtest_blend.json:folds.all.pooled.blend_roster.log_loss` |
| Live Elo Brier, all rounds | 0.211438 | `backtest_blend.json:folds.all.pooled.live_elo.brier` |
| Blend Brier, all rounds | 0.210896 | `backtest_blend.json:folds.all.pooled.blend.brier` |
| Live Elo accuracy, all rounds | 0.663231 | `backtest_blend.json:folds.all.pooled.live_elo.accuracy` |
| Blend + roster accuracy, all rounds | 0.666566 | `backtest_blend.json:folds.all.pooled.blend_roster.accuracy` |
| Live Elo margin MAE, all rounds | 9.300409 | `backtest_blend.json:folds.all.pooled.live_elo.margin_mae` |
| Blend margin MAE, all rounds | 9.265360 | `backtest_blend.json:folds.all.pooled.blend.margin_mae` |
| B0 log loss, all rounds | 0.660740 | `backtest_blend.json:folds.all.pooled.b0.log_loss` |
| Blend minus live, log loss | -0.001465 | `backtest_blend.json:folds.all.paired.blend_minus_live.log_loss.mean` |
| Blend minus live, log loss, CI low | -0.003423 | `backtest_blend.json:folds.all.paired.blend_minus_live.log_loss.ci95.0` |
| Blend minus live, log loss, CI high | 0.000603 | `backtest_blend.json:folds.all.paired.blend_minus_live.log_loss.ci95.1` |
| Blend minus live, margin MAE | -0.035049 | `backtest_blend.json:folds.all.paired.blend_minus_live.margin_mae.mean` |
| Blend minus live, margin MAE, CI low | -0.046304 | `backtest_blend.json:folds.all.paired.blend_minus_live.margin_mae.ci95.0` |
| Blend minus live, margin MAE, CI high | -0.024696 | `backtest_blend.json:folds.all.paired.blend_minus_live.margin_mae.ci95.1` |
| Blend + roster minus blend, log loss | -0.000072 | `backtest_blend.json:folds.all.paired.blend_roster_minus_blend.log_loss.mean` |
| Blend + roster minus blend, log loss, CI low | -0.001237 | `backtest_blend.json:folds.all.paired.blend_roster_minus_blend.log_loss.ci95.0` |
| Blend + roster minus blend, log loss, CI high | 0.001052 | `backtest_blend.json:folds.all.paired.blend_roster_minus_blend.log_loss.ci95.1` |
| Live Elo log loss, rounds 1 to 10 | 0.629069 | `backtest_blend.json:folds.early.pooled.live_elo.log_loss` |
| Blend log loss, rounds 1 to 10 | 0.628613 | `backtest_blend.json:folds.early.pooled.blend.log_loss` |
| Blend + roster log loss, rounds 1 to 10 | 0.628429 | `backtest_blend.json:folds.early.pooled.blend_roster.log_loss` |
| Live Elo margin MAE, rounds 1 to 10 | 9.567206 | `backtest_blend.json:folds.early.pooled.live_elo.margin_mae` |
| Blend margin MAE, rounds 1 to 10 | 9.524454 | `backtest_blend.json:folds.early.pooled.blend.margin_mae` |
| Blend + roster margin MAE, rounds 1 to 10 | 9.540041 | `backtest_blend.json:folds.early.pooled.blend_roster.margin_mae` |
| Blend + roster minus live, log loss, rounds 1 to 10 | -0.000640 | `backtest_blend.json:folds.early.paired.blend_roster_minus_live.log_loss.mean` |
| Blend + roster minus blend, log loss, rounds 1 to 10 | -0.000184 | `backtest_blend.json:folds.early.paired.blend_roster_minus_blend.log_loss.mean` |
| Warm-up live Elo log loss, all rounds | 0.567203 | `backtest_blend.json:warmup.all.pooled.live_elo.log_loss` |
| Warm-up blend minus live, log loss | -0.005582 | `backtest_blend.json:warmup.all.paired.blend_minus_live.log_loss.mean` |
