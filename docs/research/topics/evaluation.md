# Evaluation on small samples

Question Q5: how do we judge models on small live samples?
Our setup: walk-forward by round, paired bootstrap of per-game log-loss gaps, a round-clustered sensitivity check and ECE. The R1 promotion rule needs a 97.5% CI upper bound below 0 and a mean gap ≤ −0.01, at two looks.

## What the papers say

**Shared outcomes shrink the effective sample.**
- [brill-2024](../papers/brill-2024-difficulty-win-probability.md), on in-game win probability:
  - Plays share one game result, so 4,101 games of play-by-play hold about 2,291 independent outcomes, 56% of nominal. With 8 seasons it falls to 31% (p.9).
  - Naive bootstrap 90% intervals cover only 60% of the time. A cluster bootstrap by game covers 71% (Table 1, p.12).
- For our pre-game forecasts, the game is already the unit. But games in a round share conditions (rest, travel, schedule), which is why we already report a round-clustered bootstrap. Brill supports keeping that check, and supports using a cluster bootstrap for the in-game model.

**Randomness caps accuracy.**
- [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md): at a neutral site, the best NBA team beats a median team only about 67% of the time (Fig. 7, p.25). Model gaps of 0.003 in log loss are small next to this ceiling.
- [tian-2024](../papers/tian-2024-spectral-dynamic-bradley-terry.md): claimed a win over Elo with a 0.0027 accuracy gap on about 3,690 games. The binomial SE is about 0.008 (reader's computation), so the gap is noise.
- [szczecinski-2021](../papers/szczecinski-2021-simplified-kalman-rating.md): scores against the base-rate entropy as a reference. In noisy leagues all methods sit close to it (p.18).

**Many segment tests need multiple-testing control.**
- [miller-2026](../papers/miller-2026-mma-betting-efficiency.md): uses Benjamini–Hochberg FDR at 10% per table (p.9). It still reports a "significant" Fly Weight result at t = 1.93 (Table 11, reader's note).
- [robbins-2022](../papers/robbins-2022-sports-betting-efficiency.md): many bin differences are "indistinguishable from random variation" (p.18).

**Leakage and split choice change the answer.**
- [li-2025](../papers/li-2025-ai-basketball-prediction-review.md): AdaBoost dropped from 75% in CV to 66.8% on a held-out test (p.9). Published "98.9%" results sit in a peer-reviewed review without a leakage check (p.13).
- [he-2025](../papers/he-2025-stacked-ensemble-nba.md): random row splits with mirror rows and same-game box scores.
- The honest ceiling is about 69% for EuroLeague and 78% for GBL (Lampis 2023 via Li, Table 3, p.14). Our Elo test accuracy is in that range.

**Diagnostics.**
- [ridall-2025](../papers/ridall-2025-epl-bayesian-state-space.md): calibration by outcome class (Table 4, p.16). Its scoring rules "show a high degree of agreement" (p.12).

## What we do now
We already use walk-forward splits, paired bootstrap, round clustering, pre-registered gates and leakage tests. The literature supports each of these. Nothing in it argues for loosening them.

## Gaps
- No paper gives a power calculation for log-loss gaps on a few hundred games. For our R1 looks, see the power estimate in [IDEAS.md](../IDEAS.md) (idea E1).
