# MKT: the bookmakers as a benchmark forecaster

Status: diagnostic (draft; not run on live games). MKT is a benchmark, not a published or bet-on forecast.

Pass bar: none for MKT itself. A model "adds information" when the 95% CI of its `logit(model)` coefficient in the encompassing regression excludes 0.

Season labels are start years: `2026` is 2026-27.

## What it is
**Question:** do the live EuroLeague models add home-win information that the bookmakers' pre-tip price lacks?

**MKT.** For a finished EuroLeague game `g` with a pre-tip snapshot:

    P_MKT(g) = p_home of the latest odds row of g fetched strictly before its tip-off

- `p_home` is the median over bookmakers of the proportionally de-vigged two-way home probability (`src/eurohoops/odds.py`, `devig_two_way`).
- A snapshot fetched at or after tip-off is ignored. A game with no pre-tip snapshot has no MKT row and is not scored.
- MKT is computed at read time from `odds/euroleague_2026-27.csv`. It is never written to `predictions/`, and no model imports it (`tests/test_benchmark.py`).

**Metric.** On games where both MKT and the model have a pre-tip row:
- mean per-game log loss and mean Brier score of each forecaster;
- the gap (model minus MKT) and its paired bootstrap 95% CI (10,000 resamples, seed 2026), for log loss and Brier.

**Encompassing test.** Logistic regression of home win on an intercept, `logit(MKT)` and `logit(model)`, with `logit(p) = log(p / (1 - p))` on `p` clipped to [1e-6, 1 − 1e-6]. Each coefficient has a 95% CI from the inverse Fisher information (normal approximation). Reported with at least 10 paired games.

**Lead-time buckets.** Log loss and Brier by snapshot lead time, the hours between the snapshot's fetch time and tip-off (lower bound included, upper excluded):
- `<3 h`: 0 to 3 h before tip-off;
- `3-24 h`: 3 to 24 h;
- `>=24 h`: 24 h or more.

**Evaluation data.** EuroLeague 2026-27 games from the owner's commit of this card, through season end.

**Report.** Per model (Elo, M1, M5, ELOR as logged): the gap table, the encompassing test, and the lead-time table. The script is `scripts/checks/mkt_benchmark.py`. It reads the live logs and writes JSON to stdout only.

**Facts and limits.**
- Snapshot timing varies. The latest pre-tip snapshot ranged from 0.6 h to 172 h before tip-off in the research notes. Results are reported by lead-time bucket.
- At 40 games so far, the encompassing CIs are wide.
- MKT is a scored model in the forecasts record. Once it is listed, the games shared by all compared models shrink to those with a pre-tip snapshot, and the shared figures for the other models change.
- API quota: the Odds API had 347 requests left at the last recorded call (IDEAS B1). The benchmark makes no API call. `odds.py` refuses calls below 20 remaining, checked against `odds/api_calls.csv`.
- No model uses the market price as an input (prior, blend or feature).

## Results
None yet. The benchmark has not been run on live 2026-27 games.

The season page's existing "Bookmakers" block (the closing line on games both the published model and the bookmakers called) is unchanged.

## Files
- Code: `src/eurohoops/odds.py`, `scripts/checks/mkt_benchmark.py`.
- Data: `odds/euroleague_2026-27.csv`, `odds/api_calls.csv`.
- Tests: `tests/test_benchmark.py`.
