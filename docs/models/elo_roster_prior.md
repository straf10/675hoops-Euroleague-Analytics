# Elo with a roster prior (ELOR): protocol v1

**Status: approved by the owner 2026-10-15, not run.** Drafted 2026-10-15 and approved the same
day with one change: the roster comes from the EuroLeague season roster lists (decision 0 below),
not only from players who have already played. Approval authorises the protocol below, not the
model: nothing is logged unless the criteria pass.

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
  from box scores before the season-start cutoff. **Roster membership (decision 0, option A):**
  a team's roster for a game is the players (`type == "J"`) listed for that club in the cached
  season roster list `data/raw/euroleague/people/E{season}.json.gz` (`ingest/bios.py`) whose
  `startDate` is before the game's cutoff and whose `endDate` (if any) is after it. Mid-season
  signings therefore enter only from their start date. Players with no M3 rating get the same
  prior M5 gives unrated players. Before the first fold is scored, the build checks how many
  `startDate` values fall after round 1 began (2024 has many in October) and declares one fixed
  rule for registrations stamped within the first round; the rule and the counts go in the
  report. Live 2026-27 roster lists are read from the cache only; a refresh before a round is a
  normal cached ingest, never a re-fetch of a finished season.
  `models/turnover.py:roster_continuity` remains available as a diagnostic.
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
  **whole seasons**. Seed: 20261015 (fixed at approval).
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
Roster lists record registration, not availability: an injured or unused registered player
counts at their projected minutes. Their `startDate` stamps may lag the real signing.

## Criteria to start a shadow (approved)
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
  R1 rule is written for M5 against Elo; the owner confirmed (2026-10-15) that this arm is
  added to the look report as a third comparison, reported only. Its promotion rule is declared
  separately before 2027-28, as for the retuned M5. R1 is not changed by this protocol.
- **Limited live evidence in 2026-27:** with no backfill, logging starts several rounds into the
  season. Once a team is past the fade length N, ELOR equals Elo, so this season's live log
  shows little difference. The first full live test is 2027-28 from round 1.

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

## Owner decisions (2026-10-15)
0. Roster source: EuroLeague season roster lists with start/end dates (option A).
1. Grid (12 settings) and simplicity order: approved as drafted.
2. Folds 2015 to 2023 (nine), including the 2020 and 2021 COVID seasons: approved.
3. Criteria: ±0.002 margins, as in the M5 retune: approved.
4. Live judgement: a third comparison in the existing R1 look, reported only: approved.

## Build addendum (2026-10-15, before any fold is scored; for owner review)
Written with the harness (`eval/elor_cv.py`, `models/elor.py`, `models/roster.py`). Nothing
above is changed. The numbers come from `eurohoops backtest --model elor --cv-check`, which
scores no fold.

**Start-date counts, 2015 to 2023.** Player rows of each season's roster list. "After round 1
began": `startDate` at or after the season's first tip-off. "During round 1": also before the
second round's cutoff. "Played before stamp": rows whose player already had seconds for that
club that season before his `startDate`.

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

**Rule for registrations stamped during round 1 (proposed): strict** (`FIRST_ROUND_RULE =
"strict"` in `models/roster.py`). A registration counts from its own `startDate` only, so a
player stamped during round 1 joins the roster from round 2. Reasons: only 19 of 2,893 rows are
stamped during round 1, none for a player who had already played for that club, so the stamps
do not lag the debut there; and counting them from the season start would use a stamp made
after round 1's cutoff for round 1's own games, which the leakage rule forbids
(`tests/test_elor_cv.py` shows that alternative moving round-1 predictions).

**How the build reads the protocol** (no choice here looks at a fold's result):
- Roster stamps carry no time zone and are read as UTC. One 2014 row has no `startDate` and
  counts from before the season (2014 is not a fold). Roster club codes equal the `games` mart
  codes in every season 2007 to 2026, so no mapping is needed; the build stops if they differ.
- `P_t` is evaluated at each game's cutoff (the roster in force then), not once per season.
- Minute shares: H-c's `proj_hc` rule (window 5) applied to the club the player last played for
  before the cutoff, in this season (that club's last 5 games up to his last appearance) or last
  season (all its games). For a player who played his club's last game this equals
  `minutes.projected_shares`. A player with no appearance in this or last season gets no share.
  Shares above a team total of 5 are scaled down to 5; unfilled minutes count at rating 0 (M5's
  value for an unrated player).
- `P_t` in Elo points: `s * poss/100 * Q_t`, with `Q_t` the per-100 roster rating, `poss` the
  game's expected possessions (M5's) and `s` from `elo.fit_margin_scale` on live-Elo differences
  and margins of all rated games of earlier seasons (from 2007). Centring is over the clubs with
  a rostered player at that cutoff, for `Q` and `R(start)` alike; it cancels in a game's
  difference.
- A game without M3 state, expected possessions or a margin scale keeps live Elo. In 2015 to
  2023 no scored game is affected.
- Scored games: 2,535 (the 2,567 rated fold games of the M5 retune minus 32 neutral games).
- One-SE: the SE is the SD (ddof 1) of the game-weighted pooled gap over the 10,000 whole-season
  resamples (seed 20261015); the selected-minus-Elo CI uses the same draws.
- Outputs: `reports/elor_cv.json` and `reports/elor_cv_games.csv` (per game: Elo and all 12
  settings' P(home win)).
