# Elo with a roster prior (ELOR): Elo plus a preseason roster rating

Status: live shadow (logged daily to `predictions/euroleague_elor_2026-27.csv`; shown on the Forecasts page as "Roster Elo (trial)"; never the published forecast).

Judged by the standard promotion test (CLAUDE.md rule 4).

## What it is
Elo's ratings are regressed 25% toward 1500 each summer and otherwise ignore roster changes. ELOR blends a roster-based preseason rating into Elo at the start of a season, and fades it out over the first rounds.

**Formula.** For team `t` in season `s`, round `r` (`r` = 1 is the first round):

    w(r)      = w0 * max(0, 1 - (r - 1) / N)          # blend weight, fades to 0 after N rounds
    B_t(r)    = R_t(r) + w(r) * (P_t - R_t(start))      # blended rating
    d_g       = B_home(r) - B_away(r) + (0 if neutral else hca)

- `R_t(r)` is live Elo's pre-game rating. Its updates are untouched, so ELOR differs from Elo only through the fading offset.
- `R_t(start)` is Elo's season-start rating after reversion. At `r` = 1 the blended start is `(1 - w0) * R_t(start) + w0 * P_t`.
- `w0 = 0` is exactly live Elo.
- Win probability: `elo.win_probability(d_g)`, with k 20, hca 90, reversion 0.25.

**Roster rating `P_t`** (Elo points):
- The M3 player part `rapm_spm` (`reports/backtest_m3.json`; built by `_m5_player_part_el` in `src/eurohoops/cli/backtest.py`), weighted by projected minute shares. Shares come from `models/minutes.py:projected_shares` or `models/rotation.py:projected_shares_variant`, from box scores before the cutoff.
- Roster for a game: players (`type == "J"`) listed for the club in the cached season roster list `data/raw/euroleague/people/E{season}.json.gz` (`ingest/bios.py`), whose `startDate` is before the game's cutoff and whose `endDate` (if any) is after it. Mid-season signings enter from their start date.
- A registration stamped during round 1 counts from its own `startDate`, so that player joins from round 2.
- Players with no M3 rating or no minute share get the newcomer prior (below).
- The margin is converted to Elo points with `elo.fit_margin_scale`, fitted on earlier seasons only. `P_t` is centred on the league mean in that season, so it moves teams relative to each other, not the league level.
- `P_t` is evaluated at each game's cutoff. A game without M3 state, expected possessions or a margin scale keeps live Elo.
- `models/turnover.py:roster_continuity` is available as a diagnostic only.

**Cutoffs:** `models/minutes.py:round_cutoffs` gives each game's information cutoff. Roster shares and `P_t` use only box scores with tip-off before that cutoff. M3 ratings are walk-forward: each game's player part comes from the fit on games before its cutoff.

**Newcomer prior.** A first-season newcomer of season `t` is a player whose first seconds in the EuroLeague box data (from 2007) are in season `t`. History runs from 2008.
- *Rating prior:* `anchor(s) + pooled_gap(s)`. `anchor(s)` is the previous season's weighted mean O + D over all rated players. `gap(sigma)` is the newcomers' weighted mean minus the all-player weighted mean, in season `sigma`'s season-end fit. `pooled_gap(s)` is the newcomer-weighted average of the gaps over earlier seasons. The prior is NaN if a part is missing.
- *Share prior:* the mean, over newcomer team-games, of `min(1, 5 x his seconds / the team's seconds)`, from his first to his last appearance with the club in season `t`. A game he sat out counts 0.
- A player's own rating or share replaces the prior as soon as the rules give him one. A rating counts only once he has played before the cutoff.
- Team shares above a total of 5 are scaled down to 5.
- Both priors use seasons before `s` only.

**Parameters.** Searched: `w0` in {0.2, 0.35, 0.5} and `N` in {4, 8, 16, 24} rounds, 12 settings. Fixed: k 20, hca 90, reversion 0.25, the M3 parameters, the minute-share variant (`projected_shares_variant` default), and the margin scale (refit per fold on earlier seasons). Live Elo is the reference, scored on the same folds, and is not a grid point. Simplicity order for the one-SE rule: smaller `w0` first, then smaller `N`.

**Folds and scoring.** Rolling origin by season, expanding window. Scored seasons 2015 to 2023 (nine folds, including the 2020 and 2021 COVID seasons). The ratings warm-up runs from 2007. Seasons 2024-25 and 2025-26 are in no fold. Scored games are played, not forfeit, not neutral: 2,535 (the 2,567 rated fold games of the M5 retune minus 32 neutral games). Score: pooled log loss of P(home win). Brier is reported too.

**Selection.** The lowest pooled log loss is the best. The SE of each setting's gap to the best is the SD (ddof 1) of the game-weighted pooled gap over 10,000 whole-season resamples (seed 20261015). The one-SE rule picks the simplest setting within one SE of the best.

**Criteria** (all three): (1) selected pooled log loss below live Elo's on the nine folds; (2) upper end of the 95% season-bootstrap CI of the selected-minus-Elo difference below +0.002; (3) mean difference -0.002 or lower.

**Live.** Replays Elo from 2007 with fixed parameters, as the CV did (not from the published log's 2023 start). On the 2026 games the two differ by 0.0015 in mean absolute win probability (max 0.0083). Setting: `w0` 0.5 and `N` 24, read from `reports/elor_cv.json`, logged only while that report's `shadow_criteria.all` is true. `exp_margin` is the blended difference divided by the season's margin scale. Inputs: M5's live frame and M3 walk-forward fit (shared with the M5 log in one run), the live season's cached roster list (refreshed daily by `eurohoops people`), and the 2026 newcomer prior from that fit.

**Limits.** The folds are not clean: 2015 to 2023 were seen during earlier model work, and the long-history Elo run tuned on them. The live Elo parameters were chosen on 2024. The baseline is live Elo with fixed parameters, which favours the baseline on these folds. Roster lists record registration, not availability: an injured or unused registered player counts at projected minutes, and `startDate` stamps may lag the real signing.

## Results
**Roster start-date counts, 2015 to 2023** (player rows of each season's roster list; "after round 1 began" means `startDate` at or after the first tip-off; "during round 1" also before the second round's cutoff).

| Season | Players | After round 1 began | During round 1 | Of those, played before stamp |
|---|---|---|---|---|
| 2015 | 391 | 38 | 0 | 0 |
| 2016 | 278 | 45 | 0 | 0 |
| 2017 | 277 | 35 | 1 | 0 |
| 2018 | 279 | 44 | 7 | 0 |
| 2019 | 326 | 55 | 2 | 0 |
| 2020 | 368 | 86 | 3 | 0 |
| 2021 | 328 | 48 | 5 | 0 |
| 2022 | 326 | 46 | 1 | 0 |
| 2023 | 320 | 42 | 0 | 0 |

Totals: 2,893 rows, of which 19 are stamped during round 1, and none of those players had already played for that club.

**Fold results** (`reports/elor_cv.json`, `reports/elor_cv_games.csv`)
- 2,535 scored games, folds 2015–2023, strict first-round rule.
- Live Elo pooled log loss 0.605151 (Brier 0.208911). Selected setting `w0.5|n24`: 0.602833 (Brier 0.207873).
- Selected minus Elo: mean −0.002318, 95% CI [−0.004282, −0.000686].
- All three criteria pass.
- The selected setting is the best and the only one within one SE. Log loss improves steadily with more weight and a longer fade, so the best sits on the grid corner (`w0` 0.5, `N` 24). The true optimum may lie beyond the grid.
- Per season, ELOR beats Elo in 7 of 9 folds (not 2016 or 2017).
- With `N` 24 the blend stays active until round 24, so the live log differs from Elo for most of the regular season.

## Files
- Code: `src/eurohoops/models/elor.py`, `src/eurohoops/models/roster.py`, `src/eurohoops/eval/elor_cv.py`, `src/eurohoops/live_elor.py`, `src/eurohoops/config.py` (`ELOR_ELO_PARAMS`, `ELOR_CV`, `elor_prediction_log`).
- Command: `eurohoops backtest --model elor --cv` (run once), `--cv-check` (counts only).
- Roster input: `data/raw/euroleague/people/E{season}.json.gz`.
- Reports: `reports/elor_cv.json`, `reports/elor_cv_games.csv`, `reports/backtest_m3.json`.
- Log: `predictions/euroleague_elor_2026-27.csv` (`model_version` `0.2.0+elor.<hash>`).
