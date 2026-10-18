# In-game win probability (WP): protocol v1

**Status: v1 approved by the owner on 2026-10-18,** with the answers in section 10. Every value filled from the pre-study is listed in section 11 with its source.

**Draft, not approved.** Written 2026-10-18 for owner review. Nothing here is built or run. Approval
would authorise this protocol, not any fitted model's numbers.

Season labels are start years: `2024` is 2024-25, `2025` is 2025-26.

## 1. Question

Does a fitted in-game WP model beat the closed-form baseline on held-out seasons?

    WP_base(t, m) = Φ( margin_adj / (11 · sqrt(t / 2400)) )

Definitions (all exact):

| Symbol | Definition |
|---|---|
| `m` | Score margin at the event, home minus away (points, signed). |
| `t` | Seconds remaining in the game at the event (see section 2). `t` is 2400 at tip-off and 0 at the final buzzer in regulation. |
| `mu_pre` | Pre-game expected home margin: the pre-game Elo difference (home-court edge included, neutral games without it) divided by the margin scale `s`. `s` is `elo.fit_margin_scale`, fitted on training seasons only. |
| `margin_adj` | `m + mu_pre · (t / 2400)`. |

**Why the adjustment.** At tip-off the closed form has only the score, so it ignores the
expected result of the rest of the game. The pre-game expectation `mu_pre` is the expected
margin over the full game. Its share of the game left is `t / 2400`, so `mu_pre · (t / 2400)`
is the part of that expectation still to be played. Adding it to `m` gives the expected final
margin given the state, which is then divided by the closed-form noise term `11 · sqrt(t / 2400)`.
The constant 11 comes from `IDEAS.md` §7 and is not tuned here.

**Floor.** `t` is floored at 60 seconds in every formula that divides by `t`, so the baseline and the
features stay finite at the buzzer. The floor is applied to the denominator only; `t` itself is
not changed.

**Question answered.** The gate in section 6 asks whether the chosen fitted model beats the
baseline on the primary metric on the test seasons.

## 2. Data

### Cached seasons (checked)
- `data/raw/euroleague/playbyplay/E{season}/{game}.json.gz`, one file per game, for seasons
  **2007 through 2025**: 19 complete seasons, 5,040 files. Every file parses as a JSON object with
  the same key set.
- `E2026` holds 30 partial files (2026-27 in progress). Not used here.
- Each file's game is `game_id = E{season}_{file number}` in `games` (DuckDB mart, `competition =
  'euroleague'`). All 5,040 files map to a mart game.
- The mart's `games` table has, per season, all phases (RS, PI, PO, FF). The 2025 count of 402
  files equals the mart's 380 RS + 22 playoff, play-in and Final Four games.

### One row per scoring event, not per play
Training rows are **scoring events**: every made field goal and made free throw (`PLAYTYPE` in
`2FGM`, `3FGM`, `LAYUPMD`, `DUNK`, `FTM`). `LAYUPMD` and `DUNK` are the 2008–2014 coding of
2-point makes. The first draft omitted them, which drops 41,164 makes (34,085 `LAYUPMD`, 7,079
`DUNK`) from the training rows (pre-study, write-up finding 1). Justification: the score changes only at these events, so the state
`(m, t)` is known exactly at each row. Between scoring events `m` is constant and only `t` moves,
which the metrics in section 6 already cover at fixed clock checkpoints. Per-play rows would
repeat near-identical states and let long, high-event games weigh more.

The WP line in the game page and the WPA in section 8 are computed at **every** play, using the
score in force at that play and the clock at that play. The model is fitted on scoring-event rows
and applied to all plays.

### Period and clock
- **Regulation:** the four blocks `FirstQuarter`, `SecondQuarter`, `ThirdQuarter`, `ForthQuarter`
  (sic; the key is spelled this way in the source). Each block's `MINUTE` runs 1–10, 11–20, 21–30,
  31–40. Period `p` = block index 1–4. Checked: `MINUTE` ranges match the blocks in all files, apart from
  the period-end markers (`EP`, `EG`), which carry the next minute (11, 21, 31, 41).
- **Overtime:** the `ExtraTime` block. Each OT period is **5 minutes**. OT period `k` (k = 1, 2, …)
  covers `MINUTE` `41 + 5(k − 1)` to `45 + 5(k − 1)`. Checked: the first OT event minute is 41 in
  238 of 239 games with OT play. The exception is E2009_45, whose first OT play is minute 42.
  Period index `p = 4 + k`. The clock maximum is 5:00, not 10:00. A hard-coded 10-minute clock is
  forbidden. The clock is also clamped to the period's maximum (10:00 regulation, 5:00 OT). This matters for 2015 substitution rows stamped `11:00` (2,604 rows) and `06:00` in OT (14 rows).
- **Clock:** `MARKERTIME` is `mm:ss` time remaining in the period. Parse as integer minutes and
  seconds. Blank (`""`) occurs only on `BP`, `EP`, `EG` markers, which are not events of
  play. `ND` (no clock) occurs on 422 events in 157 of 259 games in **2016**. The pre-study also found a
  sentinel clock (`00:-1` or `-1:00`) in 16 more games in 2017–2022. Rule: a game with any `ND` or
  sentinel play event is **excluded** from all splits and reported (173 games: 157 in 2016, 16 in
  2017–2022). The pre-study's clock repair (linear interpolation between the nearest valid clocks of
  the same period, in log position) is measured in section 11 but not adopted. See section 10, question 2.
- **Remaining game time:** regulation `t = (4 − p) · 600 + clock_s`. Overtime `t = clock_s`
  (the rest of the current OT period; no OT periods follow it, a game that goes to a second OT is
  handled the same way for that period).

### Score
- `POINTS_A` (home, `TeamA`) and `POINTS_B` (away, `TeamB`) are running totals written on scoring
  events. Each scoring event writes the field for the scoring side; the other field may be null
  there (for example `E2024_1` event 55: `POINTS_A` null, `POINTS_B` 2). Rule: **carry forward** the
  last non-null value of each field in log order. Score at a play = carried values at that play.
- Checked: `TeamA` is the mart's `home` team and `TeamB` is `away` in 5,039 of 5,040 files.
  The carried-forward final score equals the mart's `home_score` / `away_score` in 5,039 of 5,040
  files. The exception is `E2018_21` (team codes `N/D`, no usable score): **excluded**.
- Running scores never decrease (checked in all files).

### Home team (`is_home`)
- Per event: `is_home` = (`CODETEAM` equals the mart's `games.home`). The alternative
  `CodeTeamA == games.home` gives the same result on the checked files.
- `CODETEAM` is padded to 10 characters and must be stripped before the comparison.
- Checked: every made field goal and free throw carries a `CODETEAM` equal to `CodeTeamA` or
  `CodeTeamB`. There is no other value.
- Note: `is_home` is an event attribute, so it is not constant. Laloudakis' `is_home` was always 1
  (see `IDEAS.md` §8). A constant home flag is a bug, and tests should catch it.

### Overtime games
- Games with real overtime play: **239** across 2007–2025 (1 OT period in 220, two in 17, three in 1,
  four in 1). A game counts as overtime only if its `ExtraTime` block contains play events other than
  `EP`, `EG` and `BP`.
- Three games (E2009_11, E2011_56, E2014_69) have an `ExtraTime` block with only `EP`/`EG`
  markers. Their regulation scores are not tied, so they are regulation games. They are kept, and
  their `ExtraTime` markers are ignored.

### Possession (optional feature, not in the base model)
- `parse/possessions.py:possession_ends(events, teams)` already returns, per event, the team
  whose possession ends there (`count_possessions` in the same file is built on it). The team with
  the ball at a play can therefore be derived from the sequence of ends, but this is not yet checked
  against the cached files.
- Not used, in v1 or as a v1.1 comparison (owner decision 2026-10-18, section 10 question 7).
  Possession is unmeasured and error-prone in play-by-play. Using it later needs a new protocol
  version.

### Assists (for section 8)
- `AS` rows name the passer. In 126,952 of 166,507 assist rows (76%) the previous event is a made
  field goal of the same team. In 1,313 rows the previous event is a made field goal of the other
  team, and 38,242 rows have another event before them.
- **Linking rule (pre-study rule D, section 11).** Each `AS` row is linked, in order of preference, to
  (A) the nearest preceding made field goal in the period, if it is the passer's team; else (B) the
  next made field goal, if it is the passer's team and at the same clock second; else (C) the nearest
  same-team made field goal within ±2 events or at the same clock second, searched within ±10 events.
  Rule A alone (the first draft) links 90.1% of `AS` rows; rule D links 94.9%. The 98% coverage target
  is not met (pre-study T1(a), T1(c)). Unlinked `AS` rows credit nothing. Under the 100% scorer
  convention (section 8) linkage changes no WPA value. Owner to confirm (section 10, question 4).

## 3. Splits

| Set | Seasons (start years) | Games (RS + playoffs, excluding section 2 exclusions) |
|---|---|---|
| Train | 2007–2022 | fit models; isotonic calibration (section 5) |
| Validation | 2023 | choose the GBM setting and the model family (section 5) |
| Test | 2024, 2025 | touched once, for the gate |
| Unused | 2026 partial | not used |

Notes:
- The 2019 and 2020 seasons (COVID) are kept, as in ELOR (`docs/models/elo_roster_prior.md`). 2019
  is the cancelled season: 54 of 306 regular-season games were never played, and there were no
  playoffs. 2020 games were played in empty arenas (81% record zero attendance). Their shortened
  seasons and crowd-less games are a disclosed limit. Pre-study T4: refitting without 2019 and 2020
  changes log loss by +0.0003, 95% CI [−0.0001, +0.0007], so they stay in training. (The first
  draft labelled these seasons 2020 and 2021.)
- Games with `played = false`, forfeits (none in the EuroLeague mart) and the 157 `ND` games of 2016
  are excluded and counted in the report.
- Playoffs are included. Neutral Final Four games are included with `neutral = 1`. Pre-study T3: the
  playoff gap (−0.001) against the regular season (+0.004) differs by −0.055 to +0.046 (95% CI), so no
  phase flag is set.
- **Disclosed:** the pre-game feature uses Elo, whose live parameters were chosen on 2024
  (`elo_roster_prior.md`). The 2024–25 test games therefore share a small amount of tuning history
  with the Elo component. Elo is not re-tuned here.

**Test set touched once.** Validation chooses everything: features, the GBM setting, the family
and the isotonic fit. The test seasons are read once, by the gate command, which writes the report.
No test metric is used to choose anything, and a second test run needs a new protocol version.

## 4. Features

All features are computed from the event row and from state available at tip-off or at that event.

| Feature | Definition |
|---|---|
| `m` | Margin at the event (home minus away, carried score). |
| `t` | Seconds remaining (section 2). |
| `tf` | `t / 2400`. |
| `ot` | 1 if the event is in an OT period, else 0. |
| `m_tf` | `m · tf`. |
| `z` | `m / sqrt(max(t, 60) / 2400)`. The floor of 60 seconds is the one set in section 1. |
| `logit_pre` | `logit(P_pre)`, where `P_pre` is the **published pre-game P(home)** for the game: the Elo forecast row logged for the game before tip-off, clipped to [1e-6, 1 − 1e-6]. Walk-forward Elo for history (section 4.1). |
| `neutral` | 1 if the mart's `neutral` flag is set, else 0. |

**The `home` feature.** The row is always scored from the home team's side, so a constant `home`
flag carries no information (the Laloudakis bug). The home-court edge enters through `logit_pre`
(Elo includes it, and it is zero when `neutral = 1`). The only other home-related input is `neutral`.

### 4.1 Pre-game probability for history
- For seasons before live logging, `P_pre` comes from a walk-forward Elo replay: each game's
  rating difference uses only games with tip-off earlier than that game. Elo parameters are the
  live ones (k 20, hca 90, reversion 0.25), as in `elo.replay`.
- For the live season, `P_pre` is the logged Elo row, as it was published.

### Leakage rules
1. A row's features use only events at or before that row's event in log order, and the clock and
   score at that event.
2. `P_pre` uses only games with tip-off before the game. It never uses the game's own result, later
   results, odds or injury reports.
3. The target (home won the game) and the final score are never features and never used to
   compute features for the same game.
4. The isotonic map (section 5) is fitted only on out-of-fold predictions of training seasons.
5. The margin scale `s` and any mean used for the baseline are fitted on training seasons only.
6. Tests: a row's features do not change when later events of the same game are removed, and
   `P_pre` does not change when later games are removed.

## 5. Models

Target: `y = 1` if the home team won the game, else 0. All models predict `P(home wins | state)`.

### (a) Logistic regression with time interactions
Inputs: `m`, `tf`, `ot`, `m_tf`, `z`, `logit_pre`, `neutral`, and `m · logit_pre · tf` as an
interaction. L2 penalty with `C = 1`, fixed, not tuned. Standardise inputs using training seasons.

### (b) Gradient boosting (`sklearn` `GradientBoostingClassifier` or equivalent)
Pre-declared grid, **chosen on validation only** by raw (uncalibrated) log loss on 2023, scored at
the section 6 checkpoints with the same game weighting:

| Setting | `n_estimators` | `max_depth` | `learning_rate` |
|---|---|---|---|
| G1 | 200 | 3 | 0.05 |
| G2 | 200 | 4 | 0.05 |
| G3 | 400 | 3 | 0.05 |
| G4 | 400 | 4 | 0.05 |

Subsample 1.0, all other settings default. Ties go to the smaller setting in the order G1, G2, G3, G4.
The grid is not widened after seeing validation results. Four settings is the whole grid.

### Family choice
Both candidates, (a) and (b) at its chosen setting, get their own isotonic map (next subsection).
The family is then chosen on the validation season by **calibrated** log loss at the section 6
checkpoints. The chosen family, fitted on 2007–2022 with its isotonic map, is frozen. There is no
refit on 2023 before the test.

### Calibration: isotonic on out-of-fold predictions
For each candidate family (so both families are calibrated before the choice):
1. For each season `s` in 2010–2022, fit the family on seasons 2007 to `s − 1` (expanding
   window), and predict season `s`. These predictions are out-of-fold. Seasons 2007–2009 are a
   warm-up.
2. Fit an isotonic regression from raw predicted probability to outcome on all out-of-fold rows.
3. Apply the isotonic map to the raw output of the model fitted on 2007–2022. The map is fixed
   before the validation and test seasons are scored.

Platt scaling is not used. The Laloudakis site text says Platt, but the code uses isotonic
(`IDEAS.md` §8).

## 6. Metrics and gate

### Evaluation points (weighting)
Scores are computed at fixed game-clock checkpoints, not at events:
- Checkpoints every 60 seconds of game time, from `t = 2340` down to `t = 0` (tip-off, `t = 2400`,
  is excluded). Overtime games add checkpoints every 60 seconds in each OT period, from `t = 300`
  to `t = 0`. A checkpoint uses the state at the last event at or before that time, the carried
  score, and the period's clock.
- **Each game's checkpoints are averaged first, and then games are averaged.** Every game weighs
  the same, and games with many scoring events do not dominate.
- Overtime checkpoints count only in games with real OT play.

### Primary and secondary metrics
- **Primary:** mean per-game log loss on the test seasons (2024–2025), with the checkpoint averaging
  above.
- **Secondary:** Brier score, same weighting.
- **Reported:** log loss and Brier on the validation season, and by season and by family.

### Calibration by time bucket
Buckets by `t` (regulation, period `p` in parentheses): Q1 (`t` 1800–2400), Q2 (1200–1800), Q3
(600–1200), Q4 (0–600), last 2 minutes (`t` 0–120, a subset of Q4), OT (any OT checkpoint).

For each bucket, report: mean predicted probability, observed home-win rate, their gap, and a
binned calibration table (10 bins). **Tolerance:** the absolute gap in each bucket is at most 0.02.
The report also gives the slope of observed on predicted per bucket. Calibration failure is reported,
but the gate in the next paragraph uses log loss only.

### Gate (declared before any test run)
Let `Δ = LL(chosen model) − LL(baseline)`, averaged over test games, with the checkpoint weighting.
The gate passes only if:
1. The 95% **paired bootstrap** CI over **games** (10,000 resamples of whole games, seed fixed at
   20261018, both models scored on the same resampled games) lies **entirely below zero**.
2. `Δ` is negative on the mean.

If the gate fails, the closed-form baseline is what the game pages use. The gate is pass/fail,
reported once.

The bootstrap resamples games, not checkpoints, and not seasons (two seasons are too few for a
season bootstrap).

## 7. Chain start

- Every game's WP line starts at the **published pre-game P(home)** for that game, not at 0.5. The
  first point is at tip-off, and the first event's ΔWP is measured from that value.
- The in-game model is never used as a pre-game forecaster. It is not used to produce any value
  before tip-off, and it is not logged in `predictions/`. This follows the Laloudakis lesson
  (`IDEAS.md` §8): reusing the in-game model at `t = 2400` for pre-game odds produced
  overconfident probabilities (Platt slope 0.37 on n = 71).
- The model's own output at `t = 2400` is not used as the chain start, because it can differ from
  the published `P_pre`. The chain uses `P_pre` at tip-off, always.
- **Tip-off gap.** Let `g = P_pre − WP_model(t = 2400, m = 0)`. The displayed line is
  `WP(e) = clip(WP_model(e) + g · tf(e), 0.001, 0.999)`, so it starts exactly at `P_pre` and the gap
  fades linearly to zero at the final buzzer (in OT, `tf` is 0 and the gap is gone). Every ΔWP, and so
  every WPA in section 8, is taken on this line. No play is credited with the gap itself: without
  this rule the first play of every game would absorb `g`. The fade is linear in `tf`.
  In OT the gap term uses `tf = 0`, so the gap is gone there; the model's `tf` feature in
  section 4 keeps `t / 2400` in OT. The pre-study script has the same note: its OT checkpoints use
  `t` = clock, and section 7's "`tf` is 0 in OT" is read as applying to the gap only.
- **Measured (pre-study T5, 3,196 games, 2010–2022):** mean `g` −0.017; mean `|g|` 0.038; 95th
  percentile of `|g|` 0.077, well above the 0.01 threshold, so the fade comparison is informative.
  Shape comparison on out-of-fold checkpoints: exp(−3(1 − tf)) improves log loss by 0.0004, 95% CI
  [−0.0012, +0.0004], inside noise. Linear is kept.

## 8. Downstream outputs (defined, not built)

### WPA per player
**Event-only credit (pre-study T1(c), section 11).** For a play `e` by a player on team `T_e`, with
the score before and after `e` and the clock `t_e` of `e`, on the line of section 7:

    ΔWP_e  = WP(score after e, t_e) − WP(score before e, t_e)   (home-win probability)
    s_e    = +1 if T_e is home, −1 if away
    WPA_e  = 100 · s_e · ΔWP_e          (percentage points, home perspective flipped for away)

Both terms are taken at the same clock, so time passage between plays credits nobody. A
non-scoring play has the same score before and after, so `ΔWP_e = 0`: rebounds, turnovers and
steals credit 0 by construction, which is expected. Only scoring plays carry WPA. A player's game
WPA is the sum of `WPA_e` over the plays credited to him. The first draft's definition, the change
between consecutive plays, is not used. The pre-study found it invalid: the same-season check gave
r = −0.06, the wrong sign.

**Assisted makes: convention, not an estimate (owner decision D14, 2026-10-18).** The whole
`WPA_e` of a made field goal goes to the **scorer**. The passer receives 0, whether or not an `AS`
row is linked.
- The reason is that the split could not be measured. The pre-study tried. Passer share is not
  identified: `AS` rows exist only for made field goals, so `make ~ assisted` is perfectly separated
  (T1(b)). The event-only credit then failed its pre-declared validity gate: same-season Pearson r
  of WPA per 40 minutes against plus-minus per 40 is −0.049, bootstrap 95% CI [−0.088, 0.063],
  n = 419. The gate needed a point estimate above 0.3 and a CI lower bound above 0 (T1(c)).
- Because no split was measured, no split is estimated. The 100/0 choice is a stated convention and
  is labelled as one wherever WPA is reported.
- Unlinked makes credit the scorer in full. Free throws, rebounds, turnovers and steals credit their
  own player in full.
- The convention is fixed before any result is seen. It is not fitted.

**Validity of the WPA metric.** The event-only credit did not pass its validity gate. WPA is
therefore not validated against plus-minus. The gate was not changed. A post-gate diagnostic
(season-level, n = 896) found raw box points per 40 minutes at r = 0.127 against plus-minus per 40,
so the benchmark itself is weak. **WPA per player is therefore not published** (owner decision
2026-10-18): not on the site, not in downloads, and not as a layer of the MVP ladder. The definition
above stays so that the failed gate can be read later. A different benchmark (the pre-study suggests
within-season on-court net rating, or a team-adjusted plus-minus) needs a new protocol version
before any player WPA is shown. The game-level WP line and its biggest swings are published.

### Game-control parts (`IDEAS.md` §13)
Defined exactly on the checkpoint grid of section 6, for one game with eventual winner `W`, with
`WP_W(c)` the winner's WP at checkpoint `c` (WP of the home team if `W` is home, else `1 − WP_home`):

| Part | Definition |
|---|---|
| Dominance | Mean over checkpoints of `2 · (WP_W(c) − 0.5)`. Range (−1, 1); higher means the winner was ahead throughout. |
| Control | Share of checkpoints with `WP_W(c) > 0.6`. Range [0, 1]. |
| Drama | Total variation of WP over the checkpoints: `Σ |WP(c) − WP(c − 1)|`. No upper bound; shown raw. |
| Comeback | `1 − min_c WP_W(c)`. Range [0, 1]; high when the winner was far behind. |
| Crunch | `Σ |ΔWP_e|` over events with regulation `t ≤ 300`. Shown raw. |

The thresholds, 0.6 for control and 300 s for crunch, are stated conventions for display, chosen by
the owner on 2026-10-18 and not fitted. Killer instinct is dropped. The parts are shown per game and
per team. **No composite** (`IDEAS.md` §13).

The parts are computed from the chosen WP line. If the gate fails, from the baseline.

## 9. Versioning, artefacts, what gets committed

- Version: `0.2.0+wp.<8 hex>` for the in-game WP line, where the hex is the sha256 of the
  pinned spec (families, grid, features, isotonic rule, floor, gate constants). The code computes it.
- Report: `reports/backtest_wp.json` (splits, counts, exclusions, validation and test log loss and
  Brier with bootstrap CIs, calibration tables by bucket, the chosen family and setting, the gate
  result), plus `reports/backtest_wp_games.csv` (one row per test game and checkpoint group).
- Model card: `docs/models/wp_card.md`, with every decimal in its table checked against the report
  by a test, as in `docs/models/m7.md`.
- Nothing is written to `predictions/`. The in-game WP is not pre-registered, and only the pre-game
  forecasts are logged.
- Not committed: the fitted model file (`models/`), the cached play-by-play, and any site output
  (`web/src/data/site.json`, `site/`).
- A change to any spec item above is a new protocol version, declared before it is used.

## 10. Open questions for the owner

Answered by the owner on 2026-10-18.

1. Approval: **approved** with the answers below.
2. Clock gap: **exclude** the 173 `ND` and sentinel games. The pre-study repair (T2: MAE 4.0 s,
   95th percentile 11.5 s under random blanking) is not adopted, because the test does not cover
   clustered gaps.
3. Assist split: **settled 2026-10-18 (D14): 100/0 convention, section 8.**
4. Assist linkage: **rule D, confirmed.** The pre-study's chosen rule is D (section 2). It
   links 94.9% of `AS` rows, against 90.1% for the draft's rule A. The 98% target is not met. Under
   the 100/0 convention, linkage changes no WPA value.
5. Playoffs: **include** in training and test (pre-study T3: no phase flag).
6. Game control: **keep 0.6 control and 300 s crunch as stated display conventions; drop killer
   instinct** (section 8).
7. Possession: **not at all** in v1 or v1.1 (section 4).
11. Player WPA: **not published**, because it failed its validity gate (section 8). The game WP line
    and its swings are published.
8. The 2019 and 2020 COVID seasons: **keep** in training (pre-study T4: dropping them changes log
   loss by +0.0003, CI [−0.0001, +0.0007]).
9. Baseline margin scale: **Elo scale**, refitted each evaluation season on earlier seasons only
   (pre-study `fold_scales`, `elo.fit_margin_scale`).
10. Tip-off gap (section 7): **linear** in `tf` (pre-study T5: the exponential shape is inside noise).

## 11. Values filled from the pre-study (2026-10-18)

Source: branch `wave1/wp-prestudy`, merged into this branch as `docs/models/wp_prestudy.md` (write-up)
and `reports/wp_prestudy.json` (report), with `scripts/wp_prestudy.py` and `scripts/wp_t1c.py`. All
numbers use 2007–2022 seasons only (T1(c) and its gate use 2010–2021 `s`).

| Value in this protocol | Filled value | Source |
|---|---|---|
| Scoring-event codes (section 2) | add `LAYUPMD`, `DUNK`; 41,164 makes | write-up finding 1 |
| Excluded `ND`/sentinel games (section 2) | 173 (157 in 2016, 16 in 2017–2022) | write-up finding 2 |
| Assist linkage (section 2, Q4) | rule D, 94.9% of `AS` rows; 98% not met | T1(c) "Linkage" table; report `T1c_measured_split.linkage` |
| Assist split (section 8, Q3) | 100/0 convention (D14), not an estimate | T1(b) not identified; T1(c) gate: r = −0.049, CI [−0.088, 0.063] |
| WPA credit (section 8) | event-only; time-inclusive version invalid (r = −0.06) | T1(c) "Corrected credit" and "Results, time-inclusive credit" |
| COVID seasons (section 3, Q8) | 2019 and 2020, kept; log-loss change +0.0003 | T4 |
| Playoffs (section 3, Q5) | include; gap −0.001 | T3 |
| Tip-off gap shape and size (section 7, Q10) | linear; mean g −0.017, mean abs 0.038, p95 0.077 | T5 |
| Margin scale (Q9) | Elo `fit_margin_scale`, expanding window | `scripts/wp_prestudy.py` `fold_scales` |
| Baseline context (section 6) | logistic 0.4447, closed form 0.4601 (2010–2022, out-of-fold) | write-up "Baseline context" |

Measured but not adopted: the 2016 clock repair (T2, MAE 4.0 s, 95th percentile 11.5 s). Owner
decision, section 10, question 2.

Not measured, left open: gradient boosting (the pre-study ran logistic only, so the family and
setting in section 5 are validation steps, not pre-study values), game-control thresholds, and
possession.

Pre-study corrections that change the first draft: scoring codes (section 2), the `ND`/sentinel count
(section 2), the COVID labels (section 3), the WPA credit definition (section 8), the linkage rule
(section 2), and the OT note in section 7.
