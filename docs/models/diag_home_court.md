# Diagnostic: is the frozen EuroLeague home-court value (hca 90) wrong?

Status: diagnostic (no change made; live Elo keeps k 20, hca 90, reversion 0.25).

## What it is
**Question:** in the live 2026-27 season (48 finished games), Elo's mean home-win probability is 0.606 and the actual home-win rate is 0.5625. Is the home-court value (hca 90, 62.7% at equal ratings) shown to be wrong, or is the 2026 gap noise?

**Method.**
- Data: the EuroLeague games mart. Ratings are replayed over every played game (forfeits excluded) from 2007, so they are warm. Only non-neutral played games are scored (2015 to 2026; 2026 is partial).
- Elo code reused as is: `prepare`, `replay`, `EloParams`, `win_probability`.
- Section 1: live parameters, per season: games, actual home-win rate, mean `p_home`, gap (mean `p_home` minus actual).
- Section 2: hca in {50, 60, 70, 80, 90, 100, 110}, with k and reversion at live values. Log loss and Brier on 2024-25 pooled, on 2025 alone, and on 2026 so far. 2024 was the live tuning season, so 2025 is the test season. 2024-25 pooled is shown for completeness.
- Section 3: paired bootstrap of the 2025 per-game log-loss difference, between the hca that is best on 2025 and hca 90. 10,000 resamples, seed 20261015, 95% percentile CI. "Best on 2025" is chosen on the same games the bootstrap uses, so the difference is optimistic. The CI includes 0 either way.

## Results

**Section 1: per season, live Elo (k 20, hca 90, reversion 0.25)**

| Season | Games | Actual home win | Mean p_home | Gap (p − actual) |
|---|---:|---:|---:|---:|
| 2015 | 246 | 0.6463 | 0.6160 | −0.0303 |
| 2016 | 255 | 0.6235 | 0.6173 | −0.0063 |
| 2017 | 256 | 0.6367 | 0.6157 | −0.0210 |
| 2018 | 256 | 0.6328 | 0.6182 | −0.0146 |
| 2019 | 252 | 0.6190 | 0.6130 | −0.0060 |
| 2020 | 324 | 0.5679 | 0.6163 | +0.0484 |
| 2021 | 295 | 0.6542 | 0.6141 | −0.0402 |
| 2022 | 324 | 0.6265 | 0.6165 | −0.0100 |
| 2023 | 327 | 0.6453 | 0.6156 | −0.0297 |
| 2024 | 326 | 0.6196 | 0.6185 | −0.0011 |
| 2025 | 399 | 0.6366 | 0.6200 | −0.0166 |
| 2026 (partial) | 48 | 0.5625 | 0.6058 | +0.0433 |

**Section 2: hca grid (k 20, reversion 0.25)**

| hca | LL 2024-25 | Brier 2024-25 | LL 2025 | Brier 2025 | LL 2026 | Brier 2026 |
|---:|---:|---:|---:|---:|---:|---:|
| 50 | 0.632217 | 0.221746 | 0.640075 | 0.225080 | 0.624148 | 0.216828 |
| 60 | 0.629073 | 0.220326 | 0.636443 | 0.223401 | 0.624379 | 0.217221 |
| 70 | 0.626730 | 0.219280 | 0.633621 | 0.222099 | 0.625353 | 0.217971 |
| 80 | 0.625178 | 0.218599 | 0.631600 | 0.221165 | 0.627061 | 0.219065 |
| **90 (live)** | 0.624406 | 0.218270 | 0.630369 | 0.220588 | 0.629490 | 0.220489 |
| 100 | 0.624400 | 0.218279 | 0.629913 | 0.220353 | 0.632629 | 0.222227 |
| 110 | 0.625147 | 0.218609 | 0.630218 | 0.220444 | 0.636463 | 0.224262 |

Game counts: 725 (2024-25), 399 (2025), 48 (2026). Actual home-win rates: 0.6290, 0.6366, 0.5625.

**Section 3: paired bootstrap, 2025**
- Best hca on 2025: 100 (n = 399 games).
- Observed mean log-loss difference, hca 100 minus hca 90: −0.000456.
- 95% CI (10,000 resamples, seed 20261015): [−0.003207, +0.002303]. Includes 0.

**Reading.**
- On 2025, the best hca (100) beats 90 by 0.000456 in log loss, and the CI runs from −0.0032 to +0.0023. It covers zero.
- Across the grid, 2024-25 log loss is flat between 90 and 100 (differences of 0.000006 or less).
- The 2026 gap (+0.043; Elo 0.606 against 0.5625 actual) is within noise. With 48 games the standard error of the home-win rate is about 0.07 (hand calculation, not printed by the script), so the gap is about 0.6 standard errors.
- Over 2015–2025, the gap is negative in 10 of 11 seasons: home teams won more often than the model expected. This is a weak hint that hca 90 runs low on average. It is not decisive, and the 2024-25 calibration does not move much between 90 and 100.
- The 2026 log loss is lowest at hca 50, not at 90 or 100. That is 48 games, and it points the opposite way from the historical gap.

**Conclusion.** The home-court value is not shown to be wrong. Live hca stays at 90. A future home-court change (for example the long-history tuned value of 110) would be a new shadow model, judged on live games.

## Files
- Script: `scripts/diag_home_court.py`.
- Report: `reports/diag_home_court.json`.
- Code: `src/eurohoops/models/elo.py` (`prepare`, `replay`, `EloParams`, `win_probability`), `src/eurohoops/config.py`.
