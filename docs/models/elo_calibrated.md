# Calibrated Elo (ELOC): a logistic recalibration of Elo's probability

Status: backtest only (one-shot run, negative; not logged; `ELOC_LIVE_ENABLED = False` in `config.py`).

## What it is
**Question:** does a two-parameter logistic recalibration of Elo's own probability, fitted only on earlier seasons, improve EuroLeague home-win log loss out of sample? Context: live Elo's EuroLeague test ECE is 0.049364, against 0.005338 for the constant base rate B0 (`reports/backtest_elo.json`).

**Model**

    logit(p_elo) = d * ln(10) / 400          (exact: p_elo = 1 / (1 + 10^(-d/400)))
    p_cal        = sigmoid(a + b * logit(p_elo))

- `d` is Elo's pre-game difference (home minus away, home-court advantage included), from `elo.replay`.
- `(a, b)` is the unpenalised maximum-likelihood logistic regression of home win on `logit(p_elo)`. Newton's method, step tolerance 1e-10; the fit raises if it does not converge. The identity `(a, b) = (0, 1)` is raw Elo.
- Elo parameters are fixed: k 20, hca 90, reversion 0.25 (`config.ELOR_ELO_PARAMS`). No search.
- Elo is replayed from 2007. The fit and the forecast both use the 2007 replay. The published log replays from 2023, so the two can differ slightly.

**Data.** EuroLeague games mart. Scored games are the fold seasons that were played, not forfeit and not neutral. Elo's replay uses every played game from 2007. Seasons 2020 and 2021 (COVID) are kept.

**Folds.** Rolling origin, expanding window. Scored folds are seasons 2015 to 2023 (nine). The fit for fold `s` uses the scored games of seasons 2011 to `s-1` only. The 2007 to 2010 seasons are replayed for Elo's ratings only. The live fit uses 2011 to 2025.

**Fit.** Maximum likelihood, no regularisation, no grid. Each fold's `(a, b)` is reported.

**Metrics.** Primary: pooled per-game log loss of P(home win) over the nine folds, game-weighted. Reported, not used for the comparison: pooled Brier and expected calibration error (10 equal-width bins, `eval/metrics.py:ece`), for Elo and ELOC, also per season.

**Paired comparison.** Per game, `gap = loss(ELOC) - loss(Elo)` on the same scored games. Mean and 95% CI from `eval/m7_backtest.py:cluster_bootstrap_ci`: resamples of whole seasons (the nine fold seasons, with replacement), game-weighted, 10,000 resamples, seed 20261015, percentile interval. The CI resamples only nine season clusters.

**Criteria.** Three parts: (1) pooled ELOC log loss below pooled Elo log loss; (2) upper end of the 95% CI of the gap below +0.002; (3) mean gap -0.002 or lower.

**Live plan.** Not running. If enabled, the `(a, b)` from the report's `live_fit` would be used and logged to `predictions/euroleague_eloc_2026-27.csv`, separate from the flagship Elo file. ELOC is not on the Forecasts page.

**Limits.** The live Elo parameters were tuned on 2024 (2025 was Elo's test season). The live fit's seasons therefore include Elo's tuning and test seasons. On 2024, Elo's `d` is in-sample, which can pull `b` toward 1.

**Build check.** The one-shot run aborts and writes nothing unless its scored games are ELOR's 2,535 and Elo's pooled log loss on them equals ELOR's (`reports/elor_cv.json`, `elo.log_loss`, 0.605151 to six decimals).

## Results
Run once, 2026-10-17. 2,535 scored games. The Elo baseline matched ELOR's (0.605151).

| | Log loss | Brier | ECE |
|---|---|---|---|
| Elo (2007 replay) | 0.605151 | 0.208911 | 0.021872 |
| ELOC | 0.607589 | 0.209744 | 0.034228 |

- Gap ELOC minus Elo: mean +0.002439, 95% CI [−0.002686, +0.007635].
- Against the criteria: below Elo, no. Non-inferior, no. Worth a version, no. ELOC is not logged.
- Every fold fits `b` above 1 (1.72 in 2015, falling to 1.32 in 2023) and `a` below 0 (−0.25 to −0.09). On this replay Elo is under-confident, and the intercept moves away from home wins.
- The fitted slope does not carry forward. ELOC beats Elo in 2018, 2019 and 2023, and loses in the other six folds.
- The 2007 replay's ECE on 2015–2023 (0.022) is less than half the published 2023-start Elo's test ECE on 2025 (0.049). The seasons differ, so this is not like-for-like.
- Live fit, for the record: `a` −0.063462, `b` 1.262976 (2011–2025, 4,189 games).

## Files
- Code: `src/eurohoops/models/elo.py` (replay), `src/eurohoops/config.py` (`ELOC_LIVE_ENABLED`, `ELOR_ELO_PARAMS`).
- Command: `eurohoops backtest --model eloc --cv` (one-shot run), `--cv-check` (game counts only).
- Reports: `reports/eloc_cv.json`, `reports/eloc_cv_games.csv`, baseline `reports/elor_cv.json`.
- Tests: `tests/test_eloc_cv.py` (fold `s` fit is unchanged by edits to season `s` or later games).
