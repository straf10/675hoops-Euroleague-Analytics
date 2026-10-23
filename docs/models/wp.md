# In-game win probability (WP): model spec

Status: published (the game WP line uses the fitted model; see `docs/models/wp_card.md`). Player WPA is not published.

Season labels are start years: `2024` is 2024-25, `2025` is 2025-26.

## What it is

**Question and baseline.** The closed-form baseline is

    WP_base(t, m) = Φ( margin_adj / (11 · sqrt(t / 2400)) )

| Symbol | Definition |
|---|---|
| `m` | Score margin at the event, home minus away (points, signed). |
| `t` | Seconds remaining in the game at the event. `t` is 2400 at tip-off and 0 at the final buzzer in regulation. |
| `mu_pre` | Pre-game expected home margin: the pre-game Elo difference (home-court edge included; neutral games without it) divided by `s`. `s` is `elo.fit_margin_scale`, fitted on training seasons only. |
| `margin_adj` | `m + mu_pre · (t / 2400)`. |

`mu_pre · (t / 2400)` is the part of the pre-game expected margin still to be played. Adding it to `m` gives the expected final margin given the state. The constant 11 comes from `IDEAS.md` §7.

**Floor.** `t` is floored at 60 seconds in every formula that divides by `t`. The floor applies to the denominator only.

### Data
- Play-by-play: `data/raw/euroleague/playbyplay/E{season}/{game}.json.gz`, one file per game, for seasons 2007 to 2025 (19 complete seasons, 5,040 files). `E2026` (30 partial files) is not used.
- Each file maps to a mart game, `game_id = E{season}_{file number}`. The 2025 count of 402 files equals the mart's 380 regular-season games plus 22 playoff, play-in and Final Four games.
- **Training rows are scoring events:** made field goals and made free throws (`PLAYTYPE` in `2FGM`, `3FGM`, `LAYUPMD`, `DUNK`, `FTM`). `LAYUPMD` and `DUNK` are the 2008–2014 coding of 2-point makes. Leaving them out drops 41,164 makes (34,085 `LAYUPMD`, 7,079 `DUNK`). The score changes only at these events, so the state `(m, t)` is known at each row.
- The WP line and WPA are computed at every play, using the score and clock in force at that play. The model is fitted on scoring-event rows and applied to all plays.

**Period and clock.**
- Regulation: blocks `FirstQuarter`, `SecondQuarter`, `ThirdQuarter`, `ForthQuarter` (spelled this way in the source). `MINUTE` runs 1–10, 11–20, 21–30, 31–40. Period `p` = block index 1–4. Period-end markers (`EP`, `EG`) carry minutes 11, 21, 31 and 41.
- Overtime: the `ExtraTime` block. Each OT period is 5 minutes. OT period `k` covers `MINUTE` `41 + 5(k − 1)` to `45 + 5(k − 1)`. Period index `p = 4 + k`. The OT clock maximum is 5:00.
- The clock is clamped to the period maximum (10:00 regulation, 5:00 OT). This fixes 2,604 rows stamped `11:00` in 2015 and 14 stamped `06:00` in OT.
- `MARKERTIME` is `mm:ss` time remaining in the period. Blank values occur only on `BP`, `EP`, `EG` markers.
- **Excluded:** a game with any `ND` (no clock) or sentinel (`00:-1`, `-1:00`) play event. That is 173 games in 2007–2022 (157 in 2016, 16 in 2017–2022). In 2016, `ND` occurs on 422 events in 157 of 259 games. A clock repair was measured (T2, see Results) and not adopted.
- Remaining game time: regulation `t = (4 − p) · 600 + clock_s`. Overtime `t = clock_s`.
- Overtime games: 239 across 2007–2025 contain real OT play (an `ExtraTime` block with play events other than `EP`, `EG`, `BP`): one OT period in 220, two in 17, three in 1, four in 1. Three games whose `ExtraTime` block holds only markers (E2009_11, E2011_56, E2014_69) are regulation games.

**Score.** `POINTS_A` (home) and `POINTS_B` (away) are running totals written on scoring events. The score at a play is the last non-null value of each field in log order. Running scores never decrease. `TeamA` is the mart's home team in 5,039 of 5,040 files, and the carried final score equals the mart's score in 5,039 files. `E2018_21` (team codes `N/D`, no usable score) is excluded.

**Home team.** `is_home` = `CODETEAM` (stripped of padding) equals the mart's `games.home`. It varies by event. The home-court edge enters through `logit_pre` (zero at neutral venues).

**Possession.** Not used.

**Assists** (for the WPA convention). `AS` rows name the passer. In 126,952 of 166,507 `AS` rows (76%) the previous event is a made field goal of the same team. Each `AS` row is linked, in order of preference, to (A) the nearest preceding made field goal in the period, if it is the passer's team; else (B) the next made field goal, if it is the passer's team and at the same clock second; else (C) the nearest same-team made field goal within ±2 events or at the same clock second, searched within ±10 events. Rule D links 94.9% of `AS` rows (rule A alone: 90.1%). The 98% target is not met. Unlinked `AS` rows credit nothing. Under the convention in section 8, linkage changes no WPA value.

### Splits

| Set | Seasons (start years) | Use |
|---|---|---|
| Train | 2007–2022 | Fit models; isotonic calibration |
| Validation | 2023 | Choose the GBM setting and the model family |
| Test | 2024, 2025 | Comparison against the baseline |
| Unused | 2026 partial | Not used |

- 2019 and 2020 (COVID) are kept in training. 2019 was cancelled: 54 of 306 regular-season games were never played, and there were no playoffs. 2020 games were played in empty arenas (81% record zero attendance). Dropping both changes log loss by +0.0003, 95% CI [−0.0001, +0.0007] (T4).
- Playoffs are included, and neutral Final Four games carry `neutral = 1`. The playoff gap (−0.001) against the regular season (+0.004) differs by −0.055 to +0.046 (95% CI), so no phase flag is set (T3).
- Excluded from all splits: `played = false` games, forfeits (none in the EuroLeague mart), and `ND` games.
- The pre-game feature uses Elo, whose live parameters were tuned on 2024. The 2024–25 test games share a small amount of tuning history with the Elo component.

### Features

| Feature | Definition |
|---|---|
| `m` | Margin at the event (home minus away, carried score). |
| `t` | Seconds remaining. |
| `tf` | `t / 2400`. |
| `ot` | 1 if the event is in an OT period, else 0. |
| `m_tf` | `m · tf`. |
| `z` | `m / sqrt(max(t, 60) / 2400)`. |
| `logit_pre` | `logit(P_pre)`, where `P_pre` is the published pre-game P(home) for the game: the Elo forecast logged before tip-off, clipped to [1e-6, 1 − 1e-6]. |
| `neutral` | 1 if the mart's `neutral` flag is set, else 0. |

The row is always scored from the home side, so a constant home flag carries no information. The only home-related inputs are `logit_pre` and `neutral`.

**Pre-game probability.** For seasons before live logging, `P_pre` comes from a walk-forward Elo replay: each game's rating difference uses only games with earlier tip-off. Elo parameters are the live ones (k 20, hca 90, reversion 0.25), as in `elo.replay`. For the live season, `P_pre` is the logged Elo row as published.

**Leakage.** A row's features use only events at or before that row in log order. `P_pre` uses only earlier games. The target and final score are never features. The isotonic map and the margin scale are fitted on training seasons only.

### Models

Target: `y = 1` if the home team won the game. All models predict `P(home wins | state)`.

**(a) Logistic regression with time interactions.** Inputs: `m`, `tf`, `ot`, `m_tf`, `z`, `logit_pre`, `neutral`, and `m · logit_pre · tf`. L2 penalty with `C = 1`. Inputs standardised on training seasons.

**(b) Gradient boosting** (`sklearn` `GradientBoostingClassifier`). Chosen on validation only, by raw (uncalibrated) log loss on 2023, scored at the checkpoints with the same game weighting. Subsample 1.0, other settings default, `random_state` 20261018. Trees use the features without the `m · logit_pre · tf` term and without `t` (a monotone copy of `tf`). Ties go to the smaller setting.

| Setting | `n_estimators` | `max_depth` | `learning_rate` |
|---|---|---|---|
| G1 | 200 | 3 | 0.05 |
| G2 | 200 | 4 | 0.05 |
| G3 | 400 | 3 | 0.05 |
| G4 | 400 | 4 | 0.05 |

**Family choice.** Both candidates get their own isotonic map. The family is chosen on 2023 by calibrated log loss at the checkpoints. The chosen family is fitted on 2007–2022 with its isotonic map, used unchanged. There is no refit on 2023.

**Calibration: isotonic on out-of-fold predictions.**
1. For each season `s` in 2010–2022, fit the family on seasons 2007 to `s − 1` and predict season `s`. Seasons 2007–2009 are a warm-up.
2. Fit an isotonic regression from raw predicted probability to outcome, on all out-of-fold rows.
3. Apply the isotonic map to the raw output of the model fitted on 2007–2022.

Platt scaling is not used.

**Margin scale.** The baseline uses the Elo `fit_margin_scale`, refitted for each evaluation season on earlier seasons only.

### Evaluation

**Checkpoints.** Scores are computed at fixed clock checkpoints, not at events. Every 60 seconds from `t = 2340` down to `t = 0` (tip-off is excluded). Overtime games add checkpoints every 60 seconds in each OT period, from `t = 300` to `t = 0`. A checkpoint uses the state at the last event at or before that time.

**Weighting.** Each game's checkpoints are averaged first, then games are averaged. Every game weighs the same.

**Metrics.**
- Primary: mean per-game log loss on the test seasons.
- Secondary: Brier score, same weighting.
- Reported: log loss and Brier on the validation season, by season and by family.

**Comparison.** `Δ = LL(chosen model) − LL(baseline)`, averaged over test games. 95% paired bootstrap CI over whole games (10,000 resamples, seed 20261018, both models on the same resampled games).

**Calibration by time bucket.** Q1 (`t` above 1800), Q2 (1200–1800), Q3 (600–1200), Q4 (0–600), last 2 minutes (`t` 0–120, inside Q4), OT (every OT checkpoint). Per bucket: mean predicted probability, observed home-win rate, their gap, a 10-bin calibration table, and the game-weighted slope of observed on predicted. Tolerance: absolute gap at most 0.02 per bucket. Calibration is reported; the comparison above uses log loss only.

The regulation checkpoint at `t = 0` and the first OT checkpoint at `t = 300` are the same game moment. Both are kept.

### Chain start and tip-off gap

- Each game's WP line starts at the published pre-game P(home), not at 0.5. The first point is at tip-off.
- The in-game model is never used as a pre-game forecaster. It produces no value before tip-off and is not logged in `predictions/`. Its output at `t = 2400` is not the chain start, because it can differ from the published `P_pre`.
- **Tip-off gap.** `g = P_pre − WP_model(t = 2400, m = 0)`. The displayed line is `WP(e) = clip(WP_model(e) + g · tf(e), 0.001, 0.999)`. It starts at `P_pre` and the gap fades linearly to zero at the final buzzer. In OT, `tf` is 0, so the gap is gone there. No play is credited with the gap itself.
- Measured (T5, 3,196 games, 2010–2022): mean `g` −0.017; mean `|g|` 0.038; 95th percentile of `|g|` 0.077. An exponential fade, `exp(−3(1 − tf))`, improves log loss by 0.0004, 95% CI [−0.0012, +0.0004], which is inside noise. Linear is used.

### Downstream outputs

**WPA per player: not published.** Credit definition for reference:

    ΔWP_e  = WP(score after e, t_e) − WP(score before e, t_e)   (home-win probability)
    s_e    = +1 if T_e is home, −1 if away
    WPA_e  = 100 · s_e · ΔWP_e          (percentage points)

Both terms are at the same clock, so time passage credits nobody. Non-scoring plays credit 0 by construction.

- **Assisted makes (convention, not an estimate).** The whole `WPA_e` of a made field goal goes to the scorer. The passer receives 0, whether or not an `AS` row is linked. Passer share is not identified, because `AS` rows exist only for made field goals (T1(b)).
- Unlinked makes credit the scorer in full. Free throws, rebounds, turnovers and steals credit their own player in full.
- **Validity.** The event-only credit failed its validity check: same-season Pearson r of WPA per 40 minutes against plus-minus per 40 is −0.049, bootstrap 95% CI [−0.088, 0.063], n = 419 (T1(c)). A time-inclusive version gave r = −0.06. A post-check diagnostic (season-level, n = 896) found raw box points per 40 minutes at r = 0.127 against plus-minus per 40.
- Player WPA is therefore not on the site, not in downloads, and not in the MVP ladder. The game-level WP line and its biggest swings are published.

**Game-control parts.** Defined on the checkpoint grid for one game with eventual winner `W`. `WP_W(c)` is the winner's WP at checkpoint `c`.

| Part | Definition |
|---|---|
| Dominance | Mean over checkpoints of `2 · (WP_W(c) − 0.5)`. Range (−1, 1). |
| Control | Share of checkpoints with `WP_W(c) > 0.6`. Range [0, 1]. |
| Drama | Total variation of WP over the checkpoints: `Σ |WP(c) − WP(c − 1)|`. Shown raw. |
| Comeback | `1 − min_c WP_W(c)`. Range [0, 1]. |
| Crunch | `Σ |ΔWP_e|` over events with regulation `t ≤ 300`. Shown raw. |

The 0.6 control threshold and 300 s crunch window are display conventions, not fitted. Killer instinct is dropped. The parts are shown per game and per team, computed from the chosen WP line, and there is no composite.

### Versioning and artefacts
- Version `0.2.0+wp.<8 hex>`. The hex is the sha256 of the pinned spec (families, grid, features, isotonic rule, floor, comparison constants). The code computes it.
- Report: `reports/backtest_wp.json`, and `reports/backtest_wp_games.csv` (one row per test game and checkpoint group).
- Model card: `docs/models/wp_card.md`.
- Nothing is written to `predictions/`.
- Not committed: the fitted model, the cached play-by-play, and site output.
- The backtest command refuses to run when `reports/backtest_wp.json` exists.

## Results

**Pre-study values** (report `reports/wp_prestudy.json`, scripts `scripts/wp_prestudy.py` and `scripts/wp_t1c.py`). All numbers use 2007–2022 seasons only (T1(c) and its check use 2010–2021 `s`).

| Value | Filled value | Source |
|---|---|---|
| Scoring-event codes | add `LAYUPMD`, `DUNK`; 41,164 makes | write-up finding 1 |
| Excluded `ND`/sentinel games | 173 (157 in 2016, 16 in 2017–2022) | write-up finding 2 |
| Assist linkage | rule D, 94.9% of `AS` rows; 98% not met | T1(c) "Linkage" table; report `T1c_measured_split.linkage` |
| Assist split | 100/0 convention, not an estimate | T1(b) not identified; T1(c): r = −0.049, CI [−0.088, 0.063] |
| WPA credit | event-only; time-inclusive version invalid (r = −0.06) | T1(c) "Corrected credit" and "Results, time-inclusive credit" |
| COVID seasons | 2019 and 2020, kept; log-loss change +0.0003 | T4 |
| Playoffs | include; gap −0.001 | T3 |
| Tip-off gap shape and size | linear; mean g −0.017, mean abs 0.038, p95 0.077 | T5 |
| Margin scale | Elo `fit_margin_scale`, expanding window | `scripts/wp_prestudy.py` `fold_scales` |
| Baseline context | logistic 0.4447, closed form 0.4601 (2010–2022, out-of-fold) | write-up "Baseline context" |

Measured but not adopted: the 2016 clock repair (T2, MAE 4.0 s, 95th percentile 11.5 s under random blanking).

Not measured in the pre-study: gradient boosting (the pre-study ran logistic only), the game-control thresholds, and possession.

Fitted results for the chosen model are in `docs/models/wp_card.md`.

## Files
- Code: `src/eurohoops/models/wp.py`, `src/eurohoops/models/wp_control.py`, `src/eurohoops/eval/wp_backtest.py`, `src/eurohoops/parse/possessions.py` (`possession_ends`, not used by the model).
- Command: `eurohoops backtest --model wp`.
- Pre-study: `scripts/wp_prestudy.py`, `scripts/wp_t1c.py`, `reports/wp_prestudy.json`.
- Tests: `tests/test_wp_backtest.py`, `tests/test_wp_control.py`, `tests/test_wp_model.py`, `tests/test_wp_pbp.py`.
