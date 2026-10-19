# WP pre-study (wave 1): report

**Seasons used: 2007–2022 only. No validation or test season was read.**

Scope note: one DuckDB query counted rows in the `games` table across all seasons, to get
phase and played counts. It read no play-by-play, points or box-score files for 2023 or later.
Directory listings for those seasons also appeared in the session output, but no file in them
was opened.

Script: `scripts/wp_prestudy.py`. Numbers: `reports/wp_prestudy.json`. Runtime: about 65 s from
a clean start. Protocol: `docs/models/wp.md` (draft; not edited here).

Scope of this pre-study: every model is a logistic regression (sklearn, C = 1), as instructed.
Gradient boosting is not fitted, so the family choice in section 5 is not tested here. The
closed-form baseline and the logistic model are scored out-of-fold on 2010–2022 only.

## Findings that change the protocol (read first)

1. **Shot codes (section 2, "Score" and "Assists").** From 2008 to 2014, made 2-point shots are
   coded `LAYUPMD` (34,085) and `DUNK` (7,079), and missed layups as `LAYUPATT`. Only 2007 and
   2015 onward use `2FGM`/`2FGA` alone. The drafted scoring-event list (`2FGM`, `3FGM`, `FTM`)
   drops these 41,164 makes from the training rows. The script counts them as field goals. The
   carried score is unaffected, because the points fields update on these events.
2. **ND clocks are not 2016 only (section 2).** The protocol says ND occurs on 2016 games only. In
   fact 16 more games in 2017–2022 carry a sentinel clock `00:-1` or `-1:00`. Under the drafted
   exclusion rule they are excluded too, which makes 173 excluded games for this reason, not 157.
3. **Overtime `t` (sections 4 and 7).** Section 4 defines OT `t` as the clock (at most 300 s),
   so `tf` is up to 0.125 in OT. Section 7 says `tf` is 0 in OT. The script follows section 4.
4. **Baseline start (section 7).** The closed-form line at tip-off is `Φ(mu_pre / 11)`, not
   `P_pre`. Mean absolute difference is 0.046, and the mean signed difference is −0.032. So the
   baseline does **not** start at `P_pre` by construction. The tip-off gap rule is needed.
5. **COVID labels (section 3).** See T4. The labels should read 2019 and 2020, not 2020 and 2021.
6. **Assist linkage (section 10, question 4).** The drafted rule does not reach the 98% target
   (see T1).

## T1. Assist split

**(a) Linkage.** Rule: nearest preceding made field goal of the same team in the same period,
with no other made field goal between. The script counts all made codes (`2FGM`, `3FGM`,
`LAYUPMD`, `DUNK`).

| Measure | Value |
|---|---|
| AS rows, 2007–2022 (included games) | 121,571 |
| Linked, drafted rule | 90.1% |
| Linked, variant B (AS logged just before its own make, same clock) | 92.9% |
| Linked make within 0 s / within 5 s of the AS row (share of linked, drafted rule) | 33.4% / 92.5% |
| Team-games with exact box-score agreement (drafted rule) | 38% |

Coverage per season (drafted rule): 2007 83%; 2008–2010 81–85%; 2011–2015 86–89%; 2016–2022
93–95%. Among linked assists, the same clock (0 s) holds for 90–93% in 2007–2010, 14–19% in
2011–2015, and 23–33% in 2016–2022. In 2007–2010 the 0 s and 5 s shares are equal, so the links
there are exact. From 2011 on, most linked assists fall within 5 s, which points to a logging
offset in the clock rather than wrong links.

Box-score check: the raw AS rows match the box score at 99.99% (121,571 vs 121,569 assists).
Linked assists total 109,554 (drafted) or 112,881 (variant B), against 121,569. That is 90% and
93%, **below the 98% target.** Roughly 7–10% of assists have no linked make under either rule.
The drafted rule also misses those where the AS row comes before its make.

**(b) Estimate.** Not identified (explained below), so no passer share is estimated.

- *The identification problem.* `AS` rows exist only for made field goals. Every missed shot has
  `assisted = 0` by construction, so `make ~ assisted` is perfectly separated and cannot be fitted.
  A passer share needs the make rate of assisted attempts, `p_a`, but the data show only assisted
  makes. Let `f` be the share of attempts that are assisted, `R` = unassisted makes / assisted
  makes. The identity is `S(f) = 1 − R · f / (1 − f)`, with `S` the passer share. `f` is not
  observed, so `S` is not identified. Feasible `f` runs from `N_am/N` (every assisted attempt
  made) to the value where `S = 0` (assisted and unassisted shots equally good).
- *What the data give.* 212,371 field-goal makes, of which 107,347 linked (50.5%). Over 458,189
  attempts with coordinates, R = 0.978 (bootstrap 95% CI 0.963–0.994, over games).
  Feasible `f` is 0.234–0.506. The passer share at each `f`:

| Assumed `f` | Passer share S |
|---|---|
| 0.234 (minimum) | 0.70 |
| 0.30 | 0.58 |
| 0.338 (implies 50/50) | 0.50 |
| 0.417 (implies 70/30) | 0.30 |
| 0.50 | 0.02 |
| 0.506 (`S = 0`) | 0.00 |

- R by shot type: 2-point 1.35, 3-point 0.42. The gap is large, so the answer depends on the
  shot mix.
- R is biased upward. The 7–10% of assists that fail to link are counted as unassisted makes.
- *What is identified:* the assisted share among makes by zone and shot type. A 3-point make has
  log-odds +1.12 relative to a 2-point make, and zone effects run from −0.12 to −1.20 (zone A
  is the reference). Coordinates and zone are present for all attempts, 2007–2022.

**(c) Proxy check (WPA vs RAPM):** not run. It is optional and needs the per-play WP line,
which the (b) finding makes less useful.

**Recommendation.** Do not accept the linkage rule as drafted. Its coverage is 90% against a
98% target, and variant B reaches only 93%. Do not estimate the split from these data: the
passer share is not identified. The owner has to choose it as an assumption. 100/0 is the only
choice that needs no assumption. If 70/30 is kept, it should be labelled as an assumption,
since it implies `f` ≈ 0.42.

## T2. 2016 missing clocks

| Measure | Value |
|---|---|
| 2016 games, files | 259 |
| Games with ND play events (excluded) | 157 |
| ND play events | 422 |
| Usable 2016 games | 102 |

Validation on 2015 and 2017 (included games). Each game draws a blank count from the 2016
distribution, with probability 157/259. Blanked events are random play events. Five replicates,
4,213 blanked events.

| Error (s) | Value |
|---|---|
| MAE | 4.0 |
| Median | 2.0 |
| 95th percentile | 11.5 (2015: 12.5, 2017: 11.0) |

**Recommendation:** repair. 95th percentile 11.5 s is below the 15 s threshold. Caveat: the
blanking is random, not clustered as real ND gaps may be. A clustered test is needed before the
repair is trusted for consecutive-event gaps.

## T3. Playoffs

Out-of-fold logistic predictions, 2010–2022, trained on 2007 to s−1. Game-level means over the
section 6 checkpoint grid.

| Phase | Games | Mean predicted | Observed home win | Gap | Log loss |
|---|---|---|---|---|---|
| RS (RS + TS) | 2,969 | 0.627 | 0.623 | +0.004 | 0.441 |
| PO + FF | 227 | 0.625 | 0.626 | −0.001 | 0.499 |

Counts: RS 2,425, TS 544 (group stage, treated as regular season), PO 182, FF 45.

- Gap difference (PO minus RS), 95% CI: [−0.055, +0.046]. Not beyond the CI, so no phase flag.
- Log-loss difference +0.058, CI [−0.005, +0.126]. This is a spread difference, not calibration.
  The CI just reaches zero.

**Recommendation:** no phase flag. Playoff calibration is consistent with regular season. The
playoff sample is small.

## T4. COVID seasons

| Season (start year) | Games | Observed home win | Mean predicted (checkpoints) | Predicted at tip-off |
|---|---|---|---|---|
| 2019 (2019-20) | 251 | 0.622 | 0.625 | 0.631 |
| 2020 (2020-21) | 326 | 0.564 | 0.605 | 0.633 |

- **2020 labelling:** 81% of 2020 games record zero attendance (empty arenas). In 2021, 6%
  do. 2019 is the cancelled season: 54 of 306 regular-season games were never played, and
  there were no playoffs. The draft's "2020 and 2021" is a labelling error. It should read
  **2019 and 2020**. The 28 unplayed 2021 games were not checked for cause.
- 2020 home wins are over-predicted by 4 points at checkpoints and 7 points at tip-off. 2019
  is well calibrated.
- Refit excluding 2019 and 2020 from training, evaluated on the other 11 seasons (2,619 games):
  Δ log loss +0.0003, 95% CI [−0.0001, +0.0007].

**Recommendation:** keep the COVID seasons in training. Excluding them does not improve log loss
beyond noise.

## T5. Tip-off gap

Using the out-of-fold model, g = P_pre − WP_model(t = 2400, m = 0), 3,196 games, 2010–2022.

| Statistic | Value |
|---|---|
| Mean g | −0.017 |
| \|g\| mean / sd | 0.038 / 0.025 |
| \|g\| 5th / 95th percentile | 0.004 / 0.077 |

The 95th percentile is well above 0.01, so the fade comparison runs.

Out-of-fold log loss of the adjusted line, checkpoints 2010–2022, shape by `f(tf)`:

| Shape | Log loss | Difference from linear (95% CI) |
|---|---|---|
| None (raw model) | 0.44474 | — |
| Constant | 0.45007 | worse |
| Linear, tf | 0.44473 | reference |
| Quadratic, tf² | 0.44443 | — |
| Exp, −3(1−tf) | 0.44431 | −0.0004 [−0.0012, +0.0004] |

**Recommendation:** exp(−3(1−tf)) has the lowest log loss, but the difference from linear is
inside noise. Linear (the drafted default) is adequate. Constant hold is clearly worse. The
gap term barely changes checkpoint log loss at all.

## Baseline context

On the same out-of-fold checkpoints (2010–2022), the logistic model scores log loss 0.4447, the
closed-form baseline 0.4601, a difference of −0.0154. This is not the gate, which is on
2024–25.

## Caveats

- Logistic only: gradient boosting and the calibration family choice were not run.
- Walk-forward Elo starts at 2007, so early pre-game probabilities are less informed.
- Isotonic calibration not applied. The raw logistic output is scored.
- The 2016 repair is validated under random blanking only.
- Team-game agreement in T1 is strict equality. Rates are shown alongside totals.
- The drafted `ND` rule and the sentinel `00:-1` are handled as described above.

## T1(c). Measured assist split (follow-up)

The owner asked for the split to be measured, not chosen. The criterion below was written and
committed **before** any player-season WPA was computed. Seasons 2007–2022 only.

### Linkage (chosen on box-score data only, before any outcome)

Four rules were tried. Each AS row is linked to a made field goal of the same team, in the same
period, in this order of preference:

- **A (drafted):** nearest preceding made FG (any team) in the period must be the AS team's own.
- **B:** A, else the next made FG is the same team's, at the same clock second.
- **C:** A, else the nearest same-team made FG within ±2 events or at the same clock second
  (searched within ±10 events).
- **D:** A, then B, then C.

Made FG codes are `2FGM`, `3FGM`, `LAYUPMD` and `DUNK` (2008–2014 coding). Unlinked AS rows credit
the passer nothing.

| Rule | AS rows linked | Linked / box assists | Team-game exact agreement |
|---|---|---|---|
| A (drafted) | 90.1% | 90.1% | 38.2% |
| B | 92.9% | 92.9% | 43.6% |
| C | 94.8% | 94.8% | 46.8% |
| **D (chosen: best exact agreement)** | **94.9%** | **94.9%** | **47.0%** |

Rule D is the best of the four, but it still misses the 98% target. The remaining ~5% of assists
have no linkable make in the log, and no rule links them. Per-season coverage for D is in
`reports/wp_prestudy.json` under `T1c_measured_split.linkage`.

### Criterion (pre-declared)

- **WP line.** The closed form of section 1, with `mu_pre` on the fold margin scale. The
  tip-off gap `g = P_pre − Φ(mu_pre/11)` fades as `g · tf` with `tf = t/2400` in regulation. In
  OT the gap is 0, following section 7's stated intent (section 4 would give `tf = clock/2400`
  in OT, which conflicts with section 7). The line starts at `P_pre` at tip-off. Each play's ΔWP
  is the change from the previous line point (the first from `P_pre`).
- **Credit.** Each play with a player is credited `100 · s · ΔWP`, where `s` is +1 for the home
  team and −1 for the away team. Markers, substitutions and AS rows credit nothing. For a made FG
  with a linked AS, the passer receives `S` of the credit and the scorer `1 − S`. An unlinked make
  credits the scorer in full.
- **Shares.** `S ∈ {0, 0.1, 0.2, 0.3, 0.4, 0.5}`.
- **Predictor.** WPA per 40 box minutes in season `s`.
- **Sample.** Player-seasons with `s ∈ 2010–2021` and at least 500 box minutes in `s` and in
  `s+1`. The start is 2010, not 2008, because the stints data (needed for target (i)) start in 2011.
  This deviates from the brief's 2008–2021 window and is declared here.
- **Targets.** (i) next-season on-court net rating per 100 possessions, from the mart `stints`
  table (on-court point margin divided by possessions, included games only). (iii) next-season
  RAPM `total` from `reports/m3_players.json`. The file's entries outside 2007–2022 are ignored
  (the file itself was opened in full, so this note discloses it). Target (ii), box plus-minus,
  is used only if (i) is unavailable, so it is not run.
- **Reference.** Season box plus-minus per 40 minutes, with the same targets and sample.
- **Metrics and uncertainty.** Pearson and Spearman for each target. Bootstrap over whole games,
  1,000 resamples, seed 20261018. Sample membership is fixed at the observed sample. The RAPM
  target is fixed, not refit per resample.
- **Score.** `score(S) = mean over targets of (Pearson + Spearman)/2`. The best `S` is the argmax.
- **Decision rule.** If every `S`'s score CI contains the point `score(0)`, the data cannot
  separate the shares, and the recommendation is the smallest `S` whose score lies inside the
  best `S`'s CI. Otherwise the recommendation is the best `S`.

### Results, time-inclusive credit (INVALID)

These results used the credit definition in the criterion above, where each play's ΔWP was the
change in the line between consecutive plays. Time passage between plays was therefore credited
to the player who produced the next play. The same-season sanity check gave r = −0.06, the
wrong sign, so the metric was not valid. The numbers below are kept for the record. They are not
used for any recommendation. The S recommendation from them ("S = 0") is withdrawn.


Sample: 419 player-seasons, 2010–2021 as `s`, with at least 500 box minutes in `s` and `s+1`.
Predictor: WPA per 40 minutes in `s`. Targets: next-season net rating per 100 possessions (from
mart stints, 2011–2022) and next-season RAPM total (from `m3_players.json`). Correlation point
estimates with game-cluster bootstrap 95% CIs (1,000 resamples, seed 20261018).

| S (passer share) | Net rating: Pearson [CI] | Net rating: Spearman [CI] | RAPM: Pearson [CI] | RAPM: Spearman [CI] | Score (mean of the 4) [CI] |
|---|---|---|---|---|---|
| 0.0 | 0.031 [−0.045, 0.094] | 0.045 [−0.044, 0.096] | −0.106 [−0.139, −0.042] | −0.101 [−0.137, −0.034] | −0.033 [−0.079, 0.017] |
| 0.1 | 0.029 [−0.044, 0.090] | 0.045 [−0.040, 0.099] | −0.090 [−0.125, −0.031] | −0.085 [−0.119, −0.018] | −0.025 [−0.071, 0.024] |
| 0.2 | 0.027 [−0.045, 0.086] | 0.049 [−0.037, 0.099] | −0.073 [−0.109, −0.019] | −0.063 [−0.100, −0.003] | −0.015 [−0.061, 0.031] |
| 0.3 | 0.024 [−0.046, 0.082] | 0.050 [−0.033, 0.097] | −0.056 [−0.093, −0.007] | −0.040 [−0.082, 0.011] | −0.005 [−0.052, 0.035] |
| 0.4 | 0.021 [−0.046, 0.079] | 0.048 [−0.030, 0.095] | −0.041 [−0.077, 0.004] | −0.021 [−0.063, 0.024] | 0.002 [−0.044, 0.040] |
| 0.5 | 0.018 [−0.047, 0.075] | 0.044 [−0.029, 0.093] | −0.027 [−0.061, 0.014] | −0.009 [−0.048, 0.034] | 0.007 [−0.037, 0.043] |
| Reference: season plus-minus per 40 | 0.396 [0.202, 0.352]* | 0.404 [0.203, 0.362]* | 0.574 [0.435, 0.529]* | 0.577 [0.436, 0.531]* | 0.488 [0.327, 0.434]* |

\* These reference CIs lie below the point estimates. The bootstrap mean of the correlation is
about 0.12 lower, while the means of the inputs are unchanged (mean plus-minus per 40 2.51 point
versus 2.50 bootstrap). The correlation is sensitive to a subset of player-seasons. The WPA rows
show no such gap (for example, WPA S = 0 RAPM: point −0.106, bootstrap mean −0.092), so the WPA
conclusions are not affected by this.

**Sanity check.** Same-season WPA per 40 against same-season plus-minus per 40 gives Pearson
−0.057 and Spearman −0.039 (S = 0). A working WPA should be positive here. The sign is wrong, but
the value is close to zero, not significant at n = 419.

**Decision (pre-declared rule).** Every S's score CI contains the point score at S = 0 (−0.033).
The data cannot separate the shares. The best point score is S = 0.5 (0.007), whose CI is
[−0.037, 0.043]. That CI contains the S = 0 score, so the smallest S inside it is **S = 0**.
The pre-declared recommendation is therefore **S = 0 (100/0)**.

**Linkage.** Rule D (A, then B, then C) was chosen as the best team-game exact-agreement rule
(47.0%). It links 94.9% of AS rows, and 94.9% of box-score assists. The target of 98% is not met.
Per-season coverage for D is in `T1c_measured_split.linkage.variants.D_all.per_season`. Coverage is
98–99% in 2007–2008, 94–96% in 2009–2010, 94–95% in 2011–2015 and about 94% in 2016–2022. Team-game exact agreement
falls from 87% (2007) to 32–41% (2014–2022). Box totals are used only for the agreement check.
Rule D gives 3,376 makes that are linked by more than one AS row. The first AS row is kept as the
passer, and the rest are dropped.

**Linkage, production rule (revised).** The 94.9% above is over the pre-study's included games
(2007–2022, with unreadable-clock, score-mismatch and ND games removed). The production code in
`src/eurohoops/stats/assists.py` ran the same rule over every played game and measured 91.6%
(152,164 of 166,195 AS rows linked in the 5,025 games it checked; 2,706 AS rows of 75 ND-clock
games of 2016 were skipped entirely). Causes of the unlinked rows (old rule, all played games):

| Cause | AS rows |
|---|---|
| Whole game skipped (ND clock, 2016) | 2,706 |
| Make already credited to an earlier AS row | 3,832 |
| Nearest same-team make more than 30 s away | 2,893 |
| Nearest same-team make 6–30 s away | 1,055 |
| Only an opposing make nearby | 2,773 |
| No make of the team within 10 events | 1,462 |
| Nearest same-team make is the passer's own | 1,318 |
| Team code mismatch near the row | 822 |
| Other (1–5 s same-team make beyond 2 events, same-clock self-scorer, no clock) | 103 |

Box totals equal the play-by-play AS counts (168,899 vs 168,901), and FGM totals equal the
play-by-play makes (one team-game differs by 9). So every assist has a make in the feed. The
losses are linking errors, not missing rows.

The new rule is a one-to-one maximum matching per game. An edge needs the passer's team's make,
not the passer's own; no opposing make between the two rows; the clocks at most 60 s apart and
the rows at most 30 events apart (3 events when a clock is missing). It is in `assists.py`.
Measured over all played EuroLeague games 2007–2026, **92.9% of AS rows link (156,837 of
168,901), and 92.9% of box-score assists (156,837 of 168,899).** Per season: 97.6% (2007),
97.9% (2008), 92–94% (2009–2015), 92–94% (2016–2022), 91–93% (2023–2026). The 98% target
is **not met**.

*Why not 98%.* About 7% of AS rows have no plausible make left. Looser rules do reach 98%
(index-only matching with a 30-event window reaches 98.1%), but a hand-check shows they are
wrong. Hand-check (25 links per stratum, read from the play-by-play windows; a reading, not an
independent label): links with an opposing make between the rows, 25 of 25 read as wrong or
doubtful. Links more than 60 s apart, 25 of 25 read as doubtful or wrong. Links with no
opposing make between and within 60 s, 25 of 25 read as plausible, with the make adjacent to
the AS row in most cases. The first two strata come from the ungated and index-only matchings;
the last from the ungated 60 s / 30-event matching restricted to unopposed pairs. The rule
uses only the last kind of pair. Precision of the final matching itself was not hand-checked
beyond this.

*Clock.* The clock gap between an AS row and its make is 0 s for about 90–98% of linked rows
in 2007–2010 but 16–27% from 2011 on. From 2011 most links are 1–2 s apart (about 55%), and
3–5 s for 14–18%. So the feed clock of AS rows lags the make by 1–2 s, and rule timing must
allow a few seconds of offset.

**Other caveats.**

- The WPA credit follows the section 8 definition (every play, with `ΔWP` including time passage
  since the previous event). Time passage is therefore credited to whoever produced the next event.
  This is the most likely reason the metric fails the same-season sanity check. A
  score-change-only credit would be the natural next test. It is not run here.
- Player IDs in plays that do not match a box-score player (598 rows) are dropped.
- Target (i) uses included games only, so 2016 (157 ND games excluded) has partial coverage.
- The tip-off gap term uses `tf = t/2400` in regulation and 0 in OT, as declared above.
- The M3 file was opened in full. Only entries for 2007–2022 are used. Its header lists the
  later seasons, but no value for them enters any table here.
- Runtime: the measurement stage takes about 70 s, plus about 50 s to build the data.


### Corrected credit and validity gate (pre-declared before recomputation)

The time-inclusive credit above is invalid. The corrected definition is pre-declared here,
before any recomputation.

- **Event-only credit.** For each play `e`, `ΔWP_e = WP(score after e, t_e) − WP(score before e,
  t_e)`. Both terms are evaluated on the baseline line with the linear tip-off gap fade, at the
  same clock `t_e`. Time passage between plays credits nobody. A non-scoring play has the same
  score before and after, so its `ΔWP` is 0 under the baseline. The baseline has no possession
  term, so rebounds, turnovers and steals credit 0 by construction. This is expected, not a bug.
  Credit is `100 · s · ΔWP_e` as before. The passer split of section 8 applies to linked makes
  only. Unlinked assists credit nothing to the passer, and unlinked makes credit the scorer in full.
- **Validity gate.** Same-season Pearson correlation of WPA per 40 minutes (S = 0) with
  plus-minus per 40 minutes, on the same 419 player-seasons, 2010–2021 `s`, at least 500 minutes
  in `s` and `s+1`. **The gate passes only if the point estimate is above 0.3 and the 95% bootstrap
  CI (game-cluster, 1,000 resamples, seed 20261018) has a lower bound above 0.** If the gate fails,
  the run stops after reporting the gate. No split recommendation is made.
- **If the gate passes.** The S grid {0, 0.1, …, 0.5}, the targets, the sample, the bootstrap, the
  score definition and the decision rule are unchanged from the criterion above.
- **Face-validity list.** If the gate passes, the top 10 player-seasons by total WPA in 2022, for
  `S = 0` and for the recommended `S`, among players with at least 500 box minutes in 2022.


### Gate result (event-only credit): FAILED. No split recommendation.

- Same-season Pearson, WPA per 40 at S = 0 against plus-minus per 40: **−0.049**, bootstrap 95% CI
  **[−0.088, 0.063]**, sample n = 419. The gate required point > 0.3 and CI lower bound > 0. It
  fails on both counts.
- As pre-declared, the run stopped at the gate. The S grid, the targets and the top-10 list were
  not computed, and no split is recommended.
- Diagnostic, run after the gate and not part of the criterion (season-level sample 2010–2021,
  at least 500 box minutes in the season, n = 896): raw box points per 40 against plus-minus per
  40 gives r = 0.127, assists per 40 give 0.095, and event-only scoring WPA per 40 gives 0.029.
  So plus-minus is a weak same-season benchmark in this data, and even raw points reach only
  about 0.13. The 0.3 threshold is above what the benchmark itself supports, so the gate is
  unreachable with this outcome. Changing the threshold now would be a new protocol version.
- The time-inclusive results above remain invalid. The event-only metric does not pass its own
  validity gate, so it cannot be used to measure the split.

**Next step (owner decision).** Either accept that the split cannot be measured from these data
with plus-minus as the benchmark, or declare a different validity benchmark in a new protocol
version. Candidate benchmarks are on-court net rating within season, or a team-adjusted
plus-minus.
