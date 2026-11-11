# mref: each shadow against Elo, with the market as reference

Status: diagnostic. Research only. It promotes nothing and never goes live.

Spec: `experiments/mref.md`.

## What it is
The result of a game is noisy. This diagnostic scores each live shadow against the bookmakers instead. The market is the reference, not the result.

**MKT.** For a finished EuroLeague game with a pre-tip snapshot, `q` is the market's `p_home`: the latest odds row fetched strictly before tip-off (`docs/models/mkt.md`). A snapshot at or after tip-off is ignored.

**Metric.** Per game, the cross-entropy of a model against the market:

    -(q ln p + (1 - q) ln(1 - p))

`p` is the model's logged `p_home`, clipped to [1e-6, 1 - 1e-6]. The paired gap is the model's value minus Elo's value on the same game.

**Games.** Finished, non-forfeit games with a pre-tip odds row and a scored row in both the model log and the Elo log.

**Logged rows.** The script takes each model's row, and Elo's, with `eval.forecasts._calls`: the rule of the public forecast record. That is the earliest model version's latest row stamped before tip-off. Late rows are dropped. `promote-check` (`promotion.pair_logs`) uses the latest model version instead, so the two can differ for a shadow whose version changed.

## Pass bar
Scored only at the two checkpoints of CLAUDE.md rule 4: after EuroLeague round 19, and at season end. Look 1 uses regular-season rounds up to round 19. Look 2 covers the whole season, all phases, with forfeits excluded, as in `promotion.run_look`.

A model "is closer to the market than Elo" when the mean paired gap is below 0, and the upper bound of the paired-bootstrap 97.5% CI (10,000 resamples) is below 0, with at least 100 shared games.

"closer" is this diagnostic's own bar. It is not the standard promotion test of CLAUDE.md rule 4, which also needs a mean gap of -0.01 or lower on the result-based log loss. It promotes nothing.

Before a checkpoint is complete, the report gives only `n` and the standard deviation of the gap.

## Files
- Code: `src/eurohoops/eval/mref.py`.
- Script: `scripts/diag_mref.py` (`--look 1` or `--look 2`). Writes `reports/diag_mref.json` only.
- Tests: `tests/test_mref.py`.

## Results
Look 1 is not due: 90 games of rounds 1-19 are not played yet. The first report (`reports/diag_mref.json`) gives only n and the SD of the gap: M1 51 games (SD 0.0135), M5 41 (0.0310), M5-INJ 20 (0.0473), ELOH 14 (0.0227). No mean, CI or verdict is reported yet.

At about 5 shared games per round for M1, the 100-game minimum is not certain to be met at Look 1. A model with fewer than 100 shared games gets "not testable".
