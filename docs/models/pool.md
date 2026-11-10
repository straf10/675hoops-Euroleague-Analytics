# Equal-weight forecast pool (POOL): four EuroLeague forecasts averaged in logit space

Status: retired, 2026-11-03 (owner decision, PLAN §8.3). The model no longer runs. Its code, script, tests and site display were removed (dfb9f7a, merged in ac5d666). Its log stays in `predictions/` (rule 1).

## What it was
Season labels are start years: `2026` is 2026-27.

For a game with component home-win probabilities `P_k`:

    z_k     = logit(clip(P_k, 1e-6, 1 - 1e-6))
    P_pool  = sigmoid( (z_elo + z_m1 + z_m5 + z_elor) / 4 )

Weights were fixed at 1/4. A game got a pool row only when all four component logs held a row for it, at their pinned versions:

| Component | Log |
|---|---|
| Elo (flagship) | `predictions/euroleague_2026-27.csv` |
| M1 | `predictions/euroleague_m1_2026-27.csv` |
| M5 | `predictions/euroleague_m5_2026-27.csv` |
| ELOR | `predictions/euroleague_elor_2026-27.csv` |

ELOR is live Elo plus a roster offset, so Elo counted twice in the pool.

## Results (history)
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

**Live log.** `predictions/euroleague_pool_2026-27.csv` holds 41 lines (header included). This card records no pooled score.

## Files
- Log (kept): `predictions/euroleague_pool_2026-27.csv`.
- Removed: `src/eurohoops/live_pool.py`, `POOL_LIVE_ENABLED` and `POOL_COMPONENTS` in `config.py`, the pool tests and the pool check.
