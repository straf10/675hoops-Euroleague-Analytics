# Diagnostic: do pre-game features the models do not use explain their errors?

Status: diagnostic (no change made; nothing goes live; Elo and M5 keep their live settings).

## What it is
**Question:** the live models (Elo, M5) use only some of the pre-game information. Take each model's out-of-sample per-game forecasts, compute the residuals, and test whether any pre-game feature the model does not use explains them. Also check calibration by season and by home team.

**Method.**
- Data: the EuroLeague games mart (ratings replayed from 2007, so they are warm). Scored games: 2015 to 2025, non-neutral, played, not forfeit. That is 3,260 games; both models are scored on the same games.
- **Elo:** live parameters (k 20, hca 90, reversion 0.25) through the existing `replay`. Expected margin = pre-game rating difference / 24.53358 (the margin scale in `reports/backtest_elo.json`, `tuned.margin_scale`).
- **M5:** the live variant `proj_hc|core|d180|r40` from `reports/backtest_m5_games.csv`, all splits. Its actual margins match the mart on all 3,260 scored games. Split counts (all rows, then scored): tuning 2,236 / 2,208; validation 331 / 327; test 732 / 725.
- **Features** (each read only from games before the game, or from whole earlier seasons). Rest, short-rest flags and games in the last 7 days come from `models/rest.py rest_features`. The rest of the list is in `eval/residuals.py pregame_features`:
  - home rest, away rest, rest difference (days, capped at 7);
  - home and away short rest (at most 2.5 days);
  - home and away games in the last 7 days;
  - round number; playoff flag (phase not regular season);
  - month of season (October = 0 ... June = 8);
  - confidence, |p_model − 0.5| (per model);
  - prior-season home edge: the home team's home-win rate in the previous season minus the league's that season (NaN where the mart has no non-neutral home game for that team the season before: 439 of 3,260 games, of which PAM, UNK, KHI and DAR account for 160);
  - Elo pre-game difference (M5 only).
  - Not tested: other-competition rest (always false in the mart), travel or country (the mart has no country field).
- **Encompassing test (primary):** logistic regression of home win on offset logit(p_model) (coefficient fixed at 1) and one standardized feature. A coefficient of zero means the feature adds nothing. Wald test.
- **Margin test (reported, not used for the flag):** OLS of (actual margin − expected margin) on the standardized feature.
- **Holm** across the model's features, within each test.
- **Pass bar** (spec `experiments/residuals.md`): "candidate evidence" only when the pooled Holm p is below 0.05 and the pooled sign holds in at least 2/3 of the seasons that have the feature. Otherwise "no evidence". The 2019 season has no playoff rows, so `is_playoff` has 10 seasons; every other feature has 11.
- **Reliability (descriptive, no flag):** per season, per home team (teams with at least 40 home games), and the pooled bins. Bins are the five equal-width bins of predicted P(home win), with Wilson 95% intervals.
- **Binned residuals:** per feature, 10 quantile bins (one bin per value for features with at most 10 distinct values).
- **Live 2026 (descriptive):** the published forecasts for 2026 through `eval/forecasts.build_forecasts`, per model.

**Limits on the scored set.** The live Elo parameters were chosen on the 2024 tuning season (2023 as warm-up); the M5 settings on 2015 to 2022 with 2023 as validation. The scored seasons therefore include the seasons used to choose those settings, so the residuals are slightly optimistic for them. The feature tests do not refit any model.

## Results

**Pooled calibration, scored 2015 to 2025 (3,260 games; home-win rate 0.6276 in both).**

| Model | Mean p_home | Gap (mean p − actual) | Log loss |
|---|---:|---:|---:|
| Elo | 0.6166 | −0.0110 | 0.609433 |
| M5 | 0.6190 | −0.0086 | 0.602072 |

**Section 1: encompassing tests, Elo** (coefficient on the standardized feature, logit units; p_holm across 12 features)

| Feature | Coef | 95% CI | p | p_holm | Same-sign seasons | Margin p_holm | n | Flag |
|---|---:|---|---:|---:|---:|---:|---:|---|
| home_rest | +0.0134 | [−0.0606, +0.0873] | 0.7234 | 1.0000 | 5/11 | 1.0000 | 3260 | no evidence |
| away_rest | +0.0096 | [−0.0644, +0.0836] | 0.7986 | 1.0000 | 7/11 | 1.0000 | 3260 | no evidence |
| rest_diff | +0.0080 | [−0.0669, +0.0830] | 0.8336 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| home_short | −0.0210 | [−0.0947, +0.0527] | 0.5762 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| away_short | −0.0109 | [−0.0847, +0.0628] | 0.7715 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| home_last7 | −0.0266 | [−0.1008, +0.0476] | 0.4822 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| away_last7 | +0.0196 | [−0.0544, +0.0937] | 0.6030 | 1.0000 | 5/11 | 1.0000 | 3260 | no evidence |
| round | +0.0156 | [−0.0584, +0.0896] | 0.6794 | 1.0000 | 5/11 | 1.0000 | 3260 | no evidence |
| is_playoff | +0.0289 | [−0.0459, +0.1037] | 0.4496 | 1.0000 | 4/10 | 1.0000 | 3260 | no evidence |
| month_of_season | +0.0330 | [−0.0410, +0.1070] | 0.3825 | 1.0000 | 7/11 | 1.0000 | 3260 | no evidence |
| confidence | +0.0574 | [−0.0237, +0.1385] | 0.1653 | 1.0000 | 7/11 | 1.0000 | 3260 | no evidence |
| prior_home_edge | +0.0421 | [−0.0387, +0.1228] | 0.3075 | 1.0000 | 7/11 | 1.0000 | 2821 | no evidence |

**Section 2: encompassing tests, M5** (same layout; 13 features, the 13th is the Elo difference)

| Feature | Coef | 95% CI | p | p_holm | Same-sign seasons | Margin p_holm | n | Flag |
|---|---:|---|---:|---:|---:|---:|---:|---|
| home_rest | +0.0112 | [−0.0641, +0.0865] | 0.7701 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| away_rest | +0.0080 | [−0.0674, +0.0833] | 0.8354 | 1.0000 | 7/11 | 1.0000 | 3260 | no evidence |
| rest_diff | +0.0070 | [−0.0692, +0.0832] | 0.8579 | 1.0000 | 5/11 | 1.0000 | 3260 | no evidence |
| home_short | −0.0255 | [−0.1005, +0.0494] | 0.5047 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| away_short | −0.0105 | [−0.0855, +0.0646] | 0.7844 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| home_last7 | −0.0233 | [−0.0990, +0.0523] | 0.5453 | 1.0000 | 7/11 | 1.0000 | 3260 | no evidence |
| away_last7 | +0.0174 | [−0.0581, +0.0929] | 0.6513 | 1.0000 | 5/11 | 1.0000 | 3260 | no evidence |
| round | +0.0042 | [−0.0710, +0.0795] | 0.9120 | 1.0000 | 4/11 | 1.0000 | 3260 | no evidence |
| is_playoff | +0.0178 | [−0.0579, +0.0935] | 0.6450 | 1.0000 | 4/10 | 1.0000 | 3260 | no evidence |
| month_of_season | +0.0226 | [−0.0527, +0.0979] | 0.5559 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| confidence | +0.0446 | [−0.0403, +0.1296] | 0.3032 | 1.0000 | 6/11 | 1.0000 | 3260 | no evidence |
| prior_home_edge | +0.0479 | [−0.0344, +0.1302] | 0.2537 | 1.0000 | 6/11 | 1.0000 | 2821 | no evidence |
| elo_diff | +0.0155 | [−0.0678, +0.0987] | 0.7158 | 1.0000 | 7/11 | 1.0000 | 3260 | no evidence |

No feature is flagged for either model. The smallest raw p is 0.165 (Elo, confidence); after Holm every adjusted p is 1.0. The CIs are about ±0.08 logit per standard deviation, so the design would have caught a feature with a coefficient of about 0.15 or more per standard deviation. Smaller effects cannot be ruled out.

**Section 3: reliability by season, Elo** (predicted = mean p_home; actual = home-win rate; descriptive)

| Season | Games | Predicted | Actual | Gap | Log loss |
|---|---:|---:|---:|---:|---:|
| 2015 | 246 | 0.6160 | 0.6463 | −0.0303 | 0.5898 |
| 2016 | 255 | 0.6173 | 0.6235 | −0.0063 | 0.6084 |
| 2017 | 256 | 0.6157 | 0.6367 | −0.0210 | 0.6026 |
| 2018 | 256 | 0.6182 | 0.6328 | −0.0146 | 0.5685 |
| 2019 | 252 | 0.6130 | 0.6190 | −0.0060 | 0.5876 |
| 2020 | 324 | 0.6163 | 0.5679 | +0.0484 | 0.6548 |
| 2021 | 295 | 0.6141 | 0.6542 | −0.0402 | 0.6082 |
| 2022 | 324 | 0.6165 | 0.6265 | −0.0100 | 0.6244 |
| 2023 | 327 | 0.6156 | 0.6453 | −0.0297 | 0.5874 |
| 2024 | 326 | 0.6185 | 0.6196 | −0.0011 | 0.6171 |
| 2025 | 399 | 0.6200 | 0.6366 | −0.0166 | 0.6304 |

Season gaps are negative in 10 of 11 seasons (home teams won more often than Elo expected). The 2020 gap is the only large positive one. M5's season table is in `reports/diag_residuals.json` (`models.m5.reliability.by_season`).

**Section 4: reliability by bin, pooled Elo** (Wilson 95% interval on the observed rate)

| Predicted bin | Games | Predicted | Observed | 95% interval |
|---|---:|---:|---:|---|
| 0.0 to 0.2 | 3 | 0.164 | 0.000 | [0.000, 0.561] |
| 0.2 to 0.4 | 237 | 0.340 | 0.312 | [0.257, 0.374] |
| 0.4 to 0.6 | 1,155 | 0.516 | 0.533 | [0.504, 0.562] |
| 0.6 to 0.8 | 1,575 | 0.693 | 0.697 | [0.673, 0.719] |
| 0.8 to 1.0 | 290 | 0.838 | 0.893 | [0.852, 0.924] |

The top bin is above its prediction (observed 0.893 against 0.838), and its interval excludes the prediction. The bin holds 290 games, so this is one descriptive gap, not a test.

**Section 5: reliability by home team, Elo** (teams with at least 40 home games; descriptive only)

| Home team | Games | Predicted | Actual | Gap |
|---|---:|---:|---:|---:|
| BER | 98 | 0.464 | 0.337 | +0.127 |
| DYR | 45 | 0.576 | 0.489 | +0.087 |
| DAR | 44 | 0.525 | 0.477 | +0.048 |
| ASV | 118 | 0.454 | 0.407 | +0.047 |
| KHI | 75 | 0.544 | 0.507 | +0.037 |
| VIR | 70 | 0.545 | 0.500 | +0.045 |
| ZAL | 182 | 0.570 | 0.555 | +0.015 |
| IST | 187 | 0.658 | 0.652 | +0.006 |
| MIL | 171 | 0.577 | 0.573 | +0.004 |
| PAR | 72 | 0.613 | 0.611 | +0.002 |
| RED | 161 | 0.567 | 0.565 | +0.001 |
| MCO | 100 | 0.680 | 0.700 | −0.020 |
| BAR | 192 | 0.705 | 0.729 | −0.025 |
| PAM | 102 | 0.591 | 0.618 | −0.027 |
| CSK | 110 | 0.795 | 0.827 | −0.033 |
| ULK | 189 | 0.700 | 0.741 | −0.041 |
| OLY | 189 | 0.687 | 0.735 | −0.048 |
| MAD | 197 | 0.744 | 0.802 | −0.058 |
| TEL | 173 | 0.602 | 0.647 | −0.046 |
| BAS | 183 | 0.604 | 0.667 | −0.063 |
| MUN | 140 | 0.555 | 0.614 | −0.060 |
| PAN | 191 | 0.616 | 0.675 | −0.059 |
| BAM | 42 | 0.545 | 0.595 | −0.050 |

Team gaps range from −0.063 to +0.127. A positive gap means Elo predicted more home wins than occurred (BER, DYR, ASV); a negative gap means the reverse (BAS, PAN, MUN, MAD). The 95% intervals on the observed rate are roughly ±0.08 for 100 to 200 games. The table is descriptive: a per-team flag would need a per-team test, which the pass bar does not include. M5's team table is in the JSON.

**Section 6: live 2026 (descriptive; published forecasts logged so far)**

| Model | Games | Predicted | Actual | Gap |
|---|---:|---:|---:|---:|
| Elo | 98 | 0.618 | 0.520 | +0.098 |
| M1 | 90 | 0.616 | 0.511 | +0.104 |
| M5 | 70 | 0.618 | 0.471 | +0.147 |
| M5-INJ (trial) | 33 | 0.608 | 0.485 | +0.123 |
| ELOH (trial) | 24 | 0.623 | 0.500 | +0.123 |
| Bookmakers (MKT) | 54 | 0.597 | 0.556 | +0.042 |

Each model is scored on the games it logged, so the games differ between rows. Every model predicted more home wins than occurred in 2026 so far, the bookmakers included (gap +0.042). With 54 to 98 games the standard error of an observed rate is about 0.05 to 0.07, so the Elo gap is about 2 standard errors (hand calculation, not printed by the script). The live section has no flag. Its binned margin residuals against rest difference (in the JSON) have 9 to 10 bins of 1 to 27 games each and do not support any reading.

## Reading
- **No pre-game feature the models omit explains their errors.** Every feature has a pooled Holm p of 1.0, and no feature has a sign that holds in a clear majority of seasons with a significant coefficient. Rest, short rest, schedule density, round, playoffs, month, confidence and prior home edge all look like noise to both models.
- **The test has a resolution.** Each coefficient is measured to about ±0.08 logit per standard deviation. A real effect smaller than that would not show up in 11 seasons.
- **Calibration is close overall.** Pooled predicted and actual home-win rates differ by 0.011 (Elo) and 0.009 (M5). Home teams won a little more often than predicted, consistent with the note in `docs/models/diag_home_court.md`, but this is not a flag. The per-season, per-team and per-bin gaps are descriptive.
- **2026 so far runs the other way.** Every logged model, the bookmakers included, predicted more home wins than occurred. That is a small sample, and it does not feed the pass bar.

## Conclusion
No candidate evidence for either model. Every feature has "no evidence" under the pass bar. The live Elo and M5 settings stand. Any feature worth a shadow would need a new spec and a pass bar written before it is scored.

## Files
- Spec: `experiments/residuals.md`.
- Script: `scripts/diag_residuals.py` (run: `uv run python scripts/diag_residuals.py`).
- Report: `reports/diag_residuals.json` (all numbers above, plus binned residual series for each feature).
- Code: `src/eurohoops/eval/residuals.py` (`encompassing`, `margin_residual_test`, `holm`, `reliability`, `binned_residuals`, `elo_pregame`, `pregame_features`); `src/eurohoops/models/rest.py` (`rest_features`); `src/eurohoops/models/elo.py` (`prepare`, `replay`); `src/eurohoops/eval/forecasts.py` (`build_forecasts`, `_wilson`).
- Tests: `tests/test_residuals.py` (planted and null coefficients, Holm example, reliability and binned bins, no-lookahead for the pre-game features and Elo).
