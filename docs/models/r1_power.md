# R1 promotion looks: power of the look rules

Status: diagnostic (power report; no 2026-27 live rows used). It changes no rule, look, statistic or CI.

Rule in force for 2026-27: R1 v1, unchanged.

## What it is
Code: `scripts/r1_power.py` (writes `reports/r1_power.json`), `src/eurohoops/eval/r1_power.py`, `tests/test_r1_power.py`. The rule itself is `eval/promotion.py`. The bootstrap upper bound here equals `bootstrap_ci` exactly.

**R1 rule.** Promote at the first look where the two-sided 97.5% paired-bootstrap CI of the mean per-game log-loss gap (flagship minus Elo) has an upper bound below 0, and the mean is -0.01 or lower. 10,000 resamples, seed 20261009.
- EuroLeague: M5 vs Elo, looks after round 19 and at season end.

**Per-game gap SD.** From the backtest per-game files (`reports/backtest_m5_games.csv`), using the variants the R1 look reports use. The per-game means reproduce the published validation and test values.

| Competition | Pair | Split | Games | Mean gap | SD |
|---|---|---|---|---|---|
| EuroLeague | M5 − Elo | test (2024–25) | 732 | −0.00135 | 0.1414 |
| EuroLeague | M5 − Elo | validation (2023) | 331 | −0.00474 | 0.1264 |
| EuroLeague | M1 − Elo | test | 732 | −0.00134 | 0.0879 |
| EuroLeague | M1 − Elo | validation | 331 | −0.00080 | 0.0670 |
| EuroLeague | M5 − M1 | test | 732 | −0.00002 | 0.1299 |
| EuroLeague | M5 − M1 | validation | 331 | −0.00395 | 0.1044 |

Cross-checks: the SD implied by the published CI matches the per-game SD (EuroLeague M1 − Elo test 0.0859 vs 0.0879; EuroLeague M5 − M1 validation 0.0986 vs 0.1044, a 6% difference).

Validation and pooled SDs are sensitivity rows.

The gap distribution is not normal. EuroLeague M5 − Elo test: skew 0.78, excess kurtosis 3.4.

**Game counts.** From the games mart, 2026-10-22.
- EuroLeague, round-19 look: 160 games (rounds 4–19). M5 logs from round 4.
- EuroLeague, season end: 372 games (rounds 4–38 = 350, plus 22 playoff games). The 22 assumes the 2025-26 format (play-in 3, playoffs 16, Final Four 3), because the 2026-27 playoff schedule is not in the mart yet.

**Method.**
- Analytic: normal approximation. Each look's mean is N(true gap, SD²/n). The look passes when the mean is below min(−0.01, −2.2414·SD/√n). Looks are nested, so the cumulative probability uses the bivariate normal with correlation √(n1/n2).
- Simulation: 2,000 simulated seasons, seed 20261022. Each season's gaps are resampled with replacement from the test-split gaps, centred and shifted to the true gap. The rule is applied at each look with the 10,000-resample bootstrap (seed 20261009). Monte Carlo SE of a probability near 0.03 is about 0.004.

## Results
Marginal = first promotion at that look. Cumulative = promotion by season end. Null (gap 0) is the false-promotion reference row.

**EuroLeague** (R1 SD 0.1414; looks 160 and 372 games)

| True gap | Analytic: round 19 | Analytic: season end (marginal / cumulative) | Simulation: round 19 | Simulation: season end (marginal / cumulative) |
|---|---|---|---|---|
| −0.003 | 0.024 | 0.025 / 0.049 | 0.031 | 0.036 / 0.067 |
| −0.005 | 0.036 | 0.044 / 0.080 | 0.049 | 0.058 / 0.107 |
| −0.010 | 0.089 | 0.133 / 0.222 | 0.111 | 0.151 / 0.262 |
| −0.020 | 0.326 | 0.384 / 0.710 | 0.354 | 0.363 / 0.717 |
| 0 (null) | 0.013 | 0.010 / 0.022 | 0.016 | 0.018 / 0.034 |


Sensitivity (analytic, cumulative by season end, true gap −0.01): EuroLeague with validation SD 0.1264 gives 0.270; pooled SD 0.1368 gives 0.235.

**Reading the numbers.**
- EuroLeague: a true gap of −0.01 gives about a 1-in-4 chance of promotion by season end. At −0.02 it is about 0.7.
- The analytic and simulated values agree for EuroLeague at gaps of −0.01 and −0.02, and differ at small gaps.

**Simulation vs analytic.** The simulated null rate is above nominal, and the simulation promotes more often than the analytic at small gaps.
- With normal gaps of the same SD, the simulated round-19 rate is 0.0105 at gap 0 (analytic 0.0125) and 0.0205 at −0.003 (analytic 0.0242). Both are within Monte Carlo error.
- The excess comes from the shape of the empirical gaps. The bootstrap percentile bound behaves differently at n = 160 from the normal case.
- Part of the EuroLeague season-end difference (0.034 vs 0.022) is Monte Carlo noise, about 2.5 SE.
- Not tested: whether the sample-SD dependence of the threshold contributes.

## Files
- Code: `scripts/r1_power.py`, `src/eurohoops/eval/r1_power.py`, `src/eurohoops/eval/promotion.py`, `tests/test_r1_power.py`.
- Report: `reports/r1_power.json`.
- Inputs: `reports/backtest_m5_games.csv`, games mart.
