# Models audit (Phase D, written 2026-10-11)

Spec: `docs/SITE_FEEDBACK.md`, "Phase D: models audit". Read-only analysis: nothing here changes a
model, a log or a report. The owner decides the recommendation at the end.

Conventions. "Source" is a file and key in `reports/` unless it names a card in `docs/models/`.
Live numbers are the ones already published in `reports/live_scorecard.json` (EuroLeague) and
`reports/live_scorecard_gbl.json` (GBL), as committed at `d227f9d`. They are quoted descriptively.
No paired comparison of M5 against Elo on live games was computed for this audit: that belongs to
the two pre-registered R1 looks (EuroLeague round 19 and season end), and an extra look would
break the pre-registration.

## 1. Where each model runs

| Model | Job | Live? | Logged? | On the site? |
|---|---|---|---|---|
| Elo | Win probability, margin | Yes, daily (`eurohoops predict`, both competitions) | `predictions/euroleague_2026-27.csv` (43 rows), `predictions/gbl_2026-27.csv` (14 rows) | Yes: the published forecast (Forecasts page leads with it) |
| M1 | Team model: win prob, margin, total | Yes, daily, both competitions | `predictions/euroleague_m1_2026-27.csv` (30 rows), `predictions/gbl_m1_2026-27.csv` (14 rows) | Forecasts page, "Other models" table, on shared games |
| M5 | Roster-aware game model | Yes, EuroLeague only, since round 4 (`0.2.0+m5.d4848a7e`, `docs/models/m5.md`) | `predictions/euroleague_m5_2026-27.csv` (10 rows) | "Other models" table (the Methodology list also names it); no GBL M5 (not gated) |
| M6 | Player projections, over/under board | Projections refresh daily (`project --projections-only`) but change only at the 25/50/75% checkpoints | Not a prediction log: `reports/m6_projections.json` | Player pages (projected season-end PPG etc.). The Scouting page is hidden (`web/src/pages/_scouting`) |
| M7 | Season simulator | Yes, EuroLeague only, once per completed round (`simulate`, gate v2 passed 2026-10-09) | `predictions/euroleague_sim_2026-27.csv` (40 rows = 20 teams x 2 rounds). The GBL has no log | Standings page (EuroLeague labelled gated, GBL "not gated") |

Sources for the table: `.github/workflows/daily.yml` (steps Predict, Score, Project players (M6),
Season simulation log (M7), Standings season simulation); `docs/PLAN.md` §8.1 status block;
`docs/models/m5.md` "Limitations" (live status); `docs/models/m7.md` "Live";
`web/src/components/ForecastRecord.astro` ("Other models"); `web/src/components/MethodologyModels.astro`.

Inputs and research models (not logged, not shown as forecasts):
- **M2** (shot quality, xPTS): behind the shot maps and shot-making ratings. Its gate **failed** on
  calibration although it beats the spline baseline (`docs/models/m2.md`: validation log loss
  -0.002019, CI [-0.002910, -0.001255], ECE 0.0104 against the 0.01 target; test -0.002119).
- **M3** (RAPM with box prior): player ratings; the engine inside M5. Passed on RMSE by a narrow
  margin (-0.271470, CI [-0.560519, -0.001924], `docs/models/m3.md`), and its validation edge did not
  carry to test (cited in `docs/models/m5.md`).
- **M4** (GBL to EuroLeague translation): **failed** its gate (-0.137504, CI [-0.429934, 0.018067],
  `docs/models/m4.md`). It enters only the GBL "undervalued" list.

## 2. Backtest numbers

Splits differ per model, so rows are not interchangeable. Log loss, lower is better.

### Elo (EuroLeague), `reports/backtest_elo.json`
- Tuned k 20, hca 90, reversion 0.25 (`tuned.*`); the best reversion sits on the grid edge
  (`grid.best_on_edge`). Tuning 2024 (330 games), test 2025 (402 games), warm-up 2023.
- Tuning log loss 0.618331 (`metrics.tuning.elo.log_loss`); test 0.629327 (`metrics.test.elo.log_loss`),
  Brier 0.219998, accuracy 0.641791.
- Against the home-win-rate baseline B0 on test: -0.026346, 95% CI [-0.04878, -0.004545]
  (`test_log_loss_diff_elo_minus_b0`). Elo is a real, if modest, improvement on B0.
- GBL Elo: `reports/backtest_elo_gbl.json` (same method; the GBL comparison Elo inside
  `backtest_m1_gbl.json` is re-tuned on M1's tuning seasons).

### M1 (team model), `reports/backtest_m1.json`, `reports/backtest_m1_gbl.json`
Post-hoc v2: its validation and test numbers are not a clean hold-out (`docs/models/m1.md`,
"Versions"). Comparison Elo is re-tuned on the same seasons.
- EuroLeague validation 2023 (331 games): M1 0.587714 vs Elo 0.588509 (`metrics.validation.*.log_loss`),
  difference -0.000796, 95% CI [-0.007725, 0.007076] (`gate.log_loss_m1_minus_elo`). Pass on the rule,
  not significant.
- EuroLeague test 2024-25 and 2025-26 (732 games): M1 0.623218 vs Elo 0.624554
  (`metrics.test.*.log_loss`), difference -0.001336, CI [-0.007238, 0.005207]
  (`test_vs_elo.log_loss_m1_minus_elo`). A tie. Totals are the real gain: totals CRPS difference
  -0.859228, CI [-1.156218, -0.587002] (`test_vs_elo.totals_crps_m1_minus_elo`).
- GBL validation (163 games): M1 0.429759 vs Elo 0.436247, difference -0.006488, CI
  [-0.036953, 0.020842] (`backtest_m1_gbl.json:gate`). GBL test (340 games): M1 0.48355 vs Elo
  0.479879, difference +0.00367, CI [-0.026151, 0.032969] (`test_vs_elo`): M1 is a little worse
  than Elo on log loss, within noise; its totals CRPS is better, -0.47857, CI [-0.862185, -0.096885].

### M5 (roster-aware), `reports/backtest_m5.json`, `reports/backtest_m5_gbl.json`
Chosen `proj_hc | core`, residual half-life 180 days, ridge 40, totals M1 + rest
(`chosen.key`, `chosen.choice`); 414 candidates (`grid.size`) scored on 2,236 tuning games.
- Tuning: M5 0.599344 (`chosen.tuning_log_loss`) vs M1 0.60602 vs Elo 0.609009
  (`metrics.tuning.*.log_loss`). Selected on the same games it is scored on, so optimistic.
- Validation 2023 (331 games): M5 0.583765 vs M1 0.587714 (`gate.*`), difference -0.003948,
  CI [-0.014946, 0.006291]; versus Elo, difference -0.004744, CI [-0.019088, 0.008299]
  (`comparisons.validation.m5_minus_elo.log_loss_m5_minus_elo`). Gate pass, not significant.
- Test 2024-25 and 2025-26 (732 games): M5 0.623203 vs M1 0.623218 (`metrics.test.*.log_loss`),
  difference -0.000015, CI [-0.009546, 0.009753]; versus Elo, difference -0.001351, CI
  [-0.011383, 0.008787] (`comparisons.test.m5_minus_elo.log_loss_m5_minus_elo`). A tie with both.
  The validation edge did not carry over.
- What does carry: totals. M5 totals CRPS vs Elo -0.914002 on test, CI [-1.220227, -0.576823]
  (`comparisons.test.m5_minus_elo.totals_crps_m5_minus_elo`); this is M1's total plus a rest term.
  It is M1's totals model rather than the roster part.
- Value of availability information: oracle (actual) minutes give log loss 0.620074 on test vs
  M5's 0.623203 (`oracle.test.log_loss`), a small gain on average. In the 31 test games where a
  top-3 minute-taker was missing, the margin RMSE gap, projected minus oracle, is 0.843347, CI
  [0.08003, 1.648136] (`gap.test.missed_top3.rmse_projected_minus_oracle`). That is the upper bound
  of what an availability feed can buy on this evidence: real but concentrated in few games.
- Rest features: no stable effect (`reports/m5_rest.json`).
- GBL, reported not gated (`backtest_m5_gbl.json`): validation M5 0.474807 vs M1 0.429759, CI of
  the difference [0.010791, 0.083421] (worse, excludes 0); test M5 0.478959 vs M1 0.48355.

### M6 (player projections), `docs/models/m6.md` "Results" (`reports/backtest_m6.json`)
Different task (player rates, a standardised squared-error loss), so not comparable with game log loss.
- Validation 2023-24: `proj_shrunk@1` 5.398130 vs `marcel` 5.418873, lead -0.020743, player-cluster
  95% CI [-0.166008, 0.139934] (a tie), versus `same_as_last` -3.114691 [-4.066925, -2.178728]. Gate pass.
- Test (scored once): 5.901776 vs `marcel` 6.058210, lead -0.156434, CI [-0.289809, -0.032009].
  Coverage of the 80% intervals 0.794040 to 0.843120 pooled (inside the 75-85% band).
- Over/under board: rule v2 leaves no "likely real" player on the 2025-26 board (PLAN §8.1 R7).
  On/off stability is 0.0431 (`docs/models/m6.md` "Live").
- GBL: ties `marcel`, worse on validation (6.314935 vs 5.951288).

### M7 (season simulator), `docs/models/m7.md` (`reports/backtest_m7.json`, `backtest_m7_v2.json`)
- v1 gate failed on one validation season (Brier difference to `point_sim` +0.003675, CI
  [-0.003868, +0.010623], 54 team-checkpoints).
- Gate v2 (rolling origin 2016-2025, 372 team-checkpoints): **PASS**. Pooled Brier `sim_full` minus
  `point_sim` -0.000139, season-cluster CI [-0.003839, 0.003782], below the +0.005 margin; pooled
  Brier 0.111728 vs `standings_now` 0.182796; Spiegelhalter z -0.679161. It is calibrated and far
  better than the current table, and indistinguishable from the simpler `point_sim`.
- Built wholly on M1's ratings, so it inherits M1.

## 3. Live 2026-27 so far (descriptive; scorecards as committed)

EuroLeague, `reports/live_scorecard.json`; "all models on the shared games" is not available, each
model is scored on the games it logged before tip-off.

| Quantity | Value | Source key |
|---|---|---|
| Elo, games | 38 | `elo.n` |
| Elo log loss / Brier | 0.630038 / 0.221118 | `elo.log_loss`, `elo.brier` |
| B0 (home-win rate) log loss | 0.672396 | `b0.log_loss` |
| M1, games | 30 | `m1.m1.n` |
| M1 log loss / Brier | 0.646273 / 0.230235 | `m1.m1.log_loss`, `m1.m1.brier` |
| Elo on those 30 games | 0.656869 | `m1.same_games_as_elo.elo_log_loss` |
| M5, games | 10 | `m5.m5.n` |
| M5 log loss / Brier | 0.737842 / 0.272718 | `m5.m5.log_loss`, `m5.m5.brier` |
| Elo on those 10 games | 0.732085 | `m5.same_games_as_elo.elo_log_loss` |
| Bookmaker (de-vigged odds), games | 19 | `market.n` |
| Bookmaker / Elo / B0 on those 19 | 0.592663 / 0.554026 / 0.572405 | `market.log_loss`, `market.elo_log_loss`, `market.b0_log_loss` |

GBL, `reports/live_scorecard_gbl.json`: Elo 0.392408 (Brier 0.12194) and M1 0.383867 (Brier
0.121765) on the same 14 games (`elo.*`, `m1.m1.*`, `m1.same_games_as_elo`).

M7: 40 team rows logged (`predictions/euroleague_sim_2026-27.csv`); it is scored against the final
table, so there is no live score before the season ends. M6: no live game score; its first
checkpoint is at 25% of the rounds.

Reading. With 10 to 38 games per model, nothing here can separate the models: one result moves
log loss by a few hundredths (the bookmaker's own 0.592663 on 19 games is worse than Elo's
0.554026 on the same games, which says how noisy the sample is). One descriptive remark only: M5's
10 games (it started at round 4) score 0.737842 against Elo's 0.732085 on the same games, and the
whole of that is a handful of results. The pre-registered looks are the judge.

## 4. Findings

1. **No game model has a demonstrated edge over Elo.** Every M1 and M5 comparison with Elo has a
   95% CI that includes 0, on validation and on test, in both competitions. The honest summary is
   a three-way tie in win probability. The differences that are clear are in **totals** (M1,
   M5) and in M7 and M6's comparisons with weak baselines.
2. **M5 is M3 plus M1 plus a residual.** Its win-probability value equals M1's on test
   (-0.000015). Its extra, the roster part, is the part that could improve with real
   availability information (§2 oracle gap).
3. **The injury recorder cannot be backtested.** `injuries/euroleague_2026-27.csv` holds one
   snapshot (2026-10-07T09:30:32Z, 104 rows); the history does not exist. `odds/` is also
   forward-only (from 2026-09-25).
4. **GBL**: M1 is the only workable model (M5 fails; M4 fails; M6 ties its baseline). 14 live
   games say nothing yet.
5. M6 and M7 are not competitors of the game models: they are sound, gated, and cheap to run.
6. Caveats on every number above: M1 v2 is post-hoc; M5's tuning rows are selected on the data
   scored; the used test seasons (2024-25, 2025-26) are spent for any further tuning.

## 5. Recommendation (owner decides)

**(a) Retune M5**, as the EuroLeague flagship candidate, under the protocol declared in
`docs/models/m5.md` ("Retune protocol v1", declared 2026-10-11). Reasons:
- It is the only model with a structural place for new information (projected minutes ->
  availability), and the §2 oracle gap bounds that upside as real but small and concentrated.
- It already carries M1's totals and M3's ratings, so one retune covers the whole stack.
- Elo stays published until R1, so a retune costs nothing visible. The retuned version logs as a
  shadow `model_version` beside the live M5 and never touches the R1 count (owner, 2026-10-11).
- Expectation to set with the owner: a tune of the same inputs is unlikely to move log loss by
  more than the noise (about 0.005 to 0.01 on a season-level CI). The case rests on new
  information, and on the injury recorder only after enough live games exist.

The GBL flagship stays M1 unchanged (nothing to tune; 14 live games).

**(b) Retire**: no model has to be retired now.
- Nothing logging is harmful or redundant for R1. M1 EuroLeague is the comparison for the M5 card
  and supplies M5's totals, so its log is cheap and useful.
- Candidate for later, the owner's call: stop the **EuroLeague M1 log** after the R1 season-end
  look if M5's retuned shadow supersedes it (M1's calculation stays inside M5). Past rows stay.
- Not logging already and not worth reviving: M2 (calibration gate failed), M4 (gate failed).
  Scouting, the only consumer of the M6 board, is hidden; see PLAN "Later / to think about" for
  the R7 v3 decision (dropped).

## 6. Open questions for the owner

1. Is "retune M5" confirmed, and does it include the roster-turnover feature (new code) or only
   the existing inputs?
2. Is nine folds (2015 to 2023, §"Retune protocol", `docs/models/m5.md`) acceptable given that M3's
   ratings need 2011 to 2014 as warm-up?
3. Should the odds benchmark go into the model as an input (only forward data, so shadow-only), or
   stay a benchmark?
4. Retire the EuroLeague M1 log after R1, or keep both until the end of 2027-28?
