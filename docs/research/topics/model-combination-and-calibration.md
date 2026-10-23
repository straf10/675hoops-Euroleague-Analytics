# Combining forecasts and recalibration

Question Q4: equal or estimated weights, linear or log pool, and should we recalibrate, given few live games?
Our setup: POOL is an equal-weight log pool of Elo, M1, M5 and ELOR, with weights fixed at 1/4 (`docs/models/pool.md`). A learned blend candidate gave no log-loss gain (`docs/models/candidate_elo_blend.md`). ELOC (calibrated Elo) was negative.

## What the papers say

**Equal weights are hard to beat, especially with little data.**
- [wang-2022](../papers/wang-2022-forecast-combinations-review.md): this is "the forecast combination puzzle" (p.5–6, p.19–20). The main cause is error in estimating the weights, which grows with small samples (p.20–21). Estimated weights need a large enough training sample (p.25).
- [gupta-1987](../papers/gupta-1987-combination-of-forecasts.md), simulation:
  - Regression weights were the worst method at N = 5: MAE 3.96 vs equal weights 2.44 (Table 3, p.13).
  - With N = 100, regression was the best (1.64) and equal weights were the worst estimated scheme (2.44).
  - Equal weights work well when the models have similar error variances and poorly when they do not (H6, p.14).
- Our models have similar log loss (within about 0.005 of each other on the EuroLeague tests). That is the case where equal weights do well.

**Linear pools are under-confident; log pools are sharper.**
- [wang-2022](../papers/wang-2022-forecast-combinations-review.md): linear pooling of distributions adds the members' disagreement to the variance, so it is less sharp (p.23–24). The log pool is the g = log case of the generalised pool (p.28).
- A spread parameter c can recalibrate a pool: c < 1 for neutrally or under-confident members, c ≥ 1 for over-confident ones (p.29).
- Against that, Baran & Lerch (2018) found "no substantial differences" between simple and theoretically better pools (p.30).
- [yu-2026](../papers/yu-2026-quantile-adaptive-forecast-combining.md): for full CDFs, averaging along rays (between vertical and horizontal averaging) beat the linear pool by 2–5% on a quantile score (Table 1, p.894). That is on COVID deaths, not sports.

**Stacking with learned meta-models can mislead.**
- [he-2025](../papers/he-2025-stacked-ensemble-nba.md): an MLP stack reported 83% NBA accuracy, but its features are same-game box scores and the split is random. The result is leakage, not skill.
- [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md) cites Manner (2015): merging a state-space model with market probabilities "only occasionally outperformed betting markets alone" (p.7).

## What we do now
- POOL uses the setting the literature favours for small samples: an equal-weight log pool, nothing tuned.
- It has no spread or recalibration parameter.

## Disagreements and gaps
- Wang's spread-adjusted pools vs Baran & Lerch's null result: the gain from recalibrating a pool is uncertain and data-hungry.
- Evidence on pooling binary win probabilities is thin. Most of it is about continuous or time-series forecasts.
- Whether POOL's members are too correlated (Elo and ELOR) is untested. Wang suggests screening for redundant members (p.18–19).
