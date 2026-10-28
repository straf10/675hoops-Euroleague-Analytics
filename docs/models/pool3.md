# POOL3: the equal-weight pool of ELOR, M1 and M5 (live shadow)

Status: shadow, logging from merge (`POOL3_LIVE_ENABLED` is True in `config.py`). Spec: `experiments/pool3.md`. Idea: `docs/research/IDEAS.md` §C2. Baseline: POOL (`docs/models/pool.md`).

## What it is
**Question:** POOL gives Elo and ELOR equal weight, but ELOR is Elo plus a fading roster offset, so Elo counts twice. Does a pool without Elo forecast EuroLeague home wins better than POOL?

**Screen (the trigger).** `scripts/diag_pool3.py` (report `reports/diag_pool3.json`) measured the Pearson correlation of the Elo and ELOR logits over the 2026-27 finished games all four members logged before the spec commit (`82060b7`). The rule was above 0.98. On the refreshed marts the correlation was 0.9810 on 22 games, so POOL3 was declared.

**Model.** The equal-weight logarithmic pool of the three live models ELOR, M1 and M5, at their pinned versions (`config.POOL_COMPONENTS`):

    P_pool3 = sigmoid( (logit(P_ELOR) + logit(P_M1) + logit(P_M5)) / 3 )

Each probability is clipped to `[1e-6, 1 − 1e-6]` before the logit, as in POOL. The expected margin shown in the log is the equal-weight mean of the three margins. Code: `src/eurohoops/live_pool.py` (`predict_pool3`, the same code path as POOL with `members=("elor", "m1", "m5")` and `model="pool3"`).

**Rules, as POOL.** A game gets a row only when all three members logged it at their pinned versions, their fixtures agree, and the latest member stamp is strictly before tip-off. The row is stamped with that latest member stamp, so it never postdates a component. Rows are appended once per game and never rewritten. Nothing is tuned: the weights, the clip and the members are fixed.

**No lookahead.** A row depends only on its own game's three member rows. A later game's rows change no earlier row (`tests/test_pool3.py`, `test_pool3_no_lookahead_a_later_game_changes_no_earlier_row`).

## Results
No live results yet. The pass bar is the one in `experiments/pool3.md`: on the EuroLeague games logged after the merge through season end, the paired bootstrap of (POOL3 − POOL) log loss must have a 95% CI upper bound below 0. Replacing the published forecast still needs the standard test (`CLAUDE.md` rule 4).

| Quantity | Value | Report |
|---|---|---|
| Screen: games all four members logged | 22 | `reports/diag_pool3.json:n_games` |
| Screen: corr(logit Elo, logit ELOR) | 0.9810 (bar > 0.98) | `reports/diag_pool3.json:rule` |

## Files
- Spec (pass bar): `experiments/pool3.md`.
- Screen: `src/eurohoops/eval/pool3.py`, `scripts/diag_pool3.py`, report `reports/diag_pool3.json`.
- Forecast and shadow log: `src/eurohoops/live_pool.py` (`predict_pool3`), log `predictions/euroleague_pool3_2026-27.csv` (written only while `POOL3_LIVE_ENABLED` is True).
- Wiring: `config.py` (`POOL3_LIVE_ENABLED`, `POOL3_MEMBERS`, `pool3_prediction_log`), `cli/live.py` (`_predict_pool3`, and the `pool3` scorecard path), `eval/scorecard.py` (`pool3` trial section), `api/readmodel.py` (`FORECAST_MODELS` label `pool3`), `scripts/checks/api_export.py` (legacy site entry).
- Tests: `tests/test_pool3.py`, fixtures `tests/fixtures/pool3/`.
