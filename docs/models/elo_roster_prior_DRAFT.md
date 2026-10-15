# DRAFT – not approved, not run

**Elo with a roster-prior blend (shadow model proposal).** Written 2026-10-15 for the owner to
approve or reject. No code is written for it, no CV is run, nothing is logged. Approval of this
file would authorise the protocol below, not the model.

## Question
Elo (`src/eurohoops/models/elo.py`, card `docs/models/elo.md`) regresses every rating 25% toward
1500 each summer and otherwise ignores roster changes. A team that lost its main scorers, or
signed several, starts the season with a rating that reflects last year's team. This proposal
tests whether a roster-based preseason rating, blended in at the start of a season and faded out
over the first rounds, improves EuroLeague home-win log loss over live Elo.

## Components (existing code, reused)
- **Elo state:** `elo.replay` (pre-game rating differences) and `elo.season_ratings`, which returns
  each team's current rating and its rating at the season start after reversion. The live
  parameters stay fixed: k 20, hca 90, reversion 0.25. Elo is not re-tuned inside this proposal.
- **Roster rating P_t (Elo points):** the M3 player part, `rapm_spm` (committed in
  `reports/backtest_m3.json`, the same player part M5 uses; built by `_m5_player_part_el` in
  `src/eurohoops/cli.py`), weighted by the team's projected minute shares. Shares come from
  `models/minutes.py:projected_shares` or `models/rotation.py:projected_shares_variant`, computed
  from box scores before the season-start cutoff. Roster turnover is handled by
  `models/turnover.py:roster_continuity` (player-minute continuity; see the limits below).
  The margin is converted to Elo points by `elo.fit_margin_scale`, fitted on earlier seasons only.
  P_t is centred on the league mean of P in that season, so the blend moves teams relative to
  each other, not the league level.
  Note: `_m5_player_part_el` is private to `cli.py`. An implementation would need to move it
  into `models/`. That is out of scope for this draft.
- **Cutoffs:** `models/minutes.py:round_cutoffs` gives each game's information cutoff.

## Formula
For team t in season s, round r (r = 1 is the first round of the season):

    w(r)      = w0 * max(0, 1 - (r - 1) / N)          # blend weight, fades to 0 after N rounds
    B_t(r)    = R_t(r) + w(r) * (P_t - R_t(start))      # blended rating
    d_g       = B_home(r) - B_away(r) + (0 if neutral else hca)   # pre-game difference, game g

- `R_t(r)` is live Elo's own pre-game rating for team t at round r. Its updates are untouched, so
  the shadow differs from live Elo only through the fading offset.
- `R_t(start)` is live Elo's season-start rating after reversion. `P_t - R_t(start)` is the
  gap between the roster rating and Elo's start, so at r = 1 the blended start is
  `(1 - w0) * R_t(start) + w0 * P_t`, the blend described in the question.
- `w0` is the blend weight at the start, `N` the fade length in rounds. `w0 = 0` is exactly live Elo.
- The win probability is `elo.win_probability(d_g)`, with the live k, hca and reversion.

## Parameters and grid (12 settings)
Searched: `w0` in {0.2, 0.35, 0.5} and `N` in {4, 8, 16, 24} rounds, giving 12 settings.
Fixed, not searched: k 20, hca 90, reversion 0.25, the M3 parameters, the minute-share variant
(`projected_shares_variant` default), the margin scale (refit per fold on earlier seasons only).
Live Elo is the reference, scored on the same folds with the same code. It is not a grid point.

**Simplicity order** (for the one-SE rule): smaller `w0` is simpler, and among equal `w0` a
smaller `N` is simpler.

## Protocol
Same structure as the M5 retune protocol (`docs/models/m5.md`, "Retune protocol v1"):
- **Folds: rolling-origin by season, expanding window.** Scored seasons are 2015 to 2023 (nine
  folds). The ratings warm-up runs from 2007, and the margin scale and M3 ratings use only
  seasons before each fold. Seasons 2024-25 and 2025-26 (the live tuning and test seasons) are in
  no fold. No random or game-level splits.
- **Scored games:** played, not forfeit, not neutral (as in `scripts/diag_home_court.py`).
- **Score:** pooled log loss of P(home win) over the nine folds. Brier is reported too.
- **Selection:** the setting with the lowest pooled log loss is the best. The SE of each setting's
  gap to the best is the standard deviation of the paired difference over 10,000 resamples of
  **whole seasons**. Seed: proposed 20261015, to be fixed at approval.
- **One-SE rule:** choose the simplest setting whose pooled log loss is within one SE of the
  best. Live Elo is not a grid point, so the rule always returns a blend setting; whether that
  blend beats Elo is decided by the criteria below.
- **Reported:** pooled and per-season log loss, Brier and the 12 settings; the selected setting
  and its one-SE band; the paired season-bootstrap difference (selected minus live Elo) with a
  95% CI; the number of settings within one SE; game counts per fold.
- **Stopping rule:** one run on a committed commit, with the grid, folds, simplicity order and
  criteria fixed before the first fold is scored. No second run.

**Disclosed limits.** The folds are not clean: the 2015 to 2023 seasons were seen during earlier
model work, and the long-history Elo run (`reports/backtest_elo_history.json`) tuned on them.
The live Elo parameters were chosen on 2024 only. The baseline is
live Elo with fixed parameters, which favours the baseline on these folds. The 2020 and 2021
seasons (COVID) are kept as the M5 protocol kept 2019, with the open question below.
Roster turnover is inferred from who has played: there are no historical signed-roster lists,
and the feature is empty before a team's first games (it then falls back to P_t = R_t(start),
so the blend has no effect).

## Criteria to start a shadow (proposed, the owner decides)
All three needed, as in the M5 retune protocol:
1. The selected setting's pooled log loss is below live Elo's on the same nine folds.
2. Non-inferiority: the upper end of the 95% season-bootstrap CI of the pooled log-loss
   difference (selected minus live Elo) is below +0.002.
3. Worth a version: the mean difference is −0.002 or lower.

Superiority is reported, not required.

## Shadow logging (if approved)
- A new separate file: `predictions/euroleague_elor_2026-27.csv`, with its own `model_version`
  (for example `0.2.0+elor.<hash>`). It never replaces `predictions/euroleague_2026-27.csv`
  (Elo), is never shown on the site, and is never the published forecast.
- Logged daily from the first CI run after the merge, with no backfill. Append-only, like every
  `predictions/` file.
- Judged at the existing R1 promotion look (`docs/models/m5.md`, "Flagship promotion rule"). The
  R1 rule is written for M5 against Elo, so the owner must confirm in writing that this arm is
  added to the look report as a third comparison. Its promotion rule is declared separately
  before 2027-28, as for the retuned M5. R1 is not changed by this proposal.

## Leakage safeguards
- Season-start ratings (`R_t(start)`) and the blend weight use only games before the season's
  first tip-off. The blend weight depends only on the round index, which is known from the
  schedule.
- Roster shares and P_t use only box scores with tip-off before the game's cutoff
  (`round_cutoffs`). Players absent from the previous season enter only through box scores that
  already exist.
- M3 ratings are used walk-forward, as in M5: each game's player part comes from the fit on
  games before its cutoff.
- The margin scale is fitted on seasons before each fold.
- The game's own result, later results and odds are never used. Injury reports are not used
  (no history, forward-only, see M5's retune section).
- The existing leakage tests run on the new code, and new tests check that a game's prediction
  is unchanged when later games are removed.

## Open questions for the owner
1. Approve or reject the grid (12 settings) and the simplicity order.
2. Approve the folds (2015 to 2023, nine folds), including the 2020 and 2021 COVID seasons.
3. Confirm the criteria: ±0.002 margins, the same as the M5 retune.
4. Confirm the shadow joins the R1 look as a third comparison, or declare its own look.
5. Confirm the seed (proposed 20261015).
