# POOL-c: spread-recalibrated pool (C1), draft gate

**Status: draft, not committed by the owner.** Drafted 2026-10-22, before EuroLeague round 19 is
played. Nothing here has been fitted or evaluated on live data. This card becomes binding only
when the owner commits it.

Season labels are start years: `2026` is 2026-27.

## Question
Does a single spread parameter c, applied to POOL's logit, improve POOL's home-win log loss on
live EuroLeague games? POOL is the equal-weight log pool of Elo, M1, M5 and ELOR
(`docs/models/pool.md`, v1, live-only). This card is a research test on top of it. It does not
change POOL, the flagship, or any published forecast.

## Model
Let z_pool = logit(P_pool) be the logit POOL already computes (its four components, equal
weights, clip 1e-6). POOL-c is

    P_c = sigmoid( c * z_pool ),    c in [0, 5]

- One parameter, c. The weights, the clip and the four components are POOL's and are not tuned.
- c = 1 is POOL itself. c < 1 flattens an over-confident pool; c > 1 sharpens an under-confident one.
- Fit: bounded 1-D minimisation (Brent, `scipy.optimize.minimize_scalar`, xatol 1e-8) of the mean
  per-game log loss, with probabilities clipped to [1e-6, 1 - 1e-6] as POOL's are. The loss is
  convex in c until the clip binds, so the search returns the minimum. The fit is deterministic.
- Code: `src/eurohoops/eval/pool_c.py` (`fit_c`, `apply_c`, `paired_gap`). Tests:
  `tests/test_pool_c.py` (synthetic, seeded).

## Rows
- **Which POOL rows:** POOL's scored row per game, i.e. the latest row stamped before tip-off
  (`docs/PLAN.md` §8.1, R-protocol of 2026-10-20). Rows stamped at or after tip-off never count.
- **Outcome:** the home team won (margin > 0), from the finished games in the marts.
- **Probabilities:** the logged `p_home` (4 decimals) of POOL's row.

## Draft gate
1. **Fit set:** POOL's scored rows for EuroLeague 2026-27 rounds 1–19. Declared now, before round 19
   is played. c is fitted once, on that set, and then frozen.
2. **Evaluation set:** POOL's scored rows for rounds 20 to season end. No row in the evaluation set
   is used for the fit.
3. **Test:** paired bootstrap of the per-game difference (POOL-c minus POOL) log loss over the
   evaluation rows. Resamples: 10,000 paired resamples of games with replacement, seed 20261022
   (`GATE_RESAMPLES`, `GATE_SEED` in `pool_c.py`, the function `eval.metrics.paired_bootstrap_ci`).
   Interval: the 95% percentile CI of the mean difference.
4. **Pass rule:** pass if the 95% CI upper bound is below 0. Otherwise POOL stays as it is, and
   POOL-c is recorded as not supported. No other rule (no mean threshold) applies.
5. **Nothing else:** no round-clustered sensitivity and no second look. A second look would need
   its own declaration.

## Logging, if the gate passes
POOL-c is logged only to a **new** predictions file, `predictions/euroleague_poolc_2026-27.csv`,
with `model = "poolc"`. It is never written into POOL's file (`predictions/euroleague_pool_2026-27.csv`).
Any logging needs its own owner approval and its own switch, and is not part of this draft.

## Risks and limits (disclosed)
- **Few fitting games.** POOL's first live row comes from ELOR's first row (2026-10-16), so the
  fit set holds rounds 6–19 only, fewer games than the ~190 that `IDEAS.md` assumes for rounds 1–19.
  The exact count is reported when c is fitted. A fit on that few games gives a noisy c.
- **c may be near 1.** If the pool is calibrated, c ≈ 1 and POOL-c = POOL: the test has nothing to
  find, and a pass is not expected.
- **Rounding.** POOL's logged p_home has 4 decimals. z_pool is recovered from the rounded value,
  which moves the logit by at most about 2e-4 near 0.5 and more near 0 or 1. Disclosed, not tuned.
- **Shared information.** POOL's components overlap (ELOR contains Elo), so the pool is not a
  diversified forecast. A c fitted on it is a correction for that overlap as much as for spread.
- **One season, small evaluation.** The evaluation set is rounds 20 to season end, a minority of
  the season. The 95% CI will be wide, and a pass is weak evidence.
- **Selected sample.** Only games all four components logged are pooled (`pool.md`).

## Owner decisions needed
1. Commit this gate (or amend it) before round 19 is played.
2. Confirm that POOL's scored row is the latest row before tip-off, as in §8.1.
3. Confirm the log name `predictions/euroleague_poolc_2026-27.csv` if POOL-c is ever logged.
4. Keep z_pool recovered from the logged 4-decimal p_home (as drafted), or recompute the exact
   logit from the component logs before the gate runs?
