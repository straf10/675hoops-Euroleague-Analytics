# Equal-weight forecast pool ("POOL"): protocol v1

**DRAFT — awaiting owner approval.** Nothing here has been run. No evaluation is run, and live
logging stays off (`POOL_LIVE_ENABLED = False` in `src/eurohoops/config.py`) until the owner
approves this document. Approval authorises this protocol, not the model's numbers.

Season labels are start years: `2024` is 2024-25, `2025` is 2025-26.

## Question
Does an equal-weight logarithmic pool of the four live EuroLeague forecasters beat live Elo on
home-win log loss? The pool has no tuned parameter: that is the point. It adds no multiplicity
to the programme's comparisons.

## Model
For a game g with component home-win probabilities P_k (k in Elo, M1, M5, ELOR):

    z_k     = logit(clip(P_k, 1e-6, 1 - 1e-6))
    P_pool  = sigmoid( (z_elo + z_m1 + z_m5 + z_elor) / 4 )

- Weights are fixed at 1/4. No weight, clip level or component is tuned.
- Symmetric: P_pool(1 - P_k for all k) = 1 - P_pool. The clip keeps every output in (0, 1).
- `exp_margin` of the pool row is the arithmetic mean of the four components' `exp_margin`. It is
  logged for display only and is not scored.
- **Not a component:** calibrated Elo (being built elsewhere) is excluded. Only the four below.

## Components and pinned versions
Each component is read from its own live log, at the `model_version` pinned here. Rows at any
other version are ignored, so a later model change cannot silently enter the pool.

| Component | Log | Pinned `model_version` |
|---|---|---|
| Elo (flagship) | `predictions/euroleague_2026-27.csv` | `0.2.0+425e6393` |
| M1 | `predictions/euroleague_m1_2026-27.csv` | `0.2.0+m1.cbd9aaa3` |
| M5 | `predictions/euroleague_m5_2026-27.csv` | `0.2.0+m5.d4848a7e` |
| ELOR | `predictions/euroleague_elor_2026-27.csv` | `0.2.0+elor.59b43f20` |

The Elo log also holds 10 rows at `0.1.0+4356d891` (round 1, 2026-09-24). They are not pinned, so
they never enter the pool. The pool's own version is `<package>+pool.<8 hex of sha256 of the
pinned version list>`, computed by the code.

## Historical overlap audit (done before this protocol, from committed reports)

**Question asked:** do out-of-sample backtest predictions exist for all four components on a
common set of historical games?

Sources: `reports/backtest_m5_games.csv` (rows for `elo`, `m1` = `student_t_const`, `m5` =
`proj_hc|core|d180|r40`, all splits 2015-2025), and `reports/elor_cv_games.csv` (ELOR's selected
setting `w0.5|n24`, folds 2015-2023). Joined on `game_id`.

Game counts by season (pairwise joins; ELO, M1 and M5 share the same 3,299 games):

| Pair | Games | Seasons (games per season) |
|---|---|---|
| Elo + M1 | 3,299 | 2015-2025 (250, 259, 260, 260, 252, 328, 299, 328, 331, 330, 402) |
| Elo + M5 | 3,299 | 2015-2025 (same as above) |
| M1 + M5 | 3,299 | 2015-2025 (same as above) |
| Elo + ELOR | 2,535 | 2015-2023 (246, 255, 256, 256, 252, 324, 295, 324, 327) |
| M1 + ELOR | 2,535 | 2015-2023 (same) |
| M5 + ELOR | 2,535 | 2015-2023 (same) |
| **All four** | **2,535** | **2015-2023** |

ELOR has no game before 2015 and none after 2023: its CV scores 2015-2023 only, and its 32
neutral games in that span are excluded by its own rule.

**Are these out-of-sample for each component?** No. Seasons each component has already seen:

| Component | Seasons used for tuning, selection or gating | Source |
|---|---|---|
| Elo | 2015-2025: its live parameters were chosen on 2024; its history run tuned 2015-2023 and scored 2024-25 | `docs/models/elo_roster_prior.md` ("Disclosed limits"); `config.py` `EUROLEAGUE.history_backtests` |
| M1 | 2015-2022 tuning, 2023 validation (gate), 2024-25 test (scored; test verdict committed) | `docs/models/m1.md`; `config.py` `EUROLEAGUE.m1` |
| M5 | 2015-2022 tuning, 2023 validation (gate), 2024-25 test; retune selection over 2015-2023 folds | `docs/models/m5.md`; `reports/m5_retune.json` |
| ELOR | 2015-2023: the CV that chose its live setting `w0 = 0.5, N = 24` | `reports/elor_cv.json`, `selected` |

Intersection of the "seen" sets over the four components: every season 2015-2023 is seen by
M1, M5 and ELOR, and 2024-2025 are seen by Elo, M1 and M5 and absent for ELOR. **Clean common
set: none.** The check mode (`eurohoops backtest --model pool --check`) computes this from the
reports and returns the same empty set.

## Choice: live-only evaluation (option ii)
A historical evaluation on the common games (option i) would need a clean out-of-sample set.
There is none: every common game is in some component's tuning, selection or gate set, and
ELOR cannot be scored at all on 2024 onward without a new run that the ELOR protocol does not
declare. Re-scoring the components on those games would also spend the M1 and M5 test
seasons a second time. The pool is therefore evaluated **live only**, as a reported comparison
at the existing R1 look schedule. It does not change the flagship.

## Live rules
Implemented in `src/eurohoops/live_pool.py`, run after the four component logs are written in
`eurohoops predict`.

1. **Gate:** nothing is written unless `POOL_LIVE_ENABLED` is `True`. It is `False` in this
   draft and changes only after owner approval.
2. **All four or nothing:** a game gets a pool row only if all four pinned-version rows exist
   for it. A game missing any component is not logged, with no backfill and no fallback.
3. **Agreement:** the four rows must share `home`, `away` and `tipoff_utc`. A disagreement skips
   the game and is logged as an error.
   The pool's probability and margin are computed from the 4-decimal values in the four logs,
   so every pool row can be reproduced from the logs alone.
4. **Logged before tip-off:** a game is pooled only if its tip-off is after the time the pool row
   is written; a game already played is never logged. The row's `predicted_at_utc` is the latest
   of the four component stamps, which must also be strictly before tip-off.
5. **Append-only and idempotent:** rows go to `predictions/euroleague_pool_2026-27.csv`
   (the same columns as the other logs, `model = "pool"`), keyed by `(game_id, model_version)`.
   A logged key is never written again. The file is never edited.
6. **No live read of anything else:** the pool reads only the four component logs. It never
   reads odds, injuries, marts or the rest of the forecast pipeline.

## Evaluation (live only)
- **Comparison:** on the games with a pool row, the pool against the Elo log row
  (`predictions/euroleague_2026-27.csv`) for the same game, paired and game-weighted. Mean
  difference (pool minus Elo) of per-game log loss with the look report's own game-level CI
  (`promotion._reported_gap`: R1's resamples, seed and level), plus the round-clustered
  sensitivity (whole rounds resampled).
- **Reported at the R1 looks** (`docs/models/m5.md`, "Flagship promotion rule": look 1 after
  round 19, look 2 at season end), as the block `reported_only.pool_vs_elo` in the look file
  (`reports/promotion_euroleague_<season>_look<n>.json`). It is reported, never used to promote
  or demote anything, and R1 itself is unchanged.
- **Shadow criterion, if asked:** same form as ELOR's: the CI upper end below +0.002 and the mean
  at or below −0.002. It is shown with the numbers, not as a verdict.
- **Expected size:** small. The first pool row can only come after ELOR's first row (2026-10-16,
  no backfill), so the pool judged at look 1 holds rounds 6-19 only. The count is always
  reported with the result.
- **Promotion of the pool** is not decided here. It will be declared before 2027-28 on live
  games only, as for the retuned M5 and ELOR.

## Limits (disclosed)
- **Shared information.** ELOR is live Elo plus a roster offset, so Elo enters the pool at 1/4
  directly and again through ELOR. The pool is an equal-weight average of overlapping forecasts,
  not a diversification argument.
- **Thin live evidence.** ELOR logs from 2026-10-16, so the pool starts late in 2026-27.
- **No historical test.** The pool's numbers come from live games only. Any conclusion is
  limited to the games logged.
- **Clip.** Logs keep four decimals, so a logged 0.0000 or 1.0000 becomes log-odds ±13.8 at the
  1e-6 clip and outvotes the other three. Unlikely in the EuroLeague; disclosed, not tuned.
- **Selected sample.** Games any component misses (e.g. ELOR roster failures) are not pooled, so
  the pooled games are not a random sample.

## Stopping rule
One live log, no change to the components, the pinned versions, the weights, the clip or the
criteria after approval. Any change is a new protocol version, declared before it is used.

A component version change (e.g. the M5 injury arm or a package version bump) ends v1 coverage of
new games; `predict` warns when it happens. POOL v2 must be declared before that component's first
new-version row (declare it together with the injury arm).

## Owner decisions needed
1. Approve this protocol (option ii, live-only, as drafted).
2. Confirm the pinned component versions above.
3. The CI is the look report's (R1's resamples and seed); no separate seed.
4. Only then set `POOL_LIVE_ENABLED = True` in `config.py`.
