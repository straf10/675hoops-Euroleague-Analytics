# R1 promotion looks: power report (E1)

Status: draft, not committed by the owner. This is a report, not a model change and not a gate. Nothing here changes `promote`, the looks, the statistic or the CI in `m5.md` and `m1.md` (PLAN §8.1 R1). No 2026-27 live rows were used.

Code: `scripts/r1_power.py` (writes `reports/r1_power.json`), `src/eurohoops/eval/r1_power.py`, `tests/test_r1_power.py`. The rule itself is `eval/promotion.py`; the bootstrap upper bound here is checked to equal `bootstrap_ci` exactly.

## Rule (unchanged)
Promote at the first look where the two-sided 97.5% paired-bootstrap CI of the mean per-game log-loss gap (flagship − Elo) has an upper bound below 0 and the mean is −0.01 or lower. 10,000 resamples, seed 20261009. EuroLeague: M5 vs Elo, looks after round 19 and at season end. GBL: M1 vs Elo, looks after round 13 and at season end.

## Per-game gap SD (sources)
Per-game log losses come from the backtest per-game files (`reports/backtest_m5_games.csv`, `reports/backtest_m5_gbl_games.csv`), using the gate variants. The per-game means reproduce the published gate and test values.

| Competition | Pair | Split | Games | Mean gap | SD |
|---|---|---|---|---|---|
| EuroLeague | M5 − Elo | test (2024–25) | 732 | −0.00135 | 0.1414 |
| EuroLeague | M5 − Elo | validation (2023) | 331 | −0.00474 | 0.1264 |
| EuroLeague | M1 − Elo | test | 732 | −0.00134 | 0.0879 |
| EuroLeague | M1 − Elo | validation | 331 | −0.00080 | 0.0670 |
| EuroLeague | M5 − M1 | test | 732 | −0.00002 | 0.1299 |
| EuroLeague | M5 − M1 | validation | 331 | −0.00395 | 0.1044 |
| GBL | M1 − Elo | test | 340 | +0.00367 | 0.2719 |
| GBL | M1 − Elo | validation | 163 | −0.00649 | 0.1959 |
| GBL | M5 − Elo | test | 340 | −0.00092 | 0.3415 |
| GBL | M5 − Elo | validation | 163 | +0.03856 | 0.2687 |
| GBL | M5 − M1 | test | 340 | −0.00459 | 0.2093 |
| GBL | M5 − M1 | validation | 163 | +0.04505 | 0.2320 |

Cross-checks: the SD implied by the published CI matches the per-game SD (EuroLeague M1 − Elo test 0.0859 vs 0.0879; GBL M1 − Elo test 0.2781 vs 0.2719; EuroLeague M5 − M1 validation 0.0986 vs 0.1044, a 6% difference).

The R1 power uses the test-split SD of the R1 pair: 0.1414 (EuroLeague) and 0.2719 (GBL). Validation and pooled SDs are sensitivity rows. Using an SD estimated on a split already used for model selection is a variance estimate, not a fit to the gate's data.

The gap distribution is not normal. EuroLeague M5 − Elo test: skew 0.78, excess kurtosis 3.4. GBL M1 − Elo test: skew −2.39, excess kurtosis 9.1.

## Game counts (assumptions)
From the games mart, read only, 2026-10-22. The 2026-27 schedule is 38 EuroLeague rounds of 10 games and 26 GBL rounds of 7.

- EuroLeague, round-19 look: 160 games (rounds 4–19). M5 logs from round 4, per the rule text.
- EuroLeague, season end: 372 games (rounds 4–38 = 350, plus 22 playoff games). The 22 assumes the 2025-26 format (play-in 3, playoffs 16, Final Four 3), because the 2026-27 playoff schedule is not in the mart yet.
- GBL, round-13 look: 91 games (rounds 1–13).
- GBL, season end: 200 games (182 regular season, plus 18 playoff games from 2025-26; not yet scheduled).

## Method
- Analytic: normal approximation. Each look's mean is N(true gap, SD²/n). The look passes when the mean is below min(−0.01, −2.2414·SD/√n). Looks are nested, so the cumulative probability uses the bivariate normal with corr = √(n1/n2).
- Simulation: 2,000 simulated seasons with simulation seed 20261022. Each season's gaps are resampled with replacement from the test-split gaps, centred and shifted to the true gap. The rule is applied at each look with the 10,000-resample bootstrap (seed 20261009). Monte Carlo SE of a probability near 0.03 is about 0.004.

## Results: probability of promotion
Marginal = first promotion at that look. Cumulative = promotion by season end. Null (gap 0) is a reference row: the false-promotion rate.

EuroLeague (R1 SD 0.1414; looks 160 and 372 games)

| True gap | Analytic: round 19 | Analytic: season end (marginal / cumulative) | Simulation: round 19 | Simulation: season end (marginal / cumulative) |
|---|---|---|---|---|
| −0.003 | 0.024 | 0.025 / 0.049 | 0.031 | 0.036 / 0.067 |
| −0.005 | 0.036 | 0.044 / 0.080 | 0.049 | 0.058 / 0.107 |
| −0.010 | 0.089 | 0.133 / 0.222 | 0.111 | 0.151 / 0.262 |
| −0.020 | 0.326 | 0.384 / 0.710 | 0.354 | 0.363 / 0.717 |
| 0 (null) | 0.013 | 0.010 / 0.022 | 0.016 | 0.018 / 0.034 |

GBL (R1 SD 0.2719; looks 91 and 200 games)

| True gap | Analytic: round 13 | Analytic: season end (marginal / cumulative) | Simulation: round 13 | Simulation: season end (marginal / cumulative) |
|---|---|---|---|---|
| −0.003 | 0.016 | 0.014 / 0.030 | 0.007 | 0.009 / 0.016 |
| −0.005 | 0.019 | 0.017 / 0.037 | 0.010 | 0.013 / 0.022 |
| −0.010 | 0.029 | 0.031 / 0.060 | 0.018 | 0.027 / 0.045 |
| −0.020 | 0.062 | 0.080 / 0.142 | 0.054 | 0.085 / 0.139 |
| 0 (null) | 0.013 | 0.009 / 0.022 | 0.007 | 0.004 / 0.011 |

Sensitivity (analytic, cumulative by season end, true gap −0.01): EuroLeague with validation SD 0.1264 gives 0.270; pooled SD 0.1368 gives 0.235. GBL with validation SD 0.1959 gives 0.086; pooled SD 0.2497 gives 0.065.

## Reading the numbers
- EuroLeague: a true gap of −0.01 gives about a 1-in-4 chance of promotion by season end. At −0.02 it is about 0.7.
- GBL: a true gap of −0.02 gives about 0.14 by season end. Round 13 has almost no power, because 91 games give a mean SE of 0.028.
- The analytic and simulated values agree for EuroLeague at gaps of −0.01 and −0.02. They differ at small gaps.

## Open point: simulation vs analytic
The simulated null rate is above nominal, and the simulation promotes more often than the analytic at small gaps. Only part of this is explained.

- The simulation procedure is sound. With normal gaps of the same SD, the simulated round-19 rate is 0.0105 at gap 0 (analytic 0.0125) and 0.0205 at −0.003 (analytic 0.0242). Both are within Monte Carlo error.
- The excess comes from the shape of the empirical gaps. The EuroLeague test gaps have skew 0.8 and excess kurtosis 3.4, and the bootstrap percentile bound behaves differently at n = 160 from the normal case. The GBL gaps have skew −2.4 and kurtosis 9.1, which pushes the simulated rates below analytic.
- Part of the EuroLeague gap at the season-end look is Monte Carlo noise: the difference (0.034 vs 0.022) is about 2.5 SE.
- Not tested: whether the sample-SD dependence of the threshold contributes. The normal-gap check suggests it is small, but this is not isolated.

Practical consequence: for EuroLeague, the analytic values are slightly optimistic for the null and slightly pessimistic at small gaps. The GBL analytic values are slightly optimistic overall. Neither changes the conclusion that GBL round 13 has little power.

## Not in this report
No gate, no rule change, no model change. No live 2026-27 rows. No attempt to tune anything. Round-clustered sensitivity is not repeated here; the look reports already carry it.

## Questions for the owner
1. Accept the playoff counts (22 EuroLeague, 18 GBL) from 2025-26, or give the 2026-27 format?
2. The GBL R1 test has little power at either look. Is that acceptable, or should the GBL look or statistic be declared differently before 2026-27 round 13?

**Owner decision (2026-10-23), recorded here:** R1 v1 stands unchanged for 2026-27, playoff counts 22 and 18 accepted. GBL R1 v2 is drafted below, from 2027-28 only.

---

## GBL R1 v2 (draft, applies from 2027-28)

Status: draft, not committed by the owner. The owner decided on 2026-10-23 to plan a v2; this section is the draft text and the power analysis, not a rule in force.

- **R1 v1 stands unchanged for 2026-27.** The GBL flagship looks in `m1.md` (round 13 and season end; M1 − Elo; two-sided 97.5% CI; mean at most −0.01) are not edited.
- **R1 v2 (GBL only) applies from the 2027-28 season and never retroactively.** Nothing scored in 2026-27 is judged under v2 except as pooled data below.
- **Games:** live GBL games that both Elo and M1 logged before tip-off and that have a result, from 2026-27 round 1 through the 2027-28 season. 2026-27 games are scored under the 2026-27 rules (the latest logged row before tip-off, per the scorecard rule). A new M1 or Elo `model_version` in either season breaks the pool: the count restarts from that version, as in v1.
- **Statistic and bar:** the same as v1. Mean per-game log-loss gap M1 − Elo; paired bootstrap over games (10,000 resamples, fixed seed); promote at the first look where the two-sided 97.5% CI upper bound is below 0 **and** the mean is −0.01 or lower.
- **Looks:** 2027-28 regular-season round 13 (pooled n = 200 + 91 = 291) and 2027-28 season end (pooled n = 200 + 200 = 400). The looks are nested.

### Why pool
v1 at round 13 has 91 games. At a true gap of −0.02 it promotes about 6% of the time (analytic, SD 0.2719). Pooling the 2026-27 season doubles the sample at season end and roughly triples it at round 13.

### Power (analytic, normal approximation; no live 2026-27 rows used)
SD 0.2719 is the GBL M1 − Elo test-split SD, the same as v1 (`reports/r1_power.json`, key `gbl_v2_analytic`). Cumulative = promotion by that look; marginal = first promotion at that look.

| True gap | Round 13 (291 games): marginal | Season end (400 games): marginal / cumulative |
|---|---|---|
| −0.003 | 0.020 | 0.011 / 0.031 |
| −0.005 | 0.027 | 0.016 / 0.043 |
| −0.010 | 0.053 | 0.032 / 0.085 |
| −0.020 | 0.162 | 0.093 / 0.255 |
| 0 (null, reference) | 0.013 | 0.007 / 0.019 |

For comparison, v1 at −0.02: round 13 marginal 0.062; season end cumulative 0.142.

Simulation is not repeated for v2. The GBL gap shape is strongly skewed (skew −2.4, excess kurtosis 9.1), so the analytic values are an approximation. For v1 the simulation ran below analytic at these sizes, so these v2 analytic values are probably slightly optimistic.

### Risks
- **Stationarity.** Pooling assumes the M1 − Elo gap has the same mean in 2026-27 and 2027-28. A version change in either model restarts the pool. If the gap drifts with the season (roster or rule changes), the pooled mean mixes two regimes.
- **Within-season dependence.** Games in one round share shocks. The round-clustered sensitivity used for v1 should be reported alongside v2.
- **Power is still limited.** Even pooled, a true gap of −0.01 gives about 5% at round 13 and about 8.5% by season end. The bar is the owner's v1 bar, kept as is.

### Option, not a decision
Keeping the v1 bar is the default in this draft, and no reason was found to state otherwise. A smaller detectable gap would need a different bar, which would have to be pre-registered separately; it is not proposed here.
