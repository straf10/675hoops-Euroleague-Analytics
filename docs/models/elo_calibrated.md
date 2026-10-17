# Calibrated Elo (ELOC): protocol v1

**Status: approved by the owner on 2026-10-17, before the one-shot run.** Approval authorises the
protocol below, not the model. `ELOC_LIVE_ENABLED` (`src/eurohoops/config.py`) stays `False` until
the criteria pass and the owner switches it on in a separate commit.

## Question
Live Elo (`src/eurohoops/models/elo.py`, card `docs/models/elo.md`) is the published flagship. Its
EuroLeague test calibration error is 0.049364, against 0.005338 for the constant base rate B0
(`reports/backtest_elo.json`). Elo is sharper than B0 at the cost of reliability. Does a two-parameter
logistic recalibration of Elo's own probability, fitted only on earlier seasons, improve
EuroLeague home-win log loss out of sample?

The diagnostic `docs/models/diag_home_court.md` found Elo under-predicts home wins in 10 of 11
seasons (2015 to 2025). Changing hca does not fix that (hca 90 is already near-best on 2025). A
recalibration is a different lever: the intercept `a` can absorb the average home-win bias directly,
and the slope `b` can absorb over- or under-confidence. Neither is assumed to help. The protocol tests
whether they do.

## Model
    logit(p_elo) = d * ln(10) / 400          (exact: p_elo = 1 / (1 + 10^(-d/400)))
    p_cal        = sigmoid(a + b * logit(p_elo))

`d` is Elo's pre-game difference (home minus away, home-court advantage included), from
`elo.replay`. `(a, b)` is the unpenalised maximum-likelihood logistic regression of the home-win
outcome on `logit(p_elo)`. The start is the identity `(a, b) = (0, 1)`, which is raw Elo. The
fit uses Newton's method to a step tolerance of 1e-10, and it raises if it does not converge.
`a = 0, b = 1` is exactly live Elo, so the identity is a point the fit can reach.

**Elo parameters (fixed, not searched):** k 20, hca 90, reversion 0.25, the published flagship's
parameters (`config.ELOR_ELO_PARAMS`, checked against the `tuned` block of
`reports/backtest_elo.json`). This is not the comparison Elo re-tuned in M1's backtest (E-a, E-b).

**Replay convention:** Elo is replayed from 2007 (the first warm-up season), as ELOR's CV does. The
published log replays from 2023 (`live_backtest` warm-up), so the two can differ slightly. The gap
is measured once when the flag is switched on and added to this file, as ELOR's live amendment did.
Any live comparison is against the published log (2023 start), not the 2007 replay. Both `(a, b)`
and the live forecast use the 2007 replay, so the fit and the forecast see the same Elo values.

## Data
EuroLeague games mart (`eurohoops build`). **Scored games:** the fold seasons, played, not forfeit,
not neutral (the same population as ELOR and `scripts/diag_home_court.py`). Elo's replay uses
every played game from 2007. Seasons 2020 and 2021 (COVID) are kept, as in ELOR.

## Folds (rolling origin, expanding window)
- **Scored folds:** seasons 2015 to 2023 (nine folds).
- **Fit window for fold s:** the scored games of seasons 2011 to s-1 (`fit_from` 2011). Season s
  and later never enter the fit of fold s. Season 2011 is the first season of the M5 retune frame.
  The 2007 to 2010 seasons are replayed for Elo's ratings only, because the ratings start at 1500
  and are still converging there.
- **Live fit:** the scored games of seasons 2011 to 2025 (the 2025-26 season, the last completed
  one). Its `(a, b)` is frozen in the one-shot report (see Live plan).
- No random or game-level splits. No season is left out.

## Fit and tuning
- Maximum likelihood, no regularisation. Two parameters on 1,000 to 2,500 games need none, and a
  penalty would add a choice that this protocol does not make.
- **No grid. No other tuning.** `(a, b)` are the fit's output. Nothing selects among fits, no
  criterion picks a window, and no fold result changes a setting. Each fold's `(a, b)` is reported.
- Elo's k, hca, reversion and the margin scale are fixed. ELOC does not touch Elo's own ratings.

## Metrics
- **Primary:** pooled per-game log loss of P(home win) over the nine folds (game-weighted).
- **Secondary, reported, not used for criteria:** pooled Brier, and expected calibration error
  (10 equal-width bins, `eval/metrics.py:ece`), both for Elo and for ELOC. Also per season.

## Paired comparison and CI
Per game, `gap = loss(ELOC) - loss(Elo)` on the same scored games. The mean and its 95% CI come from
`eval/m7_backtest.py:cluster_bootstrap_ci`, the same function ELOR uses: resamples of whole
seasons (the 9 fold seasons, drawn with replacement), game-weighted, 10,000 resamples, seed
20261015, percentile interval.

## Shadow criteria (all three must hold)
1. **Below Elo (reported):** pooled ELOC log loss < pooled Elo log loss on the nine folds.
2. **Non-inferior:** the upper end of the 95% CI of the gap is below +0.002.
3. **Worth a version:** the mean gap is -0.002 or lower.

These are the margins of the M5 retune and ELOR. Criterion 3 implies criterion 1. Superiority beyond
these margins is reported and not required. Failing the criteria means ELOC is not logged.

## Live plan (if approved and the criteria pass)
- **Frozen parameters:** the report's `live_fit` (`a`, `b`, from the seasons 2011 to 2025). Nothing
  is re-fitted or re-tuned live.
- **Shadow log:** `predictions/euroleague_eloc_2026-27.csv`, with its own `model_version`
  (`<package version>+eloc.<8 hex of sha256 of the frozen inputs>`). It is append-only, like every
  `predictions/` file, and it never replaces `predictions/euroleague_2026-27.csv` (the flagship Elo).
- **Not shown.** ELOC is not on the Forecasts page. It is not in `api/readmodel.py:FORECAST_MODELS`,
  and it is not the published forecast. A display would need a separate owner decision.
- **Switch:** `ELOC_LIVE_ENABLED = False` in `config.py`. `predict` writes nothing for ELOC until the
  flag is flipped (a separate, owner-approved commit). The flag is off on this branch.
- **Logging rule:** pre-tip-off, confirmed, unplayed games within the predict window only, the same
  guard as the Elo log (`refuse_late`). No backfill, so logging starts when the flag is flipped.
- **Judgement:** no promotion rule is declared here. Any use of ELOC beyond the shadow needs a new
  protocol, written and approved before the season it judges.
- **Disclosed:** the live Elo parameters were tuned on 2024 (2025 was Elo's test season), so the live
  fit's seasons include Elo's tuning and test seasons; on 2024 Elo's `d` is in-sample, which can pull
  `b` toward 1. Calibration selects nothing, but the overlap is stated.
- The hypothesis came from `docs/models/diag_home_court.md`, which looked at 2015–2025 and so includes
  the fold seasons: the idea was formed on the data that tests it.
- Elo's fixed parameters were tuned on 2024, after the folds. Both arms share them, so the paired gap
  stays fair.
- The 95% CI resamples only nine season clusters, so the percentile interval runs narrow (ELOR used
  the same method).
- Per-season or intercept-only (b = 1) fits are not tested: either would be a second arm, i.e.
  multiple testing. The reported per-fold `b` shows whether the slope matters.

## Run-once rule
- `eurohoops backtest --model eloc --cv` is the one-shot run. It refuses when `reports/eloc_cv.json`
  exists, when the working tree is not clean, and when HEAD is not `origin/main` (the ELOR and M5
  guards). It writes `reports/eloc_cv.json` and `reports/eloc_cv_games.csv` once.
- `eurohoops backtest --model eloc --cv-check` is read-only. It prints the game count per fold (fit
  and scored) and the live fit's game count. It fits nothing and scores nothing.
- Sanity check: the run aborts and writes nothing unless its scored games are ELOR's 2,535 and Elo's
  pooled log loss on them equals ELOR's (`reports/elor_cv.json` → `elo.log_loss`, 0.605151, to 6
  decimals). Both use the same replay, parameters and scored games.
- **No second run.** A change to any setting in this file is a new protocol (v2), declared and
  approved before it is run.

## What counts as failure
- The criteria fail: ELOC is not logged, and this is recorded as a negative result.
- Log loss is better but the CI is not non-inferior, or the mean is between -0.002 and 0: not a pass.
  ECE or Brier improvement alone is not a pass, because log loss is primary.
- A fit does not converge: the run aborts and writes nothing. That is a protocol failure, and it is
  reported as one. It is not retried with other settings.
- Shadow-only: a live `(a, b)` far from the folds' fits is a diagnostic to report, not a reason to
  re-fit.

## Leakage safeguards
- Fold s's `(a, b)` uses only the scored games of seasons fit_from to s-1. The test
  `tests/test_eloc_cv.py` checks that editing any game of season s or later leaves the fit of fold s
  unchanged, and that editing an earlier game does move it (the control).
- Elo's replay is causal: a game's `d` uses only games processed before it. Later edits do not move
  earlier `d`.
- The live forecast uses the `d` of upcoming games from ratings built on played games before them.
  Unplayed games never update ratings.
- The game's own result, later results, odds, injuries and rosters are not used.

## Owner decisions to approve
1. Calibration form: `sigmoid(a + b * logit(p_elo))`, fitted by unpenalised maximum likelihood.
2. Fit window: seasons 2011 to fold-1 for each fold; live fit 2011 to 2025.
3. Elo replay from 2007 with the published flagship's fixed parameters (k 20, hca 90, reversion 0.25).
4. Folds 2015 to 2023 (nine), including 2020 and 2021.
5. Criteria: margins of ±0.002 and the three-part rule above.
6. Live: frozen `(a, b)`, shadow log `predictions/euroleague_eloc_2026-27.csv`, not displayed, behind
   `ELOC_LIVE_ENABLED = False`.
