# MKT: the bookmakers as a benchmark forecaster (gate, draft)

**Status: draft, not committed by the owner.** Nothing below is in force until the owner commits it.
Drafted from `docs/research/IDEAS.md` section B1. The gate is declared before the season-end look
and before any evaluation on the games it covers.

Season labels are start years: `2026` is 2026-27.

## Question
Do the live EuroLeague models add home-win information that the bookmakers' pre-tip price lacks?
MKT is a benchmark, not a forecaster we publish or bet on. It carries no pass rule.

## Model: MKT
For a finished EuroLeague game g with a pre-tip snapshot:

    P_MKT(g) = p_home of the latest odds row of g fetched strictly before its tip-off

- `p_home` is the median over bookmakers of the proportionally de-vigged two-way home
  probability (`src/eurohoops/odds.py`, `devig_two_way`). The de-vig needs no change.
- The snapshot is the latest one fetched strictly before tip-off. A snapshot fetched at or after
  tip-off is ignored. A game with no pre-tip snapshot has no MKT row, so it is not scored.
- MKT is **computed at read time** from `odds/euroleague_2026-27.csv`. It is never written to
  `predictions/`, and no model imports it (`tests/test_benchmark.py` checks this).
- GBL: no odds, so MKT is absent there.

## Metric
On the games where both MKT and the model have a pre-tip row:
- mean per-game log loss and mean Brier score of each forecaster;
- the gap (model minus MKT) and its paired bootstrap 95% CI (10,000 resamples, seed 2026), for
  both log loss and Brier.

## Evaluation data
EuroLeague 2026-27 games played after the gate commit, through season end. Games logged or
played before the gate commit are not in the gate.

## Report
1. The gap table above, per model (Elo, M1, M5, ELOR as logged).
2. The encompassing test, per model: a logistic regression of home win on an intercept,
   logit(MKT) and logit(model), with `logit(p) = log(p / (1 - p))` on p clipped to [1e-6, 1 − 1e-6].
   Each coefficient has a 95% CI from the inverse Fisher information (normal approximation).
   Reported only with at least 10 paired games.
3. The same log-loss and Brier scores by **snapshot lead time**, the hours between the snapshot's
   fetch time and tip-off. Buckets (lower bound included, upper excluded):
   - `<3 h`: 0 to 3 h before tip-off;
   - `3-24 h`: 3 to 24 h;
   - `>=24 h`: 24 h or more.

The benchmark script is `scripts/checks/mkt_benchmark.py`. It reads the live logs and writes JSON
to stdout only. It is not run on live games until the owner commits this gate.

## Pass rule
None. This is a benchmark. It sets no promotion, no selection and no multiplicity.

**"Model adds information"** is declared for a model when the 95% CI of its logit(model)
coefficient in the encompassing regression excludes 0. The sign of the coefficient gives the
direction. The MKT coefficient is reported but does not decide anything.

## Risks
- **Snapshot timing varies.** The latest pre-tip snapshot ranged from 0.6 h to 172 h before tip-off
  in the research notes. Results are reported by lead-time bucket, so a model that looks good on
  late prices can be separated from one that looks good on early prices.
- **Sample size.** At 40 games so far, the encompassing CIs are wide. A failed "adds information"
  declaration at this size is not evidence that the model adds nothing.
- **Shared basis shrinks.** MKT is a scored model in the forecasts record, so the page's shared
  games (the games every compared model logged) can only include games with a pre-tip snapshot.
  Shared figures for the other models change once MKT is listed.
- **API quota.** The Odds API had 347 requests left at the last recorded call (IDEAS B1). The
  benchmark makes no API call. Any new odds fetch must first check the quota in
  `odds/api_calls.csv`, and `odds.py` refuses calls below 20 remaining.
- **MKT must never feed a model without its own gate.** Using the market price as an input
  (a prior, a blend, a feature) is a new model and needs its own gate, pre-registered before use.

## Not done here
- No run of the benchmark on live 2026-27 games. This card is the draft only.
- No change to `odds.py`, to the odds log, or to any `predictions/` file.
- The season page's existing "Bookmakers" block (the closing line on the games both the published
  model and the bookmakers called) is unchanged.
