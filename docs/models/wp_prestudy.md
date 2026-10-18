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
