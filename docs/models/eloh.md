# Elo with a per-team home advantage (ELOH): a live shadow

Status: shadow, fitted and frozen; logging is off until `ELOH_LIVE_ENABLED` is set in `config.py` (the orchestrator flips it). Spec and pass bar: `experiments/eloh.md`. Idea: `docs/research/IDEAS.md` §D2.

## What it is
**Question:** does a per-team home-court advantage, shrunk toward zero, forecast EuroLeague home wins better than live Elo's single home-court value (`hca` 90)? Background: `docs/models/diag_home_court.md` found no shared home-court shortfall in 2024-25, but teams may differ.

**Model.** Live Elo (k 20, hca 90, reversion 0.25, same margin scale, same replay start) with one change: a game's home-court advantage is `hca_team = 90 + δ_home`, where `δ_home` is the home team's frozen shift. Neutral games keep 0, as in Elo. Code: `src/eurohoops/live_eloh.py` (forecast), `src/eurohoops/models/eloh.py` (fit), `src/eurohoops/models/elo.py` (`replay` takes an optional per-game `home_hca`; the default is unchanged).

**Fit (once, frozen).** `scripts/fit_eloh.py`, EuroLeague 2007-08 to 2023-24 only:
1. Replay frozen live Elo over those games. For each rated home game (played, not forfeit, not neutral), the residual is `e = home win − p_home` with the pre-game `p_home`.
2. Per home team: `ē` is the mean residual over `n` home games, `s² = mean(p(1 − p)) / n`.
3. `τ² = max(0, var(ē) − mean(s²))`, with `var` the sample variance (ddof 1) across teams (method of moments).
4. Shrink: `B = τ² / (τ² + s²)`, and `δ = B·ē / (ln10/400 · p̄(1 − p̄))` in Elo points, with `p̄` the team's mean home `p_home`. A team with no rated home game in the fit seasons gets `δ = 0`.

The fit is written to `reports/eloh_fit.json` and never refitted. The script refuses to run if that file exists.

**Limits.** The residuals are not centred: the mean `ē` across teams is +0.013 (home teams won more often than Elo expected), and shrinkage is toward 0, not toward that mean. So ELOH does not correct a league-wide home-court shortfall; it only moves teams relative to the one hca. Most teams have few home games (median 28 over the fit seasons), so their `s²` is large and `B` is small.

## Results
Fit only. There are no live results yet. Scoring is the standard test at the EuroLeague checkpoints (after round 19 and at season end), against live Elo, as `experiments/eloh.md` sets.

| Quantity | Value | Report |
|---|---|---|
| Fit seasons | 2007-08 to 2023-24 | `eloh_fit.json:fit_seasons` |
| Elo parameters (frozen live) | k 20, hca 90, reversion 0.25 | `eloh_fit.json:elo_params` |
| Teams with a rated home game | 63 | `eloh_fit.json:teams_fitted` |
| Rated home games | 4,244 | sum of `teams[*].n` |
| Variance of ē across teams (ddof 1) | 0.020464 | `eloh_fit.json:var_residual_ddof1` |
| Mean sampling variance s² | 0.017345 | `eloh_fit.json:mean_sampling_var` |
| τ² | 0.003119 | `eloh_fit.json:tau2` |
| Largest \|δ\|: CSK | +58.45 (n 200, B 0.792) | `eloh_fit.json:teams.CSK` |
| Largest \|δ\|: MAD | +55.72 (n 247, B 0.811) | `eloh_fit.json:teams.MAD` |
| Largest \|δ\|: OLY | +52.14 (n 243, B 0.787) | `eloh_fit.json:teams.OLY` |
| Largest \|δ\|: BER | −50.11 (n 113, B 0.600) | `eloh_fit.json:teams.BER` |
| Largest \|δ\|: BAR | +41.56 (n 248, B 0.810) | `eloh_fit.json:teams.BAR` |

τ² is small against the sampling noise: the largest B is about 0.8, and each team with 13 or fewer home games has B between 0.06 and 0.15. The values are reproducible from the mart and `scripts/fit_eloh.py`.

## Files
- Experiment spec (pass bar): `experiments/eloh.md`.
- Fit: `scripts/fit_eloh.py`, `src/eurohoops/models/eloh.py`; frozen output `reports/eloh_fit.json`.
- Forecast and shadow log: `src/eurohoops/live_eloh.py`, log `predictions/euroleague_eloh_2026-27.csv` (written only when `ELOH_LIVE_ENABLED` is True).
- Wiring: `config.py` (`ELOH_LIVE_ENABLED`, `ELOH_FIT`, `ELOH_FIT_SEASONS`), `cli/live.py` (`_predict_eloh`), `eval/scorecard.py` (`eloh` section), `api/readmodel.py` (`FORECAST_MODELS` label), `scripts/checks/api_export.py` (legacy site entry).
- Tests: `tests/test_eloh.py`, fixtures `tests/fixtures/eloh/`.
