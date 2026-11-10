# mref
Idea:      Compare each shadow with Elo, with the bookmakers' pre-tip probability as the reference instead of the result. This removes the result noise.
Type:      diagnostic
Baseline:  Elo
Backtest:  none (no historical odds). Live 2026-27 EuroLeague games that are finished and have a pre-tip odds snapshot.
Live:      no
Metric:    per game, cross-entropy of the model against the market: -(q ln p + (1-q) ln(1-p)), where q is the MKT probability (docs/models/mkt.md) and p is the model's logged probability. Paired gap = model minus Elo, on the games both logs share.
Pass bar:  scored only at the two checkpoints of CLAUDE.md rule 4 (after EuroLeague round 19, and at season end), on rounds up to the checkpoint. A model "is closer to the market than Elo" when the mean paired gap < 0 and the upper bound of the paired-bootstrap 97.5% CI (10,000 resamples) < 0, with at least 100 shared games. Before a checkpoint is complete, the script reports only n and the standard deviation of the paired gap, never the mean or the CI. The result promotes nothing.
Result:    (step 7)
