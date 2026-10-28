# Research ideas: ranked, with draft gates

Status: **DRAFT, nothing committed.** These gates are proposals for the owner to accept, edit or drop. None is pre-registered until the owner commits it. Nothing here changes model code, gates or `predictions/`.

Source of ideas: the 32 paper notes in [papers/](papers/) and the topic summaries in [topics/](topics/). The index is at [INDEX.md](INDEX.md). The website backlog in `docs/IDEAS.md` is a separate file.

## Rules every idea follows
- No re-tuning of M1 or M5 on the validation or test splits already used (PLAN §8.1). Each idea is tested on new information, a fresh season, or live games logged **after** its gate is committed.
- `predictions/*.csv` and `odds/*.csv` stay append-only. A new forecaster gets its own new file.
- Team codes stay as the source codes.

## How ideas are ranked
Score = (expected gain × confidence) / effort.
- **Gain** (1–3): the expected effect on log loss for the flagship or published forecast. For evaluation ideas, it is the value of the decision the result informs.
- **Confidence** (1–3): how well the papers and our own numbers support the gain.
- **Effort**: S = 1 (under a day), M = 2 (a few days), L = 3 (a week or more).

| Rank | ID | Idea | Model | Gain | Conf. | Effort | Score |
|---|---|---|---|---|---|---|---|
| 1 | E1 | Power check for the R1 promotion looks | evaluation (M5, M1, Elo) | 2 | 3 | S | 6.0 |
| 2 | B1 | Market as a logged forecaster, plus an encompassing test | benchmark (all) | 2 | 3 | S | 6.0 |
| 3 | A1 | Injury-aware minutes for M5 (`M5-INJ`) | M5 (EuroLeague) | 2 | 2 | M | 2.0 |
| 4 | B2 | Early-season totals check against the market | M1/M5 totals | 1 | 2 | S | 2.0 |
| 5 | C1 | Spread-recalibrated POOL (`POOL-c`) | POOL | 1 | 1 | S | 1.0 |
| 6 | C2 | Redundancy screen of POOL members | POOL | 1 | 1 | S | 1.0 |
| 7 | D1 | Season-start state-space prior for M1 (`M1-SS`) | M1 | 2 | 1 | L | 0.67 |
| 8 | D2 | Team-specific home advantage, shrunk (`ELOH`) | Elo shadow | 1 | 1 | M | 0.5 |

Ties are broken by effort, then by whether the idea needs new data collection.

---

## E1. Power check for the R1 promotion looks
- **Model:** evaluation of M5 vs Elo (EuroLeague) and M1 vs Elo (GBL). No model change.
- **Change:** before EuroLeague round 19, write down the chance that R1 can promote at each look, given realistic gaps.
- **Why:**
  - Shared outcomes and randomness cap what small samples can show ([brill-2024](papers/brill-2024-difficulty-win-probability.md), [lopez-2017](papers/lopez-2017-how-often-best-team-wins.md)).
  - Small claimed gaps are often noise ([tian-2024](papers/tian-2024-spectral-dynamic-bradley-terry.md)).
- **Rough estimate from our own cards:**
  - The M5 − M1 test CI half-width is 0.0096 on 732 games (`docs/models/m5.md`), so the per-game gap SD ≈ 0.13.
  - M1 − Elo is 0.0062 on its test, so the SD ≈ 0.09.
  - At round 19 (about 190 EuroLeague games) the SE is about 0.007–0.009. A two-sided 97.5% CI clears 0 only if the observed gap is below about −0.016 to −0.021.
  - The test gaps so far are −0.0013 (M1 − Elo) and about 0 (M5 − M1). If the true gap is −0.003, the chance of promotion at round 19 is about 4% (reader's arithmetic, normal approximation).
- **Data:** have it (backtest JSONs, live logs).
- **Draft gate:** none. This is a report, not a model test. Output: a table of promotion probability by true gap (−0.003, −0.005, −0.01, −0.02) and by look (round 19, season end), for both competitions.
- **Risks:**
  - The SD estimate comes from past seasons. Live 2026-27 games may differ.
  - The result may lead the owner to change R1. Any change must be declared as a new rule version before the look it affects, never after seeing results.

## B1. Market as a logged forecaster, plus an encompassing test
- **Model:** a benchmark forecaster `MKT` (de-vigged home-win probability from `odds/euroleague_2026-27.csv`), scored beside Elo, M1, M5 and POOL. EuroLeague only.
- **Change:**
  - Score `MKT` on the forecasts page as a model. Use the latest snapshot before tip-off, which today has a median of 3.8 h before tip, with 12 of 40 games within 3 h.
  - Run a Colquitt-style encompassing test: a logistic regression of home win on logit(MKT) and logit(model). It asks whether each model adds information the market lacks.
- **Why:**
  - Results-only models at best tie the market: tied in the NBA ([lopez-2017](papers/lopez-2017-how-often-best-team-wins.md), Table 5), lost in the EPL ([ridall-2025](papers/ridall-2025-epl-bayesian-state-space.md), Table 3).
  - Closing lines are rational ([colquitt-2001](papers/colquitt-2001-ncaa-betting-efficiency.md)) and absorb absence news ([dare-2015](papers/dare-2015-player-absence-nba-lines.md)).
  - Proportional de-vig is the literature standard ([robbins-2022](papers/robbins-2022-sports-betting-efficiency.md)), so `odds.py` needs no change.
- **Data:** have it for EuroLeague 2026-27 (40 games so far). The GBL has no odds.
- **Draft gate (benchmark report, declared before the season-end look):**
  - Metric: mean per-game log loss and Brier on games where both `MKT` and the model have a pre-tip row.
  - Evaluation data: EuroLeague 2026-27 games played after the gate commit, through season end.
  - Report: paired bootstrap CI of (model − MKT) for each model, plus the encompassing regression coefficient on logit(model) with a 95% CI.
  - Pass rule: none. It is a benchmark. "Model adds information" is declared if the logit(model) coefficient's 95% CI excludes 0.
- **Risks:**
  - Snapshot timing varies (0.6 h to 172 h before tip). Report results by snapshot lead time.
  - API quota (347 requests left at the last call). Do not add fetches without checking the budget.
  - `MKT` must never feed a model without its own gate.

## A1. Injury-aware minutes for M5 (`M5-INJ`)
- **Model:** M5, EuroLeague. A new shadow model logged to its own file (for example `predictions/euroleague_m5inj_2026-27.csv`).
- **Change:** before the minutes projection, set to zero the projected minutes of any player whose latest BasketNews status before the information cutoff is `Out`, and renormalise the team's minute shares. Every other part of M5 stays as pinned. `Uncertain` is left unchanged in v1 (declared, not tuned).
- **Why:**
  - M5's gap to oracle minutes sits in games where a top-3 minute-taker is missing: margin RMSE +0.84, CI [0.08, 1.65], on 31 test games (`docs/models/m5.md`).
  - `proj_avail` only reacts after two missed games. The injury feed can flag the absence before the first one.
  - Opening lines misprice absences and closing lines mostly do not ([dare-2015](papers/dare-2015-player-absence-nba-lines.md), Tables 2–3).
  - The NBA's large week-to-week noise is blamed on injuries ([lopez-2017](papers/lopez-2017-how-often-best-team-wins.md), p.18).
- **Data:** have it from 2026-10-07: `injuries/euroleague_2026-27.csv` (11 snapshots so far). EuroLeague only; there is no GBL feed. Player names must be matched to EuroLeague player IDs; the BasketNews ID is in the file.
- **Expected effect:** small on average. Oracle minutes beat projected minutes by only about 0.003 log loss on test (0.620074 vs 0.623203), so the injury feed can recover at most part of that. Most of the gain falls on the few games with a key absence.
- **Draft gate (style of `docs/models/m5.md`):**
  - Question: does `M5-INJ` beat M5 on EuroLeague home-win log loss on live games?
  - Evaluation data: EuroLeague 2026-27 games that both M5 and `M5-INJ` logged after the gate commit, through season end (about 250 games).
  - Primary metric: mean per-game log-loss difference (`M5-INJ` − M5), paired bootstrap over games, 10,000 resamples, fixed seed.
  - Secondary metric: the same on the subset where at least one player with a projected share ≥ 0.10 was marked `Out` (declared before the run; counts reported).
  - Pass rule: 95% CI upper bound of the primary difference < +0.002 (non-inferiority) **and** a negative mean on the secondary subset. Report margin RMSE too.
  - Matching rule: name/ID matching is declared, and unmatched rows are reported, before any scoring.
- **Risks:**
  - Snapshot timing: a status may change after the last snapshot before cutoff. Use only snapshots taken before the cutoff.
  - The feed is unofficial and may stop.
  - Small affected subset: the secondary test will have low power (see E1).
  - The market already prices this ([dare-2015](papers/dare-2015-player-absence-nba-lines.md)), so the gain against B1's `MKT` is likely zero even if `M5-INJ` beats M5.

## B2. Early-season totals check against the market
- **Model:** M1/M5 totals (EuroLeague). Diagnostic first.
- **Change:** compare the market total and the M1 total with actual totals by round bucket (rounds 1–5, 6–10, 11+).
- **Why:** NBA totals lines run high early in the season. After a downward line move, unders won 61.9% at the open and 56.7% at the close, and the bias faded by about the 10th home game ([baryla-2007](papers/baryla-2007-nba-early-season-totals-bias.md), Table 3, p.7). M1 has a pace model with a 60-day half-life and full carry, so it may share the same early-season lag.
- **Data:** market totals in `odds/euroleague_2026-27.csv` (rounds 1–8 so far). M1 totals in the predictions logs.
- **Draft gate:** diagnostic report only, declared before EuroLeague round 11.
  - Metric: mean (line − actual) and (M1 total − actual) with bootstrap CIs, by bucket.
  - "Early-season bias present" is declared if the rounds 1–5 CI excludes 0 and the rounds 11+ CI does not.
  - Any model fix would be a separate shadow model with its own gate, tested on the 2027-28 season start.
- **Risks:** about 50 EuroLeague games per 5-round bucket, so the power is low. One season cannot separate a bias from a season-level scoring shift.

## C1. Spread-recalibrated POOL (`POOL-c`)
- **Model:** POOL (EuroLeague).
- **Change:** pool logit = c × (equal-weight log pool logit). One parameter c, fitted by log loss on POOL's live rows up to EuroLeague round 19, then frozen.
- **Why:**
  - A spread adjustment can fix pools that are under- or over-confident ([wang-2022](papers/wang-2022-forecast-combinations-review.md), p.29).
  - But Baran & Lerch found "no substantial differences" from fancier pools (p.30), and estimated weights are noisy on small samples ([gupta-1987](papers/gupta-1987-combination-of-forecasts.md), Table 3). Hence low confidence.
- **Data:** have it (live POOL rows).
- **Draft gate:**
  - Fit c on POOL's rows for rounds 1–19 (declared now, before round 19).
  - Evaluate rounds 20 to season end: paired bootstrap of (`POOL-c` − POOL) log loss.
  - Pass rule: 95% CI upper bound < 0. Otherwise POOL stays as is.
- **Risks:** only about 190 fitting games, so c will be noisy. If c is near 1, the test has nothing to find.

## C2. Redundancy screen of POOL members
- **Model:** POOL.
- **Change:** report the correlation of the members' logits and of their per-game log-loss residuals on live games. If Elo and ELOR are nearly identical (logit correlation > 0.98, declared now), declare a three-member `POOL3` (ELOR, M1, M5) as a new shadow model.
- **Why:** Wang reports that "many could be better than all" and recommends screening near-duplicate members ([wang-2022](papers/wang-2022-forecast-combinations-review.md), p.18–19). ELOR equals Elo after its fade-out rounds by construction (`docs/models/elo_roster_prior.md`), which gives Elo double weight later in the season.
- **Data:** have it.
- **Draft gate (`POOL3`, only if the screen triggers):** live games after its commit through season end. Paired bootstrap of (`POOL3` − POOL) log loss. Pass: 95% CI upper bound < 0.
- **Risks:** an expected effect near zero. Double weight on Elo may even help if Elo is the best member.

## D1. Season-start state-space prior for M1 (`M1-SS`)
- **Model:** M1 (both competitions).
- **Change:**
  - Replace the season carry (last season's rows weighted 0.25) with a prior on each team's off/def rating centred at γ × last season's end-of-season rating.
  - Keep within-season decay near zero.
  - γ is set from the literature, not tuned: **γ = 0.7**, the midpoint of Lopez's NBA 0.62 and Glickman's 0.82.
- **Why:**
  - M1 trails Elo in EuroLeague rounds 1–5 (0.5947 vs 0.5784, `docs/models/m1.md`).
  - Its carry sits on the grid minimum, and the same parameter does two jobs: discounting old seasons and reverting at season start.
  - The papers separate the two jobs. Within-season drift is small; season-start reversion is 18–46% ([glickman-1998](papers/glickman-1998-nfl-state-space.md), [lopez-2017](papers/lopez-2017-how-often-best-team-wins.md)). Ridall finds almost none ([ridall-2025](papers/ridall-2025-epl-bayesian-state-space.md)), which is a disagreement.
  - Teams with roster churn jump more ([macridemartino-2026](papers/macridemartino-2026-dynamic-bradley-terry.md)).
- **Data:** have it.
- **Draft gate:**
  - Evaluation data: fresh seasons only. EuroLeague and GBL 2027-28, every game both M1 and `M1-SS` log, from round 1.
  - Primary metric: log-loss difference (`M1-SS` − M1) on rounds 1–10, paired bootstrap.
  - Secondary metric: the same on the full season.
  - Pass rule: 95% CI upper bound of the primary < 0 **and** a full-season mean ≤ 0.
  - Report both competitions separately; the GBL is the M1 flagship case.
- **Risks:**
  - About 100 EuroLeague games in rounds 1–10 per season, so power is low (E1). It may need 2028-29 pooled too, which must be declared up front.
  - The fixed γ may be wrong for EuroLeague roster churn.
  - The largest effort here: a new prior structure in the ridge fit.

## D2. Team-specific home advantage, shrunk (`ELOH`)
- **Model:** a new Elo shadow (EuroLeague first).
- **Change:** hca_team = 90 + δ_team. δ_team is estimated from home-minus-expected results on seasons 2007–2023 only, shrunk toward 0 by a hierarchical (empirical Bayes) factor. Everything else is frozen live Elo.
- **Why:**
  - Lopez finds team-specific home advantage better by DIC in the NBA (−323.9, SE 40.5; Table 2, p.12). Glickman's single home advantage failed its check (p.9).
  - But neither shows an out-of-sample gain, and Szczecinski and Macrì-Demartino keep one value ([topics/score-distributions-and-home-advantage.md](topics/score-distributions-and-home-advantage.md)).
  - `docs/models/diag_home_court.md` found no evidence that the common hca 90 is wrong.
- **Data:** have it.
- **Draft gate:** live EuroLeague games after commit through season end, plus 2027-28. Paired bootstrap of (`ELOH` − Elo) log loss. Pass: 95% CI upper bound < 0.
- **Risks:**
  - Team home effects may not persist across seasons (arenas, crowds and rosters change).
  - Fitting on 2007–2023 avoids the Elo tuning and test seasons (2024, 2025), but the δ estimates are noisy.
  - Expected gain is very small.

---

## Ideas considered and not listed
- **In-game WP:** a closed-form Brownian baseline ([albert-2015](papers/albert-2015-win-probability-player-evaluation.md), [shimizu-2026](papers/shimizu-2026-stats-x-realtime-wp.md)), a pre-game logit input and a whole-game bootstrap ([brill-2024](papers/brill-2024-difficulty-win-probability.md)) are **already in** `docs/models/wp.md`. Late-game over-dispersion ([martingonzalez-2016](papers/martingonzalez-2016-poisson-limits-nba.md)) is covered by its calibration-by-time-bucket report.
- **Student-t vs Normal margins:** Glickman found no predictive gain from Student-t. M1's df were tuned on used splits, so there is nothing to test without re-tuning.
- **Kernel or Kalman ratings instead of Elo** ([tian-2024](papers/tian-2024-spectral-dynamic-bradley-terry.md), [duffield-2023](papers/duffield-2023-state-space-skill-rating.md), [szczecinski-2021](papers/szczecinski-2021-simplified-kalman-rating.md)): reported gains are inside the noise, with no significance tests.
- **Learned stacking** ([he-2025](papers/he-2025-stacked-ensemble-nba.md)): its result is leakage; the equal-weight POOL is the literature-backed choice.
- **Bridge penalty for RAPM** ([zanini-2024](papers/zanini-2024-variational-bayesian-bridge.md)): there is no predictive evidence, and M5's binding problem is minutes, not rating shrinkage.
- **Ten off-topic papers** (clinical trials, pure mathematics, count time series, team formation, model-selection theory): no grounded ideas. See [INDEX.md](INDEX.md).


---

## New ideas from the 2026-10-28 scan (DRAFT, not pre-registered)

Source: the scan log in [search_log_2026-10-28.md](search_log_2026-10-28.md) and the notes in [papers/](papers/) (local, gitignored, as for the other notes). Nothing here is committed to a gate. Each idea follows the rules above.

Ranking: same score as the table above (gain × confidence / effort). Scores are the scan's estimates.

| Rank | ID | Idea | Model | Gain | Conf. | Effort | Score |
|---|---|---|---|---|---|---|---|
| 1 | F1 | Point-in-time and leakage audit of every model input | all, esp. M5-INJ | 2 | 2 | S | 4.0 |
| 2 | F2 | Two-way (team-pair and round) bootstrap for the promotion test | evaluation | 2 | 2 | S | 4.0 |
| 3 | F3 | No-crowd games in the home-advantage fit (2020-21) | Elo, M1 | 1 | 2 | S | 2.0 |
| 4 | F4 | Two-parameter Platt recalibration of POOL (refines C1) | POOL | 1 | 2 | S | 2.0 |
| 5 | F5 | Out-of-season check of player-based team strength (Win Shares, RAPM) | M5, Win Shares | 1 | 1 | S | 1.0 |
| 6 | F10 | Back-to-back flag as a rest term | Elo, M5 | 1 | 1 | S | 1.0 |
| 7 | F6 | Saturating expected-margin Elo shadow | Elo shadow | 1 | 1 | S | 1.0 |
| 8 | F9 | Home-favourite test in the market benchmark | B1 | 1 | 1 | S | 1.0 |
| 9 | F7 | Negative-binomial points model for totals | M1 totals | 1 | 1 | M | 0.5 |
| 10 | F8 | Dummy indicators for excluded low-minute players | M5 | 1 | 1 | M | 0.5 |

Guard (no score): no streak or "form" features without a bias-corrected test (see G0 below).

---

## F1. Point-in-time and leakage audit of every model input
- **Model:** all live models; M5-INJ first (its BasketNews snapshots).
- **Change:** for each input, record the time it was first known, and check that every pre-game forecast uses only information dated before tip-off. Run a shuffled-label and "future-row" check on the feature pipeline. No model change if it passes.
- **Why:**
  - The point-in-time gate is the first of six readiness gates in [zhou-guan-2026](papers/zhou-guan-2026-metrics-to-decisions.md) (abstract only).
  - A reported 98.9% EuroLeague accuracy from box-score features is the leakage pattern to rule out ([balli-2021](papers/balli-2021-euroleague-98pct.md), abstract only); the NBA 83% case is in [he-2025](papers/he-2025-stacked-ensemble-nba.md).
- **Data:** have it (snapshot timestamps and ingest logs). Check the BasketNews snapshot times.
- **Draft gate:** an audit table (input, first-known time, used at forecast time, pass or fail) committed before the report. Any fail is fixed and logged as a new version, not hidden. Output is a report; no promotion test.
- **Risks:** the audit may find a leak that changes past backtest numbers. Report those numbers as they were, with the correction beside them. Never edit `predictions/` rows (rule 1).

## F2. Two-way (team-pair and round) bootstrap for the promotion test
- **Model:** evaluation of the paired test in `eval/promotion.py` (M5 vs Elo, M1 vs Elo, POOL vs Elo).
- **Change:** add a sensitivity run that clusters the paired bootstrap by both round and team pair (dyadic), alongside the current round clustering. Report both. The pass rule is unchanged unless the owner later changes it through the rule-change process.
- **Why:**
  - The dyadic bootstrap is the method for recurring teams in [pipping-gamon-2026](papers/pipping-gamon-2026-blown-lead.md) (abstract only). It widens intervals when the same teams repeat.
  - INDEX already notes shared outcomes shrink the effective sample ([brill-2024](papers/brill-2024-difficulty-win-probability.md), [lopez-2017](papers/lopez-2017-how-often-best-team-wins.md)).
- **Data:** have it (live logs and backtest JSONs).
- **Draft gate:** the sensitivity CI is reported next to the standard CI at each look. If the dyadic CI is wider, the look is reported as "not decided under the sensitivity run". No change to the pass rule.
- **Risks:** more conservative intervals make promotion harder. That is the point, but it changes what E1 implies, so rerun E1 if this is adopted.

## F3. No-crowd games in the home-advantage fit (2020-21)
- **Model:** Elo (hca 90 for EuroLeague) and M1's home term.
- **Change:** a backtest variant that excludes, or gives a separate home term to, the 2020-21 games played without fans. The fit uses earlier seasons only, so the walk-forward rule holds.
- **Why:**
  - [de-angelis-2023](papers/deangelis-2023-ghost-games-euro-basketball.md) reports an overall home-advantage drop of about 5% in ghost games across ten European leagues since 2004, with no recovery over time (abstract only).
  - INDEX already lists one home effect for all seasons as an M1 weakness.
- **Data:** have it if the 2020-21 games carry a crowd flag or a date range. Check the ingest. If not, the no-crowd date range has to be sourced first.
- **Draft gate:** a backtest on past seasons, not a fresh test. It is a model choice, so it needs the owner's approval and must be declared before it touches a live forecast. Proposed pass bar: a backtest log-loss gain of at least 0.005, with the paired CI excluding zero on 2021-22 and later. Not pre-registered.
- **Risks:** the 5% figure is pooled across European leagues, not EuroLeague-specific. The gain may be zero if home advantage has already recovered.

## F4. Two-parameter Platt recalibration of POOL (refines C1)
- **Model:** POOL (equal-weight logit pool of Elo, ELOR, M1, M5).
- **Change:** instead of a spread recalibration, fit a two-parameter Platt map (slope and intercept on the pool logit) on earlier seasons only, and hold it fixed for the live season. A one-parameter temperature (Guo et al.) is the lighter option. Isotonic is excluded.
- **Why:**
  - [niculescu-mizil-2005](papers/niculescu-mizil-2005-good-probabilities.md): isotonic overfits when data are scarce; Platt does better with small samples.
  - [guo-2017](papers/guo-2017-temperature-scaling.md): a single temperature works well in neural networks (abstract only).
  - INDEX: linear pools are under-confident; recalibration gains are uncertain.
- **Data:** have it (pool logits from backtests).
- **Draft gate:** this is C1 with a specified form. Fit on seasons before the scored season; pass bar as in the standard test. Not pre-registered.
- **Risks:** with 40 to 200 live games the slope has wide uncertainty. Report the fitted slope with its CI; if the CI covers 1, do not apply it.

## F5. Out-of-season check of player-based team strength (Win Shares, RAPM)
- **Model:** M5 roster inputs and the Win Shares player metric (in progress).
- **Change:** test whether last season's player metrics predict this season's team margins better than the current RAPM-based ratings. Score by log loss of the implied win probability, and use the three meta-metrics (stability, discrimination, independence) as diagnostics.
- **Why:**
  - [paine-2009](papers/paine-2009-win-shares-vs-ewa.md) checks Win Shares only against same-season team wins, which is close to an identity by construction.
  - [franks-2016](papers/franks-2016-meta-analytics.md) gives the three criteria (abstract only).
  - [sill-2010](papers/sill-2010-regularized-apm.md) argues for judging APM by out-of-sample game prediction (abstract only).
- **Data:** have it for EuroLeague box scores if the ingest holds them; check that Win Shares inputs exist for past seasons.
- **Draft gate:** rolling-origin test on earlier seasons only. Proposed pass bar: log-loss gain over the current M5 input, paired CI excluding zero, before any live use. Not pre-registered.
- **Risks:** Win Shares is a box-score metric and may only repeat what M5's box-score prior holds; the independence criterion would show that.

## F10. Back-to-back flag as a rest term
- **Model:** Elo (rest term) and M5 (minutes projection context).
- **Change:** a binary flag for a second game in under 36 hours, or a rest-days term with one-day and two-day levels. Shadow only.
- **Why:**
  - [esteves-2021](papers/esteves-2021-nba-back-to-back.md) reports a significant win-likelihood increase from back-to-back to one day of rest, NBA 2016-17 (abstract only; no odds ratio read).
  - [bozhidarova-2026](papers/bozhidarova-2026-streaks-synergies-nba.md): back-to-back second games win 44% against an "expected 50%" (section 3.2). The baseline is flat, so the right test is against a model-based expectation.
  - INDEX: rest effects are noise in M5 (current result).
- **Data:** have it if EuroLeague game dates are in staging (check double-round weeks).
- **Draft gate:** shadow on live games only, declared after this scan, as a new file in `predictions/`. No change to Elo. Test: standard paired bootstrap at the round-19 look.
- **Risks:** INDEX already shows rest effects as noise on EuroLeague, so expect a null. The look may not reach power (see E1).

## F6. Saturating expected-margin Elo shadow
- **Model:** Elo shadow (`ELO-T`, not yet built).
- **Change:** update ratings from the gap between true margin and an expected margin given by a saturating tanh of the rating difference, with home advantage. Otherwise identical to Elo.
- **Why:**
  - [shorewala-2025](papers/shorewala-2025-movda.md): on the NBA hold-out, MOVDA Brier 0.2258 vs standard Elo 0.2274 and Glicko-2 0.2264 (Table I). No CI and no log loss.
- **Data:** have it (game margins).
- **Draft gate:** shadow on live games with the standard test. Not pre-registered.
- **Risks:** the gain over Glicko-2 is 0.0006 Brier with no test, likely within noise. Build only if cheap.

## F9. Home-favourite test in the market benchmark
- **Model:** B1 (market as a logged forecaster).
- **Change:** add the home-favourite interaction reported in [velyvis-2021](papers/velyvis-2021-euroleague-betting-thesis.md) (bachelor thesis; introduction only) to the encompassing regression: home win on logit(MKT), logit(model) and a home-favourite dummy.
- **Why:**
  - Velyvis reports home-favourite dummies significant in almost every EuroLeague model (introduction, p. 4). Results pages not read.
  - [de-angelis-2023](papers/deangelis-2023-ghost-games-euro-basketball.md): bookmakers appear to price home advantage.
- **Data:** have it for EuroLeague 2026-27 (40 games so far), too few for a power test yet.
- **Draft gate:** part of the B1 report at season end. Not a new gate.
- **Risks:** 40 games is far too few; the test is a placeholder until season end.

## F7. Negative-binomial points model for totals
- **Model:** M1 totals (CRPS).
- **Change:** model each team's points as negative binomial per scoring type (free throws, two-pointers, three-pointers), following the hierarchical approach in [attard-2023](papers/attard-2023-bayesian-hierarchical-nba.md) (NBA 2008/09).
- **Why:**
  - The paper reports negative binomial "considerably superior" to Poisson (abstract). Numbers not extracted.
  - [martingonzalez-2016](papers/martingonzalez-2016-poisson-limits-nba.md): NBA scoring is near-Poisson mid-game and over-dispersed in close-game final minutes, so dispersion matters for totals.
- **Data:** have it (box scores by shot type if the ingest holds them; otherwise points only).
- **Draft gate:** backtest totals CRPS on seasons after the fit window. Not pre-registered.
- **Risks:** M1 totals already show a significant CRPS gain, so the dispersion gain may be small. Read Attard's tables before scoring the idea.

## F8. Dummy indicators for excluded low-minute players
- **Model:** M5 roster term.
- **Change:** when a low-minute player is dropped from the design matrix, add indicators for how many were dropped on each side, instead of leaving the stint incomplete.
- **Why:**
  - [watts-2026](papers/watts-2026-dummy-rapm.md): NBA held-out RMSE 12.897 to 12.856 (about −0.3%), lower in 13 of 16 seasons (abstract page only).
  - [petridis-2026](papers/petridis-2026-lrapm.md): lineup priors help small-sample lineups (qualitative, abstract only).
- **Data:** have it if EuroLeague stints are available; check.
- **Draft gate:** no backtest on the existing M5 test split (INDEX rule: no re-tuning on used splits). Use a fresh season or a shadow. Not pre-registered.
- **Risks:** the gain is small (about 0.3% RMSE). The penalty ratio 2.2 was chosen on NBA data; re-choose it on earlier seasons only.

## G0. Guard: no streak or "form" features without a bias-corrected test
- **Model:** any model that adds recent form, momentum or hot-hand terms.
- **Change:** none now. A future form feature must be tested against a permutation null that keeps the streak structure.
- **Why:** [miller-2018](papers/miller-2018-hot-hand-streak-bias.md) shows the standard streak statistic is biased (abstract only). [carta-2026](papers/carta-2026-euroleague-timeouts.md) (press summary only) also points to no momentum effect from timeouts.
- **Data:** not needed.
- **Draft gate:** none. A rule for future ideas.
