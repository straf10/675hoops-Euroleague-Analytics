# eurocup
Idea:      Add EuroCup (API code U, seasons 2007-08 to 2025-26 finished) as research-only data and test whether Elo ranks above B0 on it; M1 and M5 are deferred (see Scope).
Type:      diagnostic
Baseline:  B0 (constant home-win rate and home margin; neutral-venue games 0.5 and 0), the comparator in every Elo backtest
Backtest:  walk-forward Elo replay on EuroCup games from the 2007 warm-up. Settings (Elo k, hca, reversion, margin scale, B0 rates) are fitted on tuning seasons 2015-16..2022-23 only. Scored test seasons 2023-24..2025-26 (finished, played games; 2026-27 is partial and not scored). Warm-up 2007-08..2014-15 is replayed, never scored.
Live:      no
Metric:    log loss on home win (default). Per-game gap g = log loss(Elo) - log loss(B0) over the shared test games.
Pass bar:  Elo ranks above B0 only if mean(g) <= -0.01 AND the upper bound of the paired bootstrap CI of g (eval/promotion.py bootstrap_ci, 10,000 resamples, seed 20261009) is < 0. B0 ranks above Elo only if mean(g) >= +0.01 AND the lower bound of that CI is > 0. Otherwise: no ranking. Tuning-season numbers are descriptive only.
Scope:     M1 and M5 are NOT run here. Their backtests read EuroLeague-only inputs (E{season} box-score and play-by-play cache paths, the EuroLeague stints mart, and player ratings from the EuroLeague-fitted M3). Extending them is an owner decision (see the report).
           Step 5 (Elo carry-over between EuroCup and EuroLeague) is out of scope.
           EuroCup is research only: no live log, no site change, no daily workflow change.
Result:    pass for Elo over B0 (diagnostic verdict: "elo ranks above b0"). Test 2023-26, n = 586 shared games: mean gap (Elo - B0) -0.0689, 97.5% CI -0.1032..-0.0336, log loss Elo 0.6180, B0 0.6869. Tuning 2015-22 (descriptive, n = 1557): gap -0.0586. M1 and M5 not run (owner decision). Details: docs/models/diag_eurocup.md.
