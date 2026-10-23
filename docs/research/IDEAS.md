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
