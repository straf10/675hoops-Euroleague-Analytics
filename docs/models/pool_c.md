# POOL-c: POOL with a spread parameter on its logit

Status: diagnostic (draft; nothing fitted or evaluated on live data yet).

Pass bar: the 95% CI upper bound of the paired difference (POOL-c minus POOL) log loss is below 0.

## What it is
**Question:** does a single spread parameter `c`, applied to POOL's logit, improve POOL's home-win log loss on live EuroLeague games? POOL is the equal-weight log pool of Elo, M1, M5 and ELOR (`docs/models/pool.md`). This is a research test on top of POOL. It does not change POOL, the flagship or any published forecast.

**Model.** Let `z_pool = logit(P_pool)`, the logit POOL already computes (four components, equal weights, clip 1e-6). Then

    P_c = sigmoid( c * z_pool ),    c in [0, 5]

- One parameter, `c`. The weights, the clip and the four components are POOL's and are not tuned.
- `c = 1` is POOL itself. `c < 1` flattens the pool; `c > 1` sharpens it.

**Fit.** Bounded one-dimensional minimisation (Brent, `scipy.optimize.minimize_scalar`, xatol 1e-8) of the mean per-game log loss, with probabilities clipped to [1e-6, 1 − 1e-6] as POOL's are. The loss is convex in `c` until the clip binds. The fit is deterministic.

**Rows.** POOL's scored row per game (the latest row stamped before tip-off). Outcome: the home team won (margin > 0), from finished games in the marts. Probabilities: the logged `p_home` (four decimals).

**Method.**
1. Fit set: POOL's scored rows for EuroLeague 2026-27 rounds 1 to 19. `c` is fitted once on that set.
2. Evaluation set: POOL's scored rows for rounds 20 to season end. No evaluation row is used for the fit.
3. Test: paired bootstrap of the per-game difference (POOL-c minus POOL) log loss over the evaluation rows. 10,000 resamples of games with replacement, seed 20261022 (`GATE_RESAMPLES`, `GATE_SEED` in `pool_c.py`; `eval.metrics.paired_bootstrap_ci`). Interval: 95% percentile CI of the mean difference.

**Limits.**
- Few fitting games: POOL's first live row is ELOR's first row (2026-10-16), so the fit set holds rounds 6 to 19 only. The count is reported when `c` is fitted.
- If the pool is calibrated, `c` is near 1 and POOL-c equals POOL.
- Rounding: POOL's logged `p_home` has four decimals. `z_pool` is recovered from the rounded value, which moves the logit by at most about 2e-4 near 0.5, and more near 0 or 1.
- Shared information: POOL's components overlap (ELOR contains Elo). A fitted `c` corrects for that overlap as well as for spread.
- One season: the evaluation set is a minority of the season, so the CI is wide.
- Selected sample: only games all four components logged are pooled.

## Results
None yet.

## Files
- Code: `src/eurohoops/eval/pool_c.py` (`fit_c`, `apply_c`, `paired_gap`), `src/eurohoops/eval/metrics.py` (`paired_bootstrap_ci`).
- Tests: `tests/test_pool_c.py` (synthetic, seeded).
- Input: `predictions/euroleague_pool_2026-27.csv`.
