# Equal-weight forecast pool (POOL): four EuroLeague forecasts averaged in logit space

Status: live shadow (`POOL_LIVE_ENABLED = True` in `config.py`).

Judged by the standard promotion test (CLAUDE.md rule 4).

## What it is
Season labels are start years: `2026` is 2026-27.

**Model.** For a game `g` with component home-win probabilities `P_k` (k in Elo, M1, M5, ELOR):

    z_k     = logit(clip(P_k, 1e-6, 1 - 1e-6))
    P_pool  = sigmoid( (z_elo + z_m1 + z_m5 + z_elor) / 4 )

- Weights are fixed at 1/4. There is no tuned parameter, clip level or component choice.
- Symmetric: `P_pool(1 - P_k for all k) = 1 - P_pool`. The clip keeps every output in (0, 1).
- The pool row's `exp_margin` is the arithmetic mean of the four components' `exp_margin`. It is logged for display and is not scored.
- Calibrated Elo (ELOC) is not a component.

**Components.** Each component is read from its own live log, at its pinned `model_version`. Rows at any other version are ignored.

| Component | Log | Pinned `model_version` |
|---|---|---|
| Elo (flagship) | `predictions/euroleague_2026-27.csv` | `0.2.0+425e6393` |
| M1 | `predictions/euroleague_m1_2026-27.csv` | `0.2.0+m1.cbd9aaa3` |
| M5 | `predictions/euroleague_m5_2026-27.csv` | `0.2.0+m5.d4848a7e` |
| ELOR | `predictions/euroleague_elor_2026-27.csv` | `0.2.0+elor.59b43f20` |

The Elo log also holds 10 rows at `0.1.0+4356d891` (round 1, 2026-09-24). They are not pinned, so they never enter the pool. The pool's own version is `<package>+pool.<8 hex of sha256 of the pinned version list>`, computed by the code.

**Live rules** (`src/eurohoops/live_pool.py`, run after the four component logs are written in `eurohoops predict`):
1. Nothing is written unless `POOL_LIVE_ENABLED` is True.
2. A game gets a pool row only if all four pinned rows exist for it. A game missing any component is not logged. There is no backfill and no fallback.
3. The four rows must share `home`, `away` and `tipoff_utc`. A disagreement skips the game and is logged as an error. The pool's probability and margin are computed from the four-decimal values in the logs, so every pool row can be reproduced from the logs alone.
4. A game is pooled only if its tip-off is after the time the pool row is written. The row's `predicted_at_utc` is the latest of the four component stamps, and is strictly before tip-off.
5. Rows go to `predictions/euroleague_pool_2026-27.csv` (same columns as the other logs, `model = "pool"`), keyed by `(game_id, model_version)`. A logged key is not written again.
6. The pool reads only the four component logs. It reads no odds, injuries, marts or other forecast-pipeline data.

**Evaluation.** Live only. Every common historical game is in some component's tuning, selection or test set, so no clean out-of-sample set exists (see Results). The check `eurohoops backtest --model pool --check` computes this from the reports.

**Comparison.** On games with a pool row, the pool against the Elo log row for the same game, paired and game-weighted. Mean difference (pool minus Elo) of per-game log loss, with the look report's game-level CI (`promotion._reported_gap`: R1's resamples, seed and level), plus a round-clustered sensitivity (whole rounds resampled). It is reported at the R1 looks (after round 19, and season end) as `reported_only.pool_vs_elo` in `reports/promotion_euroleague_<season>_look<n>.json`. It is not used to promote or demote anything.

Shown with the numbers: the CI upper end below +0.002 and the mean at or below −0.002.

**Limits.**
- Shared information: ELOR is live Elo plus a roster offset, so Elo enters the pool at 1/4 directly and again through ELOR. The pool is an equal-weight average of overlapping forecasts.
- Timing: ELOR's first row is 2026-10-16, so the pool's first row comes after it. The look-1 pool holds rounds 6 to 19 only. The count is reported with each result.
- Clip: logs keep four decimals, so a logged 0.0000 or 1.0000 becomes log-odds ±13.8 at the 1e-6 clip and outvotes the other three.
- Selected sample: games any component misses are not pooled, so the pooled games are not a random sample.
- Version pins: a component version change ends coverage of new games under these pins. `predict` warns when it happens.

## Results
**Overlap of the four components** (pairwise joins on `game_id`; ELO, M1 and M5 share the same 3,299 games)

| Pair | Games | Seasons (games per season) |
|---|---|---|
| Elo + M1 | 3,299 | 2015-2025 (250, 259, 260, 260, 252, 328, 299, 328, 331, 330, 402) |
| Elo + M5 | 3,299 | 2015-2025 (same as above) |
| M1 + M5 | 3,299 | 2015-2025 (same as above) |
| Elo + ELOR | 2,535 | 2015-2023 (246, 255, 256, 256, 252, 324, 295, 324, 327) |
| M1 + ELOR | 2,535 | 2015-2023 (same) |
| M5 + ELOR | 2,535 | 2015-2023 (same) |
| **All four** | **2,535** | **2015-2023** |

ELOR has no game before 2015 and none after 2023. Its 32 neutral games in that span are excluded by its own rule.

No pooled live results are recorded in this card yet.

## Files
- Code: `src/eurohoops/live_pool.py`, `src/eurohoops/config.py` (`POOL_LIVE_ENABLED`, `POOL_COMPONENTS`), `src/eurohoops/eval/promotion.py`.
- Log: `predictions/euroleague_pool_2026-27.csv`, with inputs from the four component logs listed above.
- Reports: `reports/promotion_euroleague_<season>_look<n>.json` (`reported_only.pool_vs_elo`).
- Check: `eurohoops backtest --model pool --check`.
