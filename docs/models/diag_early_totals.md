# Diagnostic: early-season totals bias, market line and M1 (B2)

Status: diagnostic (draft; the script has not been run on live 2026-27 data). It changes nothing in M1, M5, the live loggers, `predictions/` or `odds/`.

Pass bar: "early-season bias present", separately for the line and for M1, when the rounds 1–5 95% CI lies entirely above 0 and the rounds 11+ 95% CI does not exclude 0.

## What it is
**Question:** do EuroLeague totals run high early in the season? Specifically, in rounds 1–5, is the market total (and M1's total) above the actual total by more than chance, and does that gap disappear in rounds 11 and later? The question comes from NBA evidence (baryla-2007: totals lines run high early, and the bias fades by about the 10th home game). It is not yet shown for EuroLeague.

**Data and definitions.**
- Season: EuroLeague 2026-27 (the first season the odds and M1 logs cover). The rule is stated for that season only.
- Games: EuroLeague regular season only (`phase` = RS), played, not a forfeit, with a result. Playoff games are in no bucket.
- Buckets by round number: 1–5, 6–10, 11+ (up to the last regular-season round). Double-round weeks count as two rounds.
- Actual total: home score + away score, from the games mart.
- Line: from `odds/euroleague_2026-27.csv`, the row with the latest `fetched_at_utc` strictly before the game's `tipoff_utc`. A blank `total` in that row means no line. There is no fallback to earlier snapshots. Rows fetched at or after tip-off are ignored.
- M1 total: `exp_total` of the scored M1 row in `predictions/euroleague_m1_2026-27.csv`. The scored row is the latest row stamped before tip-off, from the earliest M1 `model_version` that logged the game (`eval/forecasts.py`, `_provable`). Rows that only became public at or after tip-off are excluded (manual-push rule in `config.py`). A game with no such row has no M1 total.
- Sample: for each bucket, the games that have a line, an M1 total and a result. Both metrics use this same sample. Games missing either input are counted and listed in the report.

**Metrics.** Per game: `line − actual` and `M1 total − actual`. Per bucket, the mean of each with a 95% bootstrap CI: 10,000 resamples within the bucket, seed 20261022 (numpy `default_rng`), percentile interval (2.5th and 97.5th percentiles of the resampled means). The interval is two-sided. Positive means the total runs above the actual result.

**Rule.** "Early-season bias present" is flagged separately for the line and for M1 when:
- the rounds 1–5 CI lies entirely above 0, **and**
- the rounds 11+ CI does not exclude 0.

A rounds 1–5 CI entirely below 0 is reported as "early shift, opposite direction". This is descriptive only. Rounds 6–10 are reported and play no part in the rule.

**Power.** A 5-round bucket holds about 45 EuroLeague games (18 teams, 9 games per round). The CI half-width is about 1.96 × SD / √45 ≈ 0.29 × SD, where SD is the per-game SD of `total − actual`. Only a bias several points wide can be detected in one season.

**Limits.**
- One season: a bias cannot be separated from a season-level scoring shift (league-wide pace or rule changes). "Present" is a diagnostic flag, not evidence of a cause.
- Games with no line before tip-off, or with a blank total, leave the bucket. The count is reported per bucket.
- Line and M1 are not independent: M1's pace model and the market see the same early results, so their verdicts can agree for the same reason.

**Scope.** Model fixes (for example a faster-decay or early-season pace prior) are not tested here.

**Command.** `uv run python scripts/diag_early_totals.py --season 2026`. It reads `data/marts/eurohoops.duckdb`, `odds/euroleague_2026-27.csv` and `predictions/euroleague_m1_2026-27.csv` read-only, and writes only the report JSON.

## Results
None yet.

## Files
- Script: `scripts/diag_early_totals.py` (to be run).
- Report: `reports/diag_early_totals.json` (not produced yet).
- Inputs: `data/marts/eurohoops.duckdb`, `odds/euroleague_2026-27.csv`, `predictions/euroleague_m1_2026-27.csv`, `src/eurohoops/eval/forecasts.py`, `src/eurohoops/config.py`.
