# In-game win probability (WP): protocol v1

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
`2FGM`, `3FGM`, `FTM`). Justification: the score changes only at these events, so the state
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
  play. `ND` (no clock) occurs on 422 events in 157 of 259 games in **2016 only**. Rule: a game with any
  `ND` play event is **excluded** from all splits and reported (157 games). Imputing the clock is
  an open question (section 10).
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
- Not used in model v1. It is listed as an optional feature for a v1.1 comparison, and the base
  model must not depend on it.

### Assists (for section 8)
- `AS` rows name the passer. In 126,952 of 166,507 assist rows (76%) the previous event is a made
  field goal of the same team. In 1,313 rows the previous event is a made field goal of the other
  team, and 38,242 rows have another event before them. Linking rule: open question (section 10).

## 3. Splits

| Set | Seasons (start years) | Games (RS + playoffs, excluding section 2 exclusions) |
|---|---|---|
| Train | 2007–2022 | fit models; isotonic calibration (section 5) |
| Validation | 2023 | choose the GBM setting and the model family (section 5) |
| Test | 2024, 2025 | touched once, for the gate |
| Unused | 2026 partial | not used |

Notes:
- The 2020 and 2021 seasons (COVID) are kept, as in ELOR (`docs/models/elo_roster_prior.md`). Their
  crowd-less games and shortened seasons are a disclosed limit.
- Games with `played = false`, forfeits (none in the EuroLeague mart) and the 157 `ND` games of 2016
  are excluded and counted in the report.
- Playoffs are included. Neutral Final Four games are included with `neutral = 1`.
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
  this rule the first play of every game would absorb `g`. The fade shape is an owner decision
  (section 10).

## 8. Downstream outputs (defined, not built)

### WPA per player
For a play `e` with win-probability change `ΔWP_e = WP(after e) − WP(before e)` (in home-win
probability) and team `T_e` of the player:

    s_e    = +1 if T_e is home, −1 if away
    WPA_e  = 100 · s_e · ΔWP_e          (percentage points, home perspective flipped for away)

A player's game WPA is the sum of `WPA_e` over the plays credited to him. Plays with no WP change
(for example, `JB` jump balls, `BP`/`EP` markers) credit nothing.

**Assisted makes (owner decision).** A made field goal with an `AS` row linked to it splits its
`WPA_e` between scorer and passer:
- **Proposed:** scorer 70%, passer 30%.
- Alternatives for the owner: 100% scorer (Laloudakis, `IDEAS.md` §8), or 50/50.
- The split applies to the made field goal only. Unassisted makes, free throws, rebounds, turnovers
  and steals credit their own player in full.
- The split is fixed before any result is seen. It is not fitted.

**Assist linkage** is an open question (section 10).

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
| Killer instinct | Mean of `WP_W(c)` over checkpoints with regulation `t ≤ 600`. Range [0, 1]. |

The thresholds (0.6 for control, 300 s for crunch, 600 s for killer instinct) are pre-declared
here and are owner decisions. Other parts are shown per game and per team. **No composite** (`IDEAS.md`
§13).

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

1. Approve the protocol as drafted, or amend it.
2. Clock gap in 2016: exclude the 157 games with `ND` clocks (proposed), or impute the clock from
   neighbouring events and flag the rows?
3. Assist split: 70/30 (proposed), 100/0 or 50/50?
4. Assist linkage: 76% of `AS` rows follow a same-team made field goal in the log. Accept the rule
   "nearest preceding made field goal of the same team in the same period, with no other make
   between", after a coverage check on all seasons?
5. Playoffs in: include them (proposed) in training and test, or regular season only?
6. Game-control thresholds (0.6 control, 300 s crunch, 600 s killer instinct) and the killer
   instinct definition: keep, change or drop?
7. Possession as an optional feature (v1.1 comparison) or not at all?
8. The 2020 and 2021 COVID seasons: keep in training (proposed, as in ELOR), or drop?
9. Should the baseline's pre-game margin `mu_pre` use the same margin scale `s` as the Elo
   forecast, or a separate fit on the WP training seasons? Proposed: the Elo scale, as the
   baseline and the chain both depend on it.
10. Tip-off gap (section 7): fade the gap between `P_pre` and the model's tip-off value linearly
    with time left (proposed), or hold it constant, or let it decay faster?
