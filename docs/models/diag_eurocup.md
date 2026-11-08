# EuroCup diagnostic: Elo against B0

Research only. Nothing here goes live, reaches the site or changes the daily workflow.
Spec: `experiments/eurocup.md`. Script: `scripts/diag_eurocup.py`. Report: `reports/diag_eurocup.json`.

## Question
Does Elo forecast EuroCup home wins better than B0 (a constant home-win rate and home margin)?
This is the first step toward ranking the model types on more games.

## Data
- API competition code `U`. Schedules for 2007-08 to 2026-27 are cached in `data/raw/eurocup/schedule/`.
  Twenty seasons exist. Nineteen are finished. 2026-27 is partial (96 of 224 games played on 2026-11-08) and is not scored.
- The API schedules hold 4,161 games. Seven played games are left out. Each has equal final scores and a named winner, so the real score is unknown:
  2007-08 (3 games), 2010-11 (1), 2014-15 (1), 2015-16 (2). The staged table holds 4,154 games, of which 4,008 are played.
- One played game is a 20-0 score (U2008_72). It is flagged as a forfeit and is not rated.
- Knockout phase codes (`L32`, `L16`, `8F`, `4F`, `2F`, `Final`) are read as `PO`. Phases in the mart: RS 3,034, TS 240, PO 880 (all rows, played or not).
- Box scores and play-by-play: 2 played games per finished season were fetched (38 games). All 38 box scores hold a Stats block. All 38 play-by-play files hold play-type rows. Full coverage was not fetched (see Not done).
- Team codes: 164 EuroCup codes, 66 EuroLeague codes, 54 in both. The `continuity` check flags three EuroCup code name changes: `RED` (Red Star to Crvena Zvezda, 2008), `GRO` (Hanzevast Capitals to GasTerra Flames, 2010) and `DYR`. `DYR` is one continuous club: a rename and relocation in 2014, from BC Triumph Lyubertsy to Zenit Saint Petersburg (earlier BC Dynamo Moscow Region). It is kept as one team with no code split and no rating reset, the same treatment as `RED` and `GRO`.

## Method
- Warm-up 2007-08 to 2014-15 (replayed, never scored). Tuning 2015-16 to 2022-23. Test 2023-24 to 2025-26.
- Elo (k, home-court advantage, reversion, margin scale) and the B0 rates are fitted on the tuning seasons only (`run_backtest`). Test seasons are only scored.
- Per-game gap: log loss under Elo minus log loss under B0, on the same games.
- Pass bar: Elo ranks above B0 when the mean test gap is at most -0.01 and the upper bound of the 97.5% paired bootstrap CI is below 0 (`eval/promotion.py`, 10,000 resamples).

## Result
Tuned Elo: k 40, home-court advantage 90, reversion 0.25, margin scale 24.75. B0: home-win rate 0.620, home margin 3.91.

| Split | Games | Elo log loss | B0 log loss | Mean gap (Elo - B0) | 97.5% CI of gap |
|---|---|---|---|---|---|
| Tuning 2015-16..2022-23 (descriptive) | 1,557 | 0.6103 | 0.6689 | -0.0586 | -0.0756 to -0.0414 |
| Test 2023-24..2025-26 (scored) | 586 | 0.6180 | 0.6869 | -0.0689 | -0.1032 to -0.0336 |

Test games per season: 195, 196, 195.

Verdict on the test seasons: **Elo ranks above B0.** Both conditions of the pass bar hold.

## Caveats
- k = 40 is the top value of the pre-registered grid (15, 20, 30, 40). The grid was not widened.
- The EuroLeague Elo log loss (0.609, 2015-16 to 2025-26, `docs/models/diag_residuals.md`) and this EuroCup figure (0.62) are different competitions. They do not rank each other.
- Seasons 2019-20 and 2020-21 (COVID-19) fall in the tuning seasons. Their effect was not checked.

## Not done
- **M1 and M5 were not run on EuroCup.** Their backtests read EuroLeague-only inputs: `E{season}` cache paths in the box-score, play-by-play and stints parsers; the stints mart (built from EuroLeague only); rosters from the EuroLeague people listing; and player ratings from M3, fitted on EuroLeague. Extending them is an owner decision.
- Full box-score and play-by-play fetch for EuroCup: about 7,800 requests (3,912 finished games, two endpoints) at the one-request-per-second limit, about 2.2 hours.
- M5 (vs Elo and vs M1): not scored: deferred by owner decision 2026-11-08 (needs EuroCup M3 port).
- Step 5 (rating carry-over between EuroCup and EuroLeague) was out of scope.

## M1 (spec addendum, owner decision: run M1, defer M5)
Walk-forward M1 on EuroCup (`eval/m1_backtest.py`). Warm-up 2011-12..2014-15 (box scores start 2011-12 in this fetch), tuning 2015-16..2022-23, test 2023-24..2025-26. No validation gate. Comparison Elo is re-fitted on the tuning seasons. Gaps use the 586 test games with team box lines, the same games for all models.

| Model | Mean log loss (586 games) |
|---|---|
| M1 (student_t_const) | 0.6062 |
| Elo | 0.6180 |
| B0 | 0.6858 |

- M1 vs Elo: mean gap -0.0118, 97.5% CI -0.0257 to +0.0018. **No ranking**: the mean clears the -0.01 bar but the CI reaches 0.
- M1 vs B0: mean gap -0.0797, 97.5% CI -0.1144 to -0.0437. **M1 ranks above B0.**
- M5 vs Elo and M5 vs M1: not scored, deferred by owner decision 2026-11-08 (needs an EuroCup M3 port).

Box-score coverage used by M1 (cached vs played, 2011-2025): 100% in every season except 2012 (156/157) and 2013 (364/366). Missing team lines for M1 (all seasons 2007-2026 in the report): 3 games with no cached box score (U2012_146, U2013_14, U2013_263); 8 games where the box points do not equal the schedule result or the box is empty (2013: four, 2014: one, 2016: three, 2022: one; the same rule as the EuroLeague validator); 1 box score with no players (U2015_13, API placeholder). None of these fall in the scored test seasons.

Staging note: running the box-and-PBP-only fetch with a season subset overwrote the EuroCup staged schedule with those seasons only. This was a bug in the new fetch-only path. It is fixed: the mode now returns before any staging write. It is covered by a test. The staging was restored from cache (4,154 games, 2007-2026).

