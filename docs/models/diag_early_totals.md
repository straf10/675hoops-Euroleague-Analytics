# Diagnostic: early-season totals bias, market line and M1 (B2)

Status: draft, not committed by the owner. Diagnostic only. Nothing here changes M1, M5, the
live loggers, `predictions/` or `odds/`. Script (to be written after this card is committed):
`scripts/diag_early_totals.py`. Report (not produced yet): `reports/diag_early_totals.json`.
Source idea: `docs/research/IDEAS.md` B2 (research notes are untracked; see the owner's copy).

## Question
Do EuroLeague totals run high early in the season? Specifically, in EuroLeague rounds 1–5, is
the market total (and M1's total) above the actual total by more than chance, and does that gap
disappear in rounds 11 and later? The question comes from NBA evidence (baryla-2007: totals lines
run high early, the bias fades by about the 10th home game). It is not yet shown to hold in
EuroLeague.

## Data and definitions
- **Season:** EuroLeague 2026-27 (the first season the odds and M1 logs cover). The rule is
  stated for that season only; any later season is a new declaration.
- **Games:** EuroLeague regular season only (`phase` = RS), played, not a forfeit, with a
  result. Playoff games are not in any bucket.
- **Buckets:** by EuroLeague round number: 1–5, 6–10, 11+ (11 up to the last regular-season
  round). Round numbers, not calendar weeks; double-round weeks count as two rounds.
- **Actual total:** home score + away score, from the games mart.
- **Line (market total):** from `odds/euroleague_2026-27.csv`. The line of a game is the row with
  the latest `fetched_at_utc` that is strictly before the game's `tipoff_utc`. If that row has no
  total (blank `total`), the game has no line. Earlier snapshots are not used as a fallback.
  Rows fetched at or after tip-off are ignored, whatever their total.
- **M1 total:** `exp_total` of the scored M1 row in `predictions/euroleague_m1_2026-27.csv`. The
  scored row is the same one the forecast record uses (`eval/forecasts.py`, `_provable`): the
  latest row stamped before tip-off, of the earliest M1 `model_version` that logged the game,
  excluding rows that only became public at or after tip-off (manual-push rule in
  `config.py`). Rows stamped at or after tip-off never count. A game with no such row has no
  M1 total.
- **Sample:** for each bucket, the games that have a line, an M1 total and a result. Both metrics
  use this same sample, so the line and M1 numbers compare like with like. Games missing either
  input are counted and listed in the report, not dropped silently.

## Metrics
Per game: `line − actual` and `M1 total − actual`. Per bucket, the mean of each, with a 95%
bootstrap CI:
- **Resamples:** 10,000, games resampled with replacement within the bucket.
- **Seed:** 20261022 (numpy `default_rng`).
- **CI:** percentile interval, 2.5th and 97.5th percentiles of the resampled means.
- **Sign:** positive means the total runs above the actual result.

## Rule (declared before any result is computed)
"Early-season bias present" is declared, **separately for the line and for M1**, if:
- the rounds 1–5 95% CI lies **entirely above 0** (the total, line or M1, runs above the actual
  total), **and**
- the rounds 11+ 95% CI does not exclude 0.

The CI is the two-sided 95% interval described above (not one-sided).

A rounds 1–5 CI lying **entirely below 0** is reported as "early shift, opposite direction". This
is descriptive only: it is not the bias, and it does not declare anything.

Rounds 6–10 are reported and have no role in the rule.

## Risks and power
- **Low power.** A 5-round bucket holds about 45 EuroLeague games (18 teams, 9 games per round).
  The CI half-width is about 1.96 × SD / √45 ≈ 0.29 × SD, where SD is the per-game SD of
  `total − actual`. That SD is not known from this card; it is computed from the owner's data
  only after the owner commits this rule. Only a bias several points wide can be detected in one
  season.
- **One season.** A bias cannot be separated from a season-level scoring shift (league-wide
  pace or rule changes). A result of "present" is a diagnostic flag, not evidence of a cause.
- **Small line sample.** Games with no line before tip-off, or with a blank total, leave the
  bucket. The count of such games is reported per bucket.
- **Line and M1 are not independent.** M1's pace model and the market both see the same early
  results, so the two verdicts can agree for the same reason.

## Shadow model (not part of this card)
A model fix (for example a faster-decay or early-season pace prior) is **not** tested here.
If the rule declares a bias, any fix would be a separate shadow model, with its own
pre-registered gate, tested on the 2027-28 season start (the next early-season window with
fresh data). M1 and M5 are not re-tuned on any split used for their gates (PLAN §8.1).

## Declaration
- Rule committed by the owner: pending (this card is a draft).
- Command (not run yet): `uv run python scripts/diag_early_totals.py --season 2026`.
  It reads `data/marts/eurohoops.duckdb`, `odds/euroleague_2026-27.csv` and
  `predictions/euroleague_m1_2026-27.csv` read-only, and writes only the report JSON.
- The script is not run on live 2026-27 data until the owner has committed this rule.

## Owner decisions (2026-10-23)
1. **Sign.** The early-bias rule requires the rounds 1–5 95% CI to lie entirely above 0 (line or
   M1 total higher than actual). A rounds 1–5 CI entirely below 0 is reported as "early shift,
   opposite direction" (descriptive, not the bias). The two-sided 95% CI is kept.
2. **Blank total.** A blank total in the latest pre-tip snapshot gives no line, with no fallback
   to an earlier snapshot.
3. **Playoffs.** Playoff games are excluded from all buckets.

Status of the card is unchanged: draft, not committed by the owner.
