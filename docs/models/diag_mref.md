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

## Pass bar
Scored only at the two checkpoints of CLAUDE.md rule 4: after EuroLeague round 19, and at season end. Look 1 uses rounds up to round 19.

A model "is closer to the market than Elo" when the mean paired gap is below 0, and the upper bound of the paired-bootstrap 97.5% CI (10,000 resamples) is below 0, with at least 100 shared games.

Before a checkpoint is complete, the report gives only `n` and the standard deviation of the gap.

## Files
- Code: `src/eurohoops/eval/mref.py`.
- Script: `scripts/diag_mref.py` (`--look 1` or `--look 2`). Writes `reports/diag_mref.json` only.
- Tests: `tests/test_mref.py`.

## Results
None yet. Look 1 not due.
