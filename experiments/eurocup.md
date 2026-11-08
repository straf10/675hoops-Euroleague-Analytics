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

## Addendum: M1 and M5 on EuroCup (owner decision: run them)
Written before any M1 or M5 result. The Elo-vs-B0 pass bar and Result above are unchanged.

Models: M1 (team-efficiency model, `eval/m1_backtest.py`) and M5 (`eval/m5_backtest.py`), each run on EuroCup only. Comparison Elo and B0 as above.
Seasons: tuning 2015-16..2022-23; test 2023-24..2025-26 (scored once). Warm-up for box-score models 2011-12..2014-15 (box and play-by-play before 2011-12 are not fetched, and the stints mart starts 2011-12). Elo's warm-up stays 2007-08..2014-15. M1 has no validation gate for EuroCup (empty validation split): tuning chooses the grids and the margin distribution, test is scored once.
Fetch: EuroCup Boxscore and PlaybyPlay for every finished game 2011-12..2025-26, cached under `data/raw/eurocup/{boxscore,playbyplay}/U{season}/`. The 2026-27 partial season is not fetched or scored. Points endpoint is not fetched (no model here needs it).

Player ratings (M5 player part) and rosters:
- M3's committed hyperparameters (`reports/backtest_m3.json`, `chosen`) are used as fixed settings. They are NOT re-tuned on EuroCup. This is a design choice stated here, before results.
- The ratings are fitted walk-forward on EuroCup box scores only, using only games before each forecast's round. No EuroLeague-fitted rating or EuroLeague game enters any EuroCup forecast.
- Rosters come from EuroCup box-score lineups of earlier games (players who appeared for the team in the season before the forecast round). No EuroCup people listing is fetched.

M5 scoring: M5 is scored only on test games with valid stints (stint checks pass for that game, per `stint_game_checks`). The stint coverage per season is reported. A game without valid stints is not scored by M5.

Pairwise comparisons (all with the same pass-bar form as above: mean gap <= -0.01 and 97.5% paired bootstrap CI upper < 0 via `eval/promotion.bootstrap_ci`, 10,000 resamples, seed 20261009; "X ranks above Y" when the mirror holds for the other direction; else no ranking):
1. M1 vs Elo (gap = log loss M1 - log loss Elo)
2. M5 vs Elo (gap = M5 - Elo)
3. M1 vs M5 (gap = M1 - M5)
Each gap uses only the games that both models score (shared games). For pair 2 and 3 that is the test games with valid stints.

Result: (step 7, appended below this line)
Addendum result (appended; the pass bars above are unchanged):
- M5 vs Elo: not scored: deferred by owner decision 2026-11-08 (needs EuroCup M3 port).
- M5 vs M1: not scored: deferred by owner decision 2026-11-08 (needs EuroCup M3 port).
- M1 vs Elo and M1 vs B0: see the M1 result below (filled after the run).
M1 result (appended after the run; test seasons 2023-24..2025-26; 586 shared test games, all with team box lines; M1 variant chosen on tuning: student_t_const; no validation gate):
- Log loss: M1 0.6062, Elo 0.6180, B0 0.6858.
- M1 vs Elo (gap = M1 - Elo): mean -0.0118, 97.5% CI -0.0257..+0.0018. Verdict: no ranking (mean passes the bar, CI upper bound is above 0).
- M1 vs B0 (gap = M1 - B0): mean -0.0797, 97.5% CI -0.1144..-0.0437. Verdict: m1 ranks above b0.
- M5 vs Elo and M5 vs M1: not scored: deferred by owner decision 2026-11-08 (needs EuroCup M3 port).
Details: reports/diag_eurocup_m1.json; docs/models/diag_eurocup.md.
