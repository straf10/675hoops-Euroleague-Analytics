# Research knowledge base: index

Built 2026-10-22 from 32 papers; the 9 off-topic ones were removed 2026-10-23, leaving 23. PDFs are in `pdfs/` and reader notes in [papers/](papers/), both local only (gitignored). The first line of each note gives its verification status. Ideas are in [IDEAS.md](IDEAS.md).

## Our models today (phase 1 summary)

**Elo** (published forecast, baseline B1).
- 538-style, with a margin-of-victory multiplier, home advantage, and 25% season-start reversion. EuroLeague k 20 / hca 90; GBL frozen at k 40 / hca 130.
- EuroLeague test 2025: log loss 0.629327 vs B0 0.655673, a gap of −0.026, CI [−0.0488, −0.0045]; ECE 0.049.
- GBL test: log loss 0.484529.
- Weaknesses: no roster or injury information. EuroLeague parameters were tuned on one season (2024), and the reversion sits on the grid edge. No totals.

**M1** (team efficiency, ridge on points per 100 possessions, Student-t margin, pace model).
- v2 passes its rule, but no gap is significant. EuroLeague test vs Elo: −0.0013 [−0.0072, 0.0052]. GBL validation −0.0065, test +0.0037.
- Totals CRPS gains are significant.
- Weaknesses:
  - It loses to Elo in rounds 1–5 (0.5947 vs 0.5784), because the carry of 0.25 on last season's rows pulls hard to the mean.
  - One home effect for all seasons.
  - No roster information.
- GBL flagship candidate.

**M5** (roster-aware: Σ projected-minute share × M3 RAPM, plus a team residual).
- EuroLeague gate passed: 0.583765 vs M1 0.587714, −0.0039 [−0.0149, 0.0063]. The test is a tie (−0.000015).
- Totals CRPS −0.914 (significant).
- Weaknesses:
  - When a top-3 minute-taker is missing (31 games), margin RMSE is +0.84 worse than with oracle minutes.
  - It failed the GBL check.
  - Rest effects are noise.
- EuroLeague flagship candidate.

**M6** (player projections, Marcel-like empirical Bayes).
- proj_shrunk@1 passed. Test vs Marcel −0.156, CI excludes 0.
- Aging and translation terms did not help.
- The board names no "likely real" player.

**M7** (season simulator drawing from M1's posterior).
- v1 failed. v2 passed: Brier −0.000139 vs point_sim, CI upper 0.0038 < 0.005. It is calibrated.
- Strengths are fixed within a simulation. GBL rules are unverified.

**Shadows:**
- ELOR (roster-prior Elo) passed its CV: −0.0023 [−0.0043, −0.0007].
- ELOC (calibrated Elo) was negative.
- POOL is an equal-weight log pool of Elo, M1, M5 and ELOR.
- A learned blend showed no gain.

## Open questions given to the readers
- **Q1.** Dynamic strength within vs between seasons; season-start reversion.
- **Q2.** Availability: adjusting for a missing key player, and how much the market prices it.
- **Q3.** Market benchmark: de-vig method, closing vs earlier lines, known biases.
- **Q4.** Combining forecasts: equal vs estimated weights, linear vs log pool, recalibration.
- **Q5.** Evaluation on small live samples: significance, randomness limits, calibration.
- **Q6.** Score distribution (Normal, Student-t, count) and team-specific home advantage.

## Topics
- [dynamic-ratings](topics/dynamic-ratings.md): within-season drift is small. Season-start reversion is 0–46% across papers (they disagree). Kalman variants give small gains over Elo at best.
- [availability-and-rosters](topics/availability-and-rosters.md): opening lines misprice absences; closing lines mostly do not. No paper measures absence effects in European basketball.
- [betting-markets](topics/betting-markets.md): proportional de-vig is standard (no method comparison exists). No favourite–longshot bias in the NBA. Early-season NBA totals run high. Models at best tie the market.
- [model-combination-and-calibration](topics/model-combination-and-calibration.md): equal weights are hard to beat on small samples. Linear pools are under-confident. Recalibration gains are uncertain.
- [evaluation](topics/evaluation.md): shared outcomes shrink the effective sample. Small gaps are noise. Leakage explains the 83–99% accuracy claims.
- [score-distributions-and-home-advantage](topics/score-distributions-and-home-advantage.md): Normal margins are adequate and Student-t gave no gain. Team home advantage is supported in-sample only.

## Papers
Sports forecasting, betting markets and forecast combination (22):
- [albert-2015](papers/albert-2015-win-probability-player-evaluation.md): review of in-game WP and WPA; Stern's Brownian-motion basketball model. Verified.
- [baryla-2007](papers/baryla-2007-nba-early-season-totals-bias.md): NBA totals lines run high early in the season; closing lines remove most of the bias. Verified.
- [brill-2024](papers/brill-2024-difficulty-win-probability.md): play-by-play WP has about 56% effective sample; naive bootstrap under-covers (60% vs 90%). Verified.
- [colquitt-2001](papers/colquitt-2001-ncaa-betting-efficiency.md): NCAA closing lines are rational; less-covered conferences have larger errors. Verified.
- [dare-2015](papers/dare-2015-player-absence-nba-lines.md): absences move NBA lines; openers misprice them, closers mostly do not. Verified.
- [duffield-2023](papers/duffield-2023-state-space-skill-rating.md): state-space skill ratings vs Elo; small test log-loss gains, no significance test. Verified.
- [glickman-1998](papers/glickman-1998-nfl-state-space.md): NFL state-space model; within-season AR 0.99, between-season 0.82; team home advantage; Student-t no gain. Verified (interval and page numbers corrected).
- [he-2025](papers/he-2025-stacked-ensemble-nba.md): stacked ensemble with 83% NBA "accuracy" from same-game box scores; a leakage example. Verified.
- [li-2025](papers/li-2025-ai-basketball-prediction-review.md): review of 34 AI basketball studies; honest ceilings about 69% (EuroLeague) and 78% (GBL). Verified.
- [lopez-2017](papers/lopez-2017-how-often-best-team-wins.md): four US leagues; season reversion 31–46%, NBA 38%; team home advantage by DIC; ties the market in the NBA. Verified.
- [macridemartino-2026](papers/macridemartino-2026-dynamic-bradley-terry.md): NBA dynamic Bradley–Terry with adaptive season-to-season jumps; small Brier gains. Verified.
- [martingonzalez-2016](papers/martingonzalez-2016-poisson-limits-nba.md): NBA scoring is near-Poisson mid-game and over-dispersed in close-game final minutes. Verified.
- [miller-2026](papers/miller-2026-mma-betting-efficiency.md): MMA favourite–longshot gap is significant but not profitable; age and travel fail out of sample. Verified.
- [ridall-2025](papers/ridall-2025-epl-bayesian-state-space.md): EPL Bayesian state-space; almost no season reversion; all models lose to bookmakers. Verified (κ inconsistency is the paper's own).
- [robbins-2022](papers/robbins-2022-sports-betting-efficiency.md): proportional de-vig; no favourite–longshot bias in the NBA or NHL; NBA hold 3.64%. Verified.
- [santosfernandez-2019](papers/santosfernandez-2019-bayesian-sports-review.md): review of 74 Bayesian sports papers; structures only, no performance numbers. Verified.
- [shimizu-2026](papers/shimizu-2026-stats-x-realtime-wp.md): Gaussian in-game WP for the B1 League; in-sample only. Verified.
- [szczecinski-2021](papers/szczecinski-2021-simplified-kalman-rating.md): simplified Kalman rating ≈ Glicko; in noisy leagues all methods are near the entropy. Verified.
- [tian-2024](papers/tian-2024-spectral-dynamic-bradley-terry.md): kernel spectral ranker matches Elo on NBA accuracy (gap inside the noise). Verified.
- [gupta-1987](papers/gupta-1987-combination-of-forecasts.md): odds-matrix weights; regression weights fail at small N; equal weights are robust when model errors are similar. Verified.
- [wang-2022](papers/wang-2022-forecast-combinations-review.md): review of forecast combination; equal weights are hard to beat; spread-adjusted pools. Verified.
- [yu-2026](papers/yu-2026-quantile-adaptive-forecast-combining.md): radial CDF averaging beats the linear pool by 2–5% on COVID forecasts. Verified (reader's mismatch flag withdrawn).

Statistics methods, marginal relevance (1):
- [zanini-2024](papers/zanini-2024-variational-bayesian-bridge.md): Bayesian bridge regression with ADVI; fast, but no predictive comparison with ridge. Verified.

## What we already do vs. what the literature suggests

| Model | Already in line with the literature | The literature suggests | Idea |
|---|---|---|---|
| Elo | 25% season reversion, inside the 18–46% range (Glickman, Lopez). Proportional de-vig benchmark. | Team-specific home advantage (Lopez, Glickman), shown in-sample only. | [D2](IDEAS.md#d2-team-specific-home-advantage-shrunk-eloh), low priority |
| M1 | Small within-season decay. Student-t margin (Normal would do, per Glickman). Totals from pace × efficiency (scoring is near-Poisson mid-game). | Separate season-start reversion from the discounting of old seasons. Carry more than a quarter of last season (Lopez 62%, Glickman 82%). | [D1](IDEAS.md#d1-season-start-state-space-prior-for-m1-m1-ss); [B2](IDEAS.md#b2-early-season-totals-check-against-the-market) for totals |
| M5 | Lineup-sum structure, as in Deshpande & Jensen. Roster-turnover term tested. | Use availability information before the absence shows in box scores. The market prices it by the close (Dare). | [A1](IDEAS.md#a1-injury-aware-minutes-for-m5-m5-inj) |
| M6 | Per-player shrinkage (persist = n/(n+k)). | Nothing new from these papers. | none |
| M7 | Calibration check, rolling origin. | Nothing new from these papers. | none |
| POOL | Equal-weight log pool, nothing tuned. This is the setting the literature favours on small samples (Wang, Gupta). | Optional spread recalibration (Wang p.29; uncertain per Baran & Lerch). Screen near-duplicate members. | [C1](IDEAS.md#c1-spread-recalibrated-pool-pool-c), [C2](IDEAS.md#c2-redundancy-screen-of-pool-members) |
| In-game WP | Brownian closed-form baseline, pre-game logit input, whole-game bootstrap, calibration by time bucket. | Already covered (Albert, Shimizu, Brill). | none |
| Evaluation | Walk-forward splits, paired bootstrap, round clustering, pre-registered gates, leakage tests. | Plan for power: small gaps cannot pass R1 on one season's games. Use the market as a benchmark forecaster. | [E1](IDEAS.md#e1-power-check-for-the-r1-promotion-looks), [B1](IDEAS.md#b1-market-as-a-logged-forecaster-plus-an-encompassing-test) |
