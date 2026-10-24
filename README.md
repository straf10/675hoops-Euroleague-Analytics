# 6.75 Analytics

**EuroLeague and Greek Basket League (GBL) win forecasts for 2026-27, logged before tip-off and scored afterwards.** Every morning at 07:47 UTC a GitHub Actions job fetches new data, asks eight models who will win the next games, commits their forecasts to a public log, and scores every finished game. Misses stay on the scorecard.

Live site: https://675hoops.com/ (EuroLeague). "6.75" is the FIBA three-point distance in metres; the package and CLI are named `eurohoops`.

[![ci](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/ci.yml) [![daily predictions](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/daily.yml/badge.svg)](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/daily.yml)

**Contents:** [How it works](#how-it-works) · [1 Ingest and build](#1-ingest-and-build) · [2 Models](#2-models) · [3 Model maths](#3-model-maths) · [4 Backtesting](#4-backtesting) · [5 Logging](#5-logging) · [6 Scoring](#6-scoring) · [7 Promotion](#7-promotion) · [8 Publishing](#8-publishing) · [Quick start](#quick-start)

## How it works

`ingest` → `build` → `backtest` → `predict` → `score` → `publish`, each run as `uv run eurohoops <cmd>`. The backtest runs offline when a model changes; its report fixes the parameters the daily run uses.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/overview-dark.svg">
  <img alt="Daily pipeline: sources, raw cache, DuckDB marts, predict, append-only logs, score, site; the offline backtest feeds parameters and the promotion test picks the published model" src="docs/assets/readme/overview-light.svg" width="100%">
</picture>

The daily workflow ([`daily.yml`](.github/workflows/daily.yml)) commits `predictions/`, `reports/` and `odds/` to `main`. That commit proves each forecast existed before its game.

## 1. Ingest and build

- **Ingest** stores every raw response gzip-compressed under `data/raw/` and never fetches it again. Only the live season's schedule refreshes. esake.gr gets at most one request per 2 s.
- **Build** parses the cache, validates each table with pandera, and loads the DuckDB marts. Everything downstream reads the marts. Team codes stay the source's (`ULK`, `PAN`); display names appear only on the site.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/ingest-dark.svg">
  <img alt="Five sources (EuroLeague API, esake.gr, EuroLeague people, The Odds API, BasketNews) go into an immutable raw cache, then parse and validate into DuckDB marts; odds and injury snapshots go to append-only logs" src="docs/assets/readme/ingest-light.svg" width="100%">
</picture>

| Source | What | Notes |
|---|---|---|
| EuroLeague API | schedules, box scores, play-by-play, shots, rosters from 2007-08 | undocumented, so everything is cached |
| esake.gr | GBL results, box scores, play-by-play from 2018-19 | box scores before 2020-21 are less reliable |
| The Odds API | EuroLeague bookmaker prices | recorded forward from 2026-09-25; a benchmark, not a betting product |
| BasketNews | EuroLeague injury report snapshots | recorded several times a day ([`scripts/record_injuries.ps1`](scripts/record_injuries.ps1)) |

**Possessions**, the unit behind M1, M3 and M5:

```
poss = FGA − OREB + TOV + 0.42 · FTA        pace = poss × 40 / minutes
```

Not every free throw ends a possession; 0.42 is the weight that matches a play-by-play possession count on average. A **stint** is a stretch with the same ten players on the floor (EuroLeague, 2011 onward); stints feed M3. The `player_xwalk` mart links one person across both leagues ([`docs/data/entity.md`](docs/data/entity.md)).

## 2. Models

Elo is the published forecast. Every other game model is a **shadow**: it logs its own forecast for every game, is scored on the same games, and replaces Elo only by beating it on live games at a fixed checkpoint ([section 7](#7-promotion)).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/models-dark.svg">
  <img alt="Model dependency map: Elo is published; ELOR builds on Elo and M3; M5 builds on M3 and M1; M7 simulates seasons from M1; M5-INJ adjusts M5 for injuries; POOL averages four logs; B0 is the baseline" src="docs/assets/readme/models-light.svg" width="100%">
</picture>

EuroLeague numbers unless marked; log loss is lower-is-better.

| Model | Adds over Elo | Status | Headline result |
|---|---|---|---|
| **Elo** ([card](docs/models/elo.md)) | the reference; MOV Elo after FiveThirtyEight ([R5](#references)) | Published | Test log loss 0.6293 (2025-26, 402 games), B0 0.6557 |
| **M1** ([card](docs/models/m1.md)) | offence, defence, pace; totals | Shadow, EL and GBL | Test 0.6232 vs re-tuned Elo 0.6246, not significant |
| **M2** ([card](docs/models/m2.md)) | shot quality (xPTS) | Research | Validation 0.6333 vs 0.6353; missed its calibration target |
| **M3** ([card](docs/models/m3.md)) | player impact (RAPM + box-score prior) | Player ratings; feeds M5, ELOR | Test RMSE 11.68, level with box-score-only |
| **M4** ([card](docs/models/m4.md)) | GBL ↔ EuroLeague translation | Not live | Failed: −0.14, CI [−0.43, +0.02] |
| **M5** ([card](docs/models/m5.md)) | who is expected to play | Shadow, EL flagship candidate | Validation 0.5838 vs M1 0.5877; test tie with M1 |
| **M5-INJ** ([card](docs/models/m5_inj.md)) | injury reports | Shadow since 2026-10-23 | Live only |
| **ELOR** ([card](docs/models/elo_roster_prior.md)) | summer roster changes | Shadow | Folds 2015–23: −0.0023 vs Elo, CI [−0.0043, −0.0007] |
| **POOL** ([card](docs/models/pool.md)) | average of Elo, M1, M5, ELOR | Shadow | Live only |
| **M6** ([card](docs/models/m6.md)) | player projections and comparables | Live | Test loss 5.90 vs Marcel 6.06, CI excludes 0 |
| **M7** ([card](docs/models/m7.md)) | season simulation | Published standings | Brier 0.1117 vs 0.1828 for current standings |

No model beats Elo on win probability in backtests yet (M5 − Elo on test: −0.0014, CI [−0.0114, 0.0088]). M5's totals gain is clear: CRPS −0.914, CI [−1.220, −0.577]. A test checks every number on the cards against the committed reports.

## 3. Model maths

Every game model outputs `p_home` (probability the home team wins) and `exp_margin` (expected home-minus-away points).

### Elo

One rating per team, starting at 1500. The rating gap plus home court becomes a probability; after the game both ratings move by the same amount, more for surprises and bigger margins.

```
d      = R_home − R_away + hca                hca = 90 (EL), 130 (GBL)
p_home = 1 / (1 + 10^(−d/400))
M      = (|margin| + 3)^0.8 / (7.5 + 0.006 · w)   w = winner's rating edge
Δ      = K · M · (result − p_home)            K = 20 (EL), 40 (GBL)
R_home += Δ,  R_away −= Δ;  each summer R ← R − 0.25 · (R − 1500)
```

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/elo-curve-dark.svg">
  <img alt="Elo win probability against the rating gap; equal teams give the home side 0.627 from the 90-point home-court advantage" src="docs/assets/readme/elo-curve-light.svg" width="460">
</picture>

### M1 · team efficiency

A weighted ridge regression rates offence, defence and pace from every earlier game. Old games count less, and each season pulls ratings toward the league mean.

```
100 · points / poss = μ + h·home + off[team] − def[opponent]     (ridge, time-decayed)
ORtg_H = μ + h + off[H] − def[A]        ORtg_A = μ − h + off[A] − def[H]
margin = pace · (ORtg_H − ORtg_A) / 100
p_home = P(margin + s·ε > 0),  ε ~ Student-t (df 7 EL, 20 GBL)
```

### M3 · player impact

Adjusted plus-minus per 100 possessions, controlling for the other nine players, shrunk toward a box-score estimate (SPM) rather than zero.

```
100 · pts / poss = c + h·home + Σ O[offence five] − Σ D[defence five]
minimise Σ w·error² + λ‖β − β_SPM‖²,   λ = 4000;   player value = O − D
```

### M5 · roster-aware

Team strength from the players expected to play (minute shares from the last five games), plus a team residual for coaching and system.

```
player_part = (poss/100) · [Σ_home share·(O − D) − Σ_away share·(O − D)]
margin      = player_part + h + r_home − r_away
```

**M5-INJ** is M5 with every player listed **Out** in the latest BasketNews snapshot set to zero minutes, teammates scaled up to fill them. Nothing is re-tuned.

### ELOR · Elo with a roster prior

Elo plus a preseason roster rating `P_t` (M3 ratings × projected minutes), faded out over the season.

```
w(r) = 0.5 · max(0, 1 − (r − 1)/24)        B_t = R_t + w(r) · (P_t − R_t,start)
```

### POOL

The average of four logged forecasts in log-odds space, with nothing to tune:

```
p_pool = sigmoid(mean of logit(p_elo), logit(p_m1), logit(p_m5), logit(p_elor))
```

### M7 · season simulator

Plays the rest of the season 10,000 times. Each run draws team strengths from M1's posterior, `θ ~ N(θ̂, σ²(G + P)⁻¹)`, keeps them all season, and applies the official tie-breaks, play-in and playoffs.

## 4. Backtesting

A backtest replays history as if live: each forecast uses only games before its round, and parameters are chosen on seasons earlier than the ones scored.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/splits-dark.svg">
  <img alt="Season splits per model: warm-up, tuning, validation, test and the live 2026-27 season" src="docs/assets/readme/splits-light.svg" width="100%">
</picture>

**Warm-up** builds ratings, **tuning** picks parameters by log loss, **validation** checks the choice, **test** (2024-25, 2025-26) is scored once. Each experiment's pass bar is committed in `experiments/<id>.md` before its result is computed. M1 v2 and M7 gate v2 reused seen seasons, so they are not clean hold-outs.

## 5. Logging

Each run forecasts every game in rounds starting within 48 hours and appends one row per model: `game_id, home, away, tipoff_utc, p_home, exp_margin, model, model_version, predicted_at_utc`. Rows are never edited. The scored row is the **latest one stamped and pushed before tip-off**; later rows are shown as "Logged late" and not scored.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/timeline-dark.svg">
  <img alt="Example week: the Tuesday run logs nothing, Wednesday logs row 1 once the round is within 48 hours, Thursday logs row 2 which is scored, Friday scores the result" src="docs/assets/readme/timeline-light.svg" width="100%">
</picture>

## 6. Scoring

Log loss decides. It is a proper scoring rule: your best expected score comes from reporting what you believe.

```
LL = −mean[ y·ln(p) + (1 − y)·ln(1 − p) ]      y = 1 if the home team won
```

A 0.65 call costs 0.431 if right and 1.050 if wrong. Always saying 0.5 scores 0.693.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/logloss-dark.svg">
  <img alt="Log loss penalty for one game against the forecast, for a home win and a home loss" src="docs/assets/readme/logloss-light.svg" width="560">
</picture>

Also reported: **Brier** `mean((p − y)²)`, **ECE** (calibration over 10 bins), **margin MAE** and **CRPS** (the whole margin distribution), and accuracy (secondary). Baselines: **B0**, the long-run home-win rate; **MKT**, the de-vigged bookmaker median before tip-off, `(1/odds_h) / (1/odds_h + 1/odds_a)`. Published pre-game EuroLeague work tops out near 67% accuracy ([R16](#references)); far higher claims ([R18](#references)) usually leak the game being predicted.

**Live, 2026-10-23** (current numbers on the site):

| Forecaster | League | Games | Log loss | Accuracy |
|---|---|---:|---:|---:|
| **Elo** | EL | 65 | 0.635 | 61.5% |
| B0 | EL | 65 | 0.709 | 53.8% |
| M1 | EL | 57 | 0.643 | 61.4% |
| M5 | EL | 37 | 0.645 | 62.2% |
| ELOR | EL | 13 | 0.589 | 69.2% |
| Market (Elo on same games 0.609) | EL | 34 | 0.584 | – |
| **Elo** | GBL | 21 | 0.428 | 81.0% |
| M1 | GBL | 21 | 0.367 | 85.7% |

Shadows started on different dates, so only the paired test below compares them fairly with Elo.

## 7. Promotion

A shadow replaces Elo only by beating it on live games at a checkpoint: EuroLeague after round 19 and at season end (challenger M5), GBL after round 13 and at season end (challenger M1). `eurohoops promote-check` refuses to run early.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/promotion-dark.svg">
  <img alt="Promotion flow: write the pass bar, walk-forward backtest, live shadow log, checkpoint, paired bootstrap; promoted only if the CI upper bound is below 0 and the mean gap is at most -0.01" src="docs/assets/readme/promotion-light.svg" width="100%">
</picture>

```
d_i     = LL_shadow(i) − LL_elo(i)        on the games both logs share
CI      = 97.5% interval of the mean over 10,000 paired resamples (seed 20261009)
promote ⇔ CI upper < 0  and  mean(d) ≤ −0.01
```

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/bootstrap-dark.svg">
  <img alt="Illustration of two bootstrap distributions of the mean gap: one wholly below zero with mean under -0.01 passes, one centred near zero fails" src="docs/assets/readme/bootstrap-light.svg" width="560">
</picture>

97.5% because two looks split the 5% error budget; −0.01 because a shadow must be clearly better, not just detectably better. Pairing cancels out a hard week that hurts both models.

## 8. Publishing

`api/readmodel.py` turns marts, logs and reports into JSON; `publish` writes `web/src/data/site.json`, and the Astro site in `web/` deploys to Cloudflare. Because the logs live in public git history, anyone can verify every forecast predates its game and recompute every score.

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). The site needs Node 24.

```bash
uv sync
uv run eurohoops ingest                      # EuroLeague 2007-08 to the live season (past seasons: raw cache only)
uv run eurohoops ingest --details            # also box scores, play-by-play and shots (slower)
uv run eurohoops build                       # DuckDB marts
uv run eurohoops predict                     # live forecasts, appended to predictions/
uv run eurohoops score                       # scorecards
uv run eurohoops publish                     # site data for web/

cd web && npm ci && npm run dev              # http://localhost:4321/
```

- An empty cache fails. The full history needs the raw archive used by [`seed-el-history.yml`](.github/workflows/seed-el-history.yml) (release `data-el-raw-2007-2022`).
- `ingest --current-only` stages only the live season; M5 needs a full `ingest`.
- GBL uses the same commands with `--competition gbl`. Backtests run per model, e.g. `uv run eurohoops backtest --model m1`.

## Tests and quality

CI ([`ci.yml`](.github/workflows/ci.yml)) runs on every push:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest -q -n auto --dist loadfile --cov=eurohoops --cov-fail-under=85
uv run vulture src scripts/vulture_whitelist.py --min-confidence 60
```

About 1,950 tests at 92% line coverage. Fixed seeds and paired bootstrap intervals make every comparison reproducible.

## Repository layout

`src/eurohoops/` pipeline · `web/` site · `tests/` · `scripts/` · `docs/` ([plan](docs/PLAN.md), [product](docs/PRODUCT.md), [model cards](docs/models/)) · `predictions/` and `odds/` logs · `reports/` backtests and scorecards. Rules are in [`CLAUDE.md`](CLAUDE.md); the experiment process in [`workflow.md`](workflow.md).

## References

Full list in [`docs/PLAN.md`](docs/PLAN.md#sources). Cited above:

- **R5** FiveThirtyEight, *NBA Elo methodology*. [link](https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings)
- **R16** Giasemidis (2020), *Descriptive and Predictive Analysis of EuroLeague Games and the Wisdom of Basketball Crowds*. [link](https://arxiv.org/abs/2002.08465)
- **R18** Ballı & Özdemir (2021), EuroLeague prediction with hybrid features, *Chaos, Solitons & Fractals*. [link](https://www.sciencedirect.com/science/article/abs/pii/S0960077921004732)

## Data terms and license

- **EuroLeague statistics** remain the property of Euroleague Basketball, shared for non-commercial analysis and not covered by our licence (this includes the [Downloads page](https://675hoops.com/downloads/) files).
- **Our outputs** (forecast logs, scorecards, published model outputs) are CC BY 4.0, attributed as "6.75 Analytics (https://675hoops.com)"; see [`LICENSE-DATA`](LICENSE-DATA).
- **Code:** all rights reserved; see [`LICENSE`](LICENSE). Public for portfolio and reference, not licensed for reuse.
