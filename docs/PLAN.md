# EuroHoops Analytics — Project Plan
*Greek Basket League (GBL) + EuroLeague analytics & prediction platform*

*Target roles: ML Engineer + Sports Analyst*

---

## 0. Pitch

An end-to-end, production-style ML system that ingests official EuroLeague and Greek Basket League data automatically, builds **player-level models** (shot quality, regularized adjusted plus-minus, cross-league translation, projections), composes them into **calibrated game and season forecasts**, and proves them with a **public, timestamped, out-of-sample prediction log for the full 2026-27 season** — served through an API and a clean website, with a written methodology that reports failures as honestly as wins.

The differentiators, in priority order:
1. **Live predictions** for a whole season, logged before each tip-off.
2. **Player modelling depth** (xPTS + RAPM + league translation), not just a team classifier.
3. **Leak-free evaluation** with proper scoring rules, calibration, baselines and significance tests.
4. **Real engineering**: scheduled pipelines, data contracts, tests, experiment tracking, deployed API.

---

## 1. Data inventory

### 1.1 EuroLeague — official public API (no key)  ⭐ primary modelling dataset
| Endpoint | Content | Coverage |
|---|---|---|
| `live.euroleague.net/api/PlaybyPlay?gamecode=N&seasoncode=E{YYYY}` | Full PBP incl. **substitutions (`IN`/`OUT`)**, shots, fouls, TOs, rebounds, assists, timeouts, game clock, running score | 2007-08 → today (2000–2006 return empty) |
| `live.euroleague.net/api/Points?...` | Every shot with **`COORD_X`/`COORD_Y`**, `ZONE`, `FASTBREAK`, `SECOND_CHANCE`, `POINTS_OFF_TURNOVER`, clock, score, UTC timestamp | 2007-08 → today |
| `live.euroleague.net/api/Boxscore?...` | Player/team box scores | 2007-08 → today |
| `api-live.euroleague.net/v2/competitions/E/seasons/E{YYYY}/games` (+ `/games/{n}/stats`) | Schedule, results, rosters, player bios (height, DOB, nationality) | Swagger at `api-live.euroleague.net/swagger` |

- 2026-27: 20 teams, 38 regular-season rounds, 380 games, 24 Sep 2026 → 16 Apr 2027, then play-in/playoffs/Final Four.
- Python wrapper `euroleague-api` (PyPI) for exploration; production ingestion is our own code (retries, caching, schema).
- Competition code `U` = EuroCup (same API), optional extra data for league translation.
- The API is public but undocumented for third parties. Every raw response is cached; it can change without notice.

### 1.2 Greek Basket League — ESAKE (esake.gr), HTML
| Page | Content |
|---|---|
| `/el/action/EsakeResults?idchampionship={SEASON_ID}&idseason={PHASE}&series={ROUND}` | Fixtures/results per round → game IDs (hex, e.g. `D6867DA7`) |
| `/el/action/EsakegameView?idgame={ID}&mode=3` | **Full box score**: PTS, 2PM-A, 3PM-A, FTM-A, OREB/DREB, AST, BLK, BLK-against, fouls committed/drawn, STL, TO, minutes, PIR |
| `/el/action/EsakegameView?idgame={ID}&mode=2` | **Play-by-play**, rendered by a BasketHotel (Genius Sports) widget: game ID hex→decimal, `GAME_FULL_VIEW_WIDGET`, `show_tabs=["play_by_play"]`, served from `widgets.baskethotel.com/widget-service/show?…`, with an export option |
| `EsakeplayerView`, `EsaketeamView`, `EsakeRanking`, `EsakeStats` | Player/team pages, standings, leaders |

- Season dropdown goes back to 1992-93; season IDs are hex (2025-26 = `44B80BEB`, 2026-27 = `184645B9`). Box-score depth for old seasons is not yet verified.
- 2025-26 had a two-phase format (Α Φάση regular season, Β Φάση). The simulator encodes the format per season.
- GBL 2026-27 starts after the Super Cup (26–27 Sep).
- No robots.txt (404). Scraping throttles at ≥2 s between requests, caches raw HTML, identifies the scraper, and never re-scrapes cached pages.
- Names mix scripts inside one box score: `ΓΚAΟΥΝΤΛΟΚ AΝΤΡΙΟΥ` (Greek transliteration) next to `PETROPOULOS ANDREAS` (Latin). EuroLeague uses `SURNAME, NAME`. Entity resolution is a sub-project (§4.3).
- Unverified: whether GBL PBP includes substitutions (needed for GBL RAPM) and shot coordinates (probably not).

### 1.3 Betting odds (benchmark only)
- No verified free, clean historical EuroLeague/GBL odds source. Options: OddsPortal archives (JS-heavy, ToS grey), The Odds API historical (paid).
- Plan: a one-day spike on OddsPortal for EuroLeague closing moneyline/spread/total. If that fails, benchmark against Elo and naive baselines, and record current odds each round (a forward-only dataset).
- The Odds API lists EuroLeague (`basketball_euroleague`) but not the GBL. GBL has no market benchmark unless a manual or scraped source is found.
- Odds are a benchmark of market efficiency, not a betting product.

### 1.4 Not usable / out of scope
- Tracking data (SportVU-style) is not public for Europe, so no EPV or defensive-tracking models.
- No official pre-game injury or availability feed. BasketNews injury reports have been recorded from the owner's PC since 2026-10-07 but no model uses them yet (§5.6).

---

## 2. Research foundation

| # | Paper | What it establishes | How we use it |
|---|---|---|---|
| R1 | Kubatko, Oliver, Pelton & Rosenbaum (2007), *A Starting Point for Analyzing Basketball Statistics*, JQAS 3(3) | Possession framework; equal possessions per game; standard formulas | Possession/pace/ORtg/DRtg definitions; stint possession counting |
| R2 | Oliver (2004), *Basketball on Paper* | Four Factors (eFG%, TOV%, ORB%, FTr) | Team-analysis page + interpretable features |
| R3 | Glickman & Stern (1998), *A State-Space Model for NFL Scores*, JASA 93 | Team strengths as latent states evolving over time (Kalman) | Team rating model v2 (dynamic strengths) |
| R4 | Manner (2016), *Modeling and Forecasting the Outcomes of NBA Basketball Games*, JQAS 12(1) | Margin-based model + dynamic state-space strengths; weak evidence for heteroscedasticity; time variation shows mainly across seasons | Margin → win-prob mapping; test game-specific variance |
| R5 | FiveThirtyEight NBA Elo methodology | MOV-adjusted Elo, K-factor, home advantage, season-start mean reversion | **Baseline #1** |
| R6 | Sill (2010), *Improved NBA Adjusted +/- Using Regularization and Out-of-Sample Testing*, MIT Sloan | Ridge-regularized APM ~doubles out-of-sample accuracy; evaluate player metrics by predicting future games | RAPM and the evaluation of player metrics |
| R7 | Deshpande & Jensen (2016), *Estimating an NBA Player's Impact on His Team's Chances of Winning*, JQAS 12(2) | Bayesian regression on win-probability changes, posterior uncertainty for player rankings | Bayesian RAPM variant + uncertainty intervals on player cards |
| R8 | Watts, Pipping-Gamón & Wyner (2026), *Dummy RAPM*, arXiv:2608.19454 | Dummy indicators for excluded low-minute players reduce held-out margin RMSE (small but consistent, 13/16 seasons) | Low-minute player handling in RAPM (relevant for small GBL samples) |
| R9 | Chang et al. (2014), *Quantifying Shot Quality in the NBA*, MIT Sloan | eFG% conflates shot quality and shot-making → ESQ (expected) and EFG+ (above expected) | **xPTS model** and shot-making-over-expected metric |
| R10 | Franks, D'Amour, Cervone & Bornn (2016), *Meta-Analytics*, JQAS 12(4) | Judge metrics by stability, discrimination, independence | Separate skill from noise in over/underperformance signals |
| R11 | Efron & Morris (1975), *Data Analysis Using Stein's Estimator*, JASA 70 | Shrinkage beats raw averages for small samples | Empirical-Bayes shrinkage of shooting %, xPTS residuals |
| R12 | Vaci et al. (2019), *Large data and Bayesian modeling — aging curves of NBA players*, Behavior Research Methods 51 | Hierarchical Bayesian aging curves | Player projections (age effect) |
| R13 | Terner & Franks (2021), *Modeling Player and Team Performance in Basketball*, Annu. Rev. Stat. Appl. 8 | Survey: team strategy, player value, shot models, production curves | Reading map; cite in write-up |
| R14 | Walsh & Joshi (2024), *ML for Sports Betting: Accuracy or Calibration?*, MLWA 16 (+ 2025 corrigendum) | Selecting models by calibration beats selecting by accuracy; the corrigendum fixed feature-engineering bugs | Model selection by log-loss/calibration; unit-test the feature pipeline |
| R15 | Hubáček, Šourek & Železný (2019), *Exploiting Sports-Betting Market Using ML*, IJF 35(2) | Beating accuracy ≠ beating the market; decorrelate from bookmaker | Framing of market benchmark |
| R16 | Giasemidis (2020), *Descriptive and Predictive Analysis of EuroLeague Games and the Wisdom of Basketball Crowds*, arXiv:2002.08465 | ML on EuroLeague 2016–19: ≤67% test accuracy; crowd predictions beat the models | Realistic accuracy ceiling for EuroLeague; crowd as benchmark |
| R17 | Lampis, Ntzoufras, Vassalos & Dimitriou (2023), *Predictions of European Basketball Match Results with ML*, J. Sports Analytics | 5,214 games 2013–18 incl. GBL, EuroLeague, EuroCup, ACB | Closest prior work for GBL; compare against it |
| R18 | Ballı & Özdemir (2021), EuroLeague prediction w/ hybrid features, Chaos Solitons & Fractals | Reports 98.9% accuracy | Cautionary example: pre-game prediction cannot plausibly reach this (ceiling ≈ 67–70%); such numbers indicate features from the game being predicted |
| R19 | German Basketball Analytics, *Ranking all Major European Basketball Leagues* (Substack) | Team-rating gaps between competitions (e.g. ABA teams ≈21 pts worse in EuroLeague) | Prior for GBL↔EuroLeague translation |

**Take-aways:**
- Accuracy ceiling for pre-game EuroLeague prediction is ~67–70% (R16). Anything far above that indicates leakage. Primary metric is log loss, plus Brier and calibration (R14).
- Player metrics are judged by out-of-sample game prediction (R6) and by stability/discrimination (R10).
- Small samples dominate GBL, so shrinkage and regularization apply everywhere (R6, R8, R11).

---

## 3. Architecture

```
            ┌──────────── scheduled (GitHub Actions cron) ────────────┐
Sources     │  ingest  →  raw (immutable)  →  staging  →  marts        │
EL API ─────┤  httpx+retry   JSON/HTML cache  Parquet     DuckDB       │
ESAKE HTML ─┤                               pandera contracts          │
BasketHotel ┤                                                          │
Odds (fwd) ─┘                                                          │
            │  features (as-of, point-in-time)  →  models  →  predict  │
            │  MLflow tracking/registry           backtest   publish   │
            └──────────────────────────────────────────────────────────┘
                        │ prediction log (git, public)
                        ▼
              FastAPI (read-only)  →  Website (static, charts)
```

**Stack:**
| Concern | Choice | Why |
|---|---|---|
| Env/packaging | Python 3.12, `uv`, `ruff`, `mypy`, `pytest`, pre-commit | Standard, fast |
| Ingestion | `httpx` + `tenacity`, `selectolax` for HTML; Playwright only if BasketHotel needs it | Reliable, testable |
| Storage | Raw JSON/HTML (gzip) → Parquet → **DuckDB** | Zero-cost, fast, SQL, portable; Postgres only if the API needs it |
| Data contracts | `pandera` schemas + invariant checks (5 players on court, score reconciles with box score) | Catch silent data bugs |
| Modelling | scikit-learn, LightGBM, statsmodels, **PyMC** | Classical + Bayesian |
| Experiments | **MLflow** (tracking + model registry) | Reproducibility |
| Orchestration | GitHub Actions cron → Typer CLI (`eurohoops ingest / build / train / predict / publish`) | Free, visible, enough. Dagster is an optional later upgrade |
| Serving | **FastAPI** (Docker) on a free/low-cost host | Documented API |
| Frontend | Static site (Astro or Next.js static export) + Observable Plot / Vega-Lite charts | Polish comes last |
| Monitoring | Rolling log-loss/calibration vs baselines, data-freshness checks, CI failure alerts | Model in production |

**Repo layout**
```
EuroHoops-Analytics/
  src/eurohoops/{ingest,parse,entity,features,models,eval,sim,serve,cli}/
  src/eurohoops/sql/  # staging → marts transforms
  tests/          # unit (parsers, features), property tests (no leakage), data-contract tests
  notebooks/      # exploration only; nothing production lives here
  predictions/    # public log (CSV/JSON), committed by CI
  site/           # frontend
  docs/           # methodology, model cards, ADRs (architecture decision records)
  .github/workflows/
```

---

## 4. Data engineering

### 4.1 EuroLeague ingestion
- Backfill 2007-08 → 2025-26: schedule, box score, PBP, shots (19 seasons, roughly 190–380 games each; 2019-20 is partial). Throttled, cached, idempotent (skips existing).
- Daily job during the season: new results and upcoming fixtures.

### 4.2 GBL ingestion
- Scrape results per season/phase/round → game IDs → box scores (mode=3).
- Spike: BasketHotel `widget-service/show` for PBP. Decide direct HTTP vs Playwright network capture. Record what PBP contains (subs, clock, coordinates).
- Backfill: last 8 seasons (2018-19 →), extended only if useful.

### 4.3 Entity resolution (players & teams across EL, GBL, seasons)
- Greek→Latin transliteration (ELOT 743 plus custom rules for foreign names written in Greek, e.g. `ΓΚ`→`G`, `ΝΤ`→`D`, `ΜΠ`→`B`), and normalization (accents, order `SURNAME, NAME`).
- Candidate matching: fuzzy (Jaro-Winkler / rapidfuzz), blocked by season, team, jersey number and minutes-played consistency.
- A manual override table (CSV, version-controlled) covers the hard cases. Precision and recall are reported on a hand-labelled sample (~200 pairs).
- Team name history (sponsor names change every year: "Panathinaikos AKTOR", "ΣΚΑΪ ΠΑΝΑΘΗΝΑΪΚΟΣ AKTOR") maps to canonical club IDs.

### 4.4 Derived tables
- **Possessions** (R1 rules) and **stints** (lineup segments from `IN`/`OUT`) with points for/against and possessions per stint.
- Checks: exactly 5 on court per team at all times; stint points sum to the final score; possessions per team within ±2 per game. Games failing checks are flagged, not dropped.
- Point-in-time snapshots: every feature is computed "as of" a timestamp.

### 4.5 Data quirks to model or flag
- 2019-20 season cancelled mid-way; 2020-21 largely without fans (home advantage smaller), so the home-court parameter is set by season.
- 2021-22: Russian clubs removed mid-season (their games voided/forfeited); format changes (16 → 18 → 20 teams, play-in added in recent seasons).
- GBL phase formats differ by season.

---

## 5. Modelling

### Evaluation and promotion rules
Evaluation and promotion rules: CLAUDE.md. Experiment process: workflow.md.

### 5.1 M0 — Elo baseline
- 538-style: MOV multiplier, home advantage, season-start reversion (R5); K tuned on tuning seasons. Separate ratings per competition, optional shared rating for Greek clubs in both.
- Output: win probability plus (via a fitted linear map) expected margin. Live now.

### 5.2 M1 — Team efficiency model (possession-based)
- Adjusted ORtg/DRtg per team via ridge / Bayesian hierarchical regression on game (or stint) efficiency, with home effect and opponent adjustment; exponential time decay.
- Predict pace × efficiencies → expected points per team → margin and total.
- Predictive distribution: margin ~ Normal/Student-t, variance tested per R4; win probability = P(margin > 0).
- v2: dynamic state-space strengths (R3/R4) fit with a Kalman filter or PyMC.

### 5.3 M2 — Shot-quality model (xPTS), EuroLeague
- Target: make/miss per shot (FGA); xPTS = p(make) × value.
- Features: distance and angle from coordinates (court coordinate system and units to verify), zone, 2/3, `FASTBREAK`, `SECOND_CHANCE`, `POINTS_OFF_TURNOVER`, time remaining in period/game, score margin, home/away, season (league-wide shooting trends).
- Shooter identity is excluded: quality is not skill (R9).
- Known gap: shooting fouls on missed shots are not FGAs, so xPTS undervalues rim pressure. Free-throw generation is modelled separately (FTA per possession/shot zone), and "total shot value" = xPTS + expected FT points is reported.
- Models: logistic GAM/splines baseline → LightGBM → calibrated (isotonic on held-out). Leave-one-season-out CV.
- Outputs: team shot quality (offense and defense allowed), player shot-making = Σ(actual − xPTS) shrunk with empirical Bayes (R11), per 100 shots with intervals.
- Stability check (R10): year-to-year correlation of shot-making over expected vs raw eFG%.

### 5.4 M3 — Player impact: RAPM → Bayesian RAPM → box-score prior
1. **RAPM** (R6): design matrix of stints (+1 offense players, −1 defense players → separate O-RAPM and D-RAPM), target points per 100 possessions, possession weights, ridge λ by CV on future game margins. Multi-season with time decay. Low-minute handling via dummy indicators (R8).
2. **Bayesian RAPM** in PyMC (R7): posterior intervals, shown as uncertainty on player cards.
3. **Box-score prior ("SPM")**: regress multi-season RAPM on box-score rates (like BPM) on EuroLeague data. Used as the prior mean in RAPM (lower variance) and applied to GBL box scores, giving GBL player impact even if GBL PBP lacks subs.
4. Evaluation: out-of-sample margin prediction of next-N games using minutes-weighted player ratings vs team-only ratings vs PIR (EuroLeague's official index as a naive baseline).

### 5.5 M4 — League translation (GBL ↔ EuroLeague)
- Data: players and teams in both competitions (Olympiacos, Panathinaikos every season; players moving between GBL and EL clubs across seasons).
- Team level: competition offset estimated from Greek teams' ratings in both (R19 as prior).
- Player level: mixed model of per-100-possession rates (and SPM) with competition fixed effects and player random effects → translation factors per stat, with uncertainty.
- Validation: predict EuroLeague production of players who moved GBL→EL the following season; compare with naive "same stats" and "team-offset only".

### 5.6 M5 — Game predictor v2 (roster-aware)
- Team strength = Σ(projected minutes × player rating) + team residual (coaching/system) + home + rest/travel (days since last game, back-to-backs with EL midweek + GBL weekend).
- Availability: no injury feed used yet (BasketNews snapshots recorded since 2026-10-07, not used by any model). Two variants are reported: (a) projected roster (from recent rotations; usable live), (b) oracle roster (who actually played; upper bound, labelled as such, not used for the live log).
- Blend with M1 and Elo; pick by log loss on validation; recalibrate.
- Outputs: P(win), expected margin (spread), expected total with distribution → over/under probabilities for any line.

### 5.7 M6 — Player projections & scouting
- Rest-of-season and next-season projection: shrunk current rates + aging curve (R12, hierarchical) + translation (M4) if changing league.
- Over/under-performance board: observed vs expected on dimensions that R10 finds stable (shot-making over xPTS, 3P% vs FT%-informed prior, on/off vs RAPM). Flags "likely regression" vs "likely real".
- Similarity search: player embedding from standardized per-100 rates, xPTS profile and shot map → nearest neighbours ("plays like…").
- "Undervalued" list for GBL: high impact/translation with low minutes or age ≤ 24.

### 5.8 M7 — Season simulator
- Monte Carlo (10k+ runs) of the remaining schedule. Team strengths are sampled from their posterior in each simulation, not only game noise, so probabilities are not overconfident.
- Exact formats and tiebreakers: EuroLeague 2026-27 (top-6 playoffs, 7–10 play-in; rules to verify), GBL phases and playoffs per season.
- Outputs per team: final-position distribution, playoff/play-in/title odds, tracked over the season (chart).
- Backtest: mid-season simulations on past seasons (Brier on "made playoffs", RPS on final rank).

---

## 6. Product (website + API)

Pages (minimal first, polish last):
1. **Predictions** — next round: win probability, spread, total, confidence; after games: result and running scorecard vs baselines.
2. **Model performance** — live log loss/Brier vs Elo and baselines, reliability diagram, cumulative chart. Updated automatically.
3. **Standings projection** — simulation odds, trajectory over the season.
4. **Teams** — four factors, ratings, shot profile, schedule strength.
5. **Players / Scouting** — player card (RAPM ± interval, xPTS shot-making, shot chart, projection, comparables), over/under-performer board, GBL→EL translation.
6. **Methodology** — model cards, data sources, limitations, what failed.

API (FastAPI, read-only): `/games/upcoming`, `/predictions/{game_id}`, `/teams/{id}/ratings`, `/players/{id}`, `/simulations/latest`, `/metrics/live`. OpenAPI docs public.

---

## 7. MLOps & quality

- **Prediction logging**: a CI job writes predictions to `predictions/` and commits them before tip-off; the commit hash and timestamp show when each forecast was made. EuroLeague rounds span Tue–Fri and GBL plays weekends, so the predict job runs daily (e.g. 08:00 UTC) for that day's games, plus a round-level preview when a round opens. Every row stores `predicted_at` and `tipoff_utc`; the scorecard counts only rows with `predicted_at < tipoff_utc`.
- CI on every push: ruff, mypy, pytest (parsers with saved fixtures, feature leakage tests, contract tests).
- MLflow: every training run logs data snapshot hash, params, metrics and artifacts. Registry stage "production" is what the predictor loads.
- Retraining: ratings update after every round; heavier models (xPTS, RAPM prior) monthly.
- Monitoring: rolling 50-game log loss vs Elo; calibration drift; data freshness (fails loudly if a round is missing); scraper breakage alerts.
- Docs: model cards per model, ADRs for major decisions, README with architecture diagram and a three-command reproduction.
- Docker image for API + pipeline; one-command local run.

---

## 8. Timeline and status

Weeks start Mon 28 Sep 2026. Target load is 20–25 h/week; at 30+ h/week, weeks 3–18 compress by about 25%. EuroLeague started 24 Sep 2026; GBL starts late Sep/early Oct.

| Weeks | Phase | Deliverables |
|---|---|---|
| 0–1 | Bootstrap | Repo, CI, EL ingestion (current + 3 seasons), Elo M0, first live EL predictions by round 3–4, GBL PBP spike report |
| 2–3 | Data foundation | GBL results scraper (8 seasons) → GBL Elo live by week 3; GBL box scores, full EL backfill 2007→, DuckDB marts, pandera contracts, minimal predictions page |
| 3–5 | Evaluation harness | Walk-forward backtester, metrics, baselines, bootstrap CIs, leakage tests; Elo tuned |
| 5–7 | Team model M1 | Possession/stint tables, adjusted efficiencies, margin/total distributions; MLflow |
| 7–10 | Shot model M2 | xPTS model, calibration, player shot-making, shot charts |
| 9–12 | Player impact M3 | Stints, RAPM (+dummy), Bayesian RAPM, SPM prior, GBL transfer |
| 12–14 | Entity resolution + M4 | Cross-league player matching (P/R reported), translation factors |
| 14–16 | M5 + M7 | Roster-aware predictor (projected vs oracle), season simulator |
| 16–18 | M6 + product | Projections, scouting board, similarity; API; site polish |
| 18–20 | Write-up | Methodology page, 2–3 blog posts, README (demo video dropped by owner, 2026-10-11) |
| 20+ (→ Jun 2027) | Run the season | Weekly checks, end-of-season report: live results vs baselines, incl. EL playoffs/F4 and GBL finals |

### 8.1 Review backlog

Flagship model: **M5 for the EuroLeague, M1 for the GBL.** M5 failed its GBL check (+0.045 validation log loss vs Elo, CI excludes 0). Elo remains the published forecast until R1's promotion test is met. Gains come from new information (availability/injuries, preseason roster turnover) and the odds benchmark (§1.3), not from more tuning on the validation and test splits.

- **R1 Flagship promotion rule**: rule written into `docs/models/m5.md` and `m1.md`. Still to build: the promotion test itself (paired bootstrap at the two looks), needed by EuroLeague round 19.
- **R2 Season scorecard**: done. Per model and season to date: games, picks right, log loss, Brier, margin MAE, % of margins within 5 and 10 pts, totals MAE. Live for both competitions.
- **R3 Per-round view**: done. EuroLeague rounds, not calendar weeks.
- **R4 All-games list**: done. Filterable by round and model; shadow-model start rounds are stated.
- **R5 M7 gate v2**: passed. Rolling-origin evaluation over 2016–2025, expanding training windows, season-level bootstrap. EuroLeague standings use `simulate` (labelled gated). GBL is not gated (rules unverified). A loader bug affecting only the 2016-17 selection-season rows was found after the run; the verdict is unchanged.
- **R6 Standings labels**: done. "Top 6" (Play-in kept), median place as the main figure, 80% range muted beside it.
- **R7 Scouting thresholds**: done under rule v2. Uses `PERSIST_REAL` and `N_MIN` from EuroLeague rotation-player volume; the on/off label is dropped. No player is currently "likely real" on the 2025-26 board. Per-player shrinkage (`persist = n/(n+k)`) is in M6.
- **R8 EuroLeague titles**: done. All-time titles since 1958 (seed of pre-2007-08 titles plus titles counted from our data since 2007-08), shown next to seasons for clubs with at least one title.
- **R9 Win Shares per player**: done (added 2026-10-28; EuroLeague only; card `docs/models/win_shares.md`). Points per win follows Basketball-Reference: 0.32 × league PPG × (team pace / league pace), per season, not a fitted constant. That rule is what makes the league's WS sum to its wins: the replacement levels 0.92 and 1.08 leave 0.16 × points as marginal points, so WS sums to wins only when points per win = 0.32 × PPG. The fitted 35.5 (95% CI 33.92 to 37.11) is kept as a comparison only. Offense is Oliver's full PProd (field goals, assists, free throws, offensive rebounds, with the scoring-possession adjustment) over full possessions (scoring possessions, missed FGs and FTs, turnovers). Defense uses individual DRtg with Oliver's Stop% (fouls by the player's share of team fouls). WS = OWS + DWS, plus WS/40 (40-minute games). EuroLeague first, as a descriptive stat on player pages and Leaders; label DWS as the weakest part (box-score proxies). Optional: add WS/40 next to PIR as a baseline in M3's next-N-games test. Sources: [Basketball-Reference WS](https://www.basketball-reference.com/about/ws.html) and [ratings](https://www.basketball-reference.com/about/ratings.html); Oliver's book via [datafield.dev ch. 13](https://datafield.dev/professional-basketball-analytics/part-03/chapter-13/).

Dropped: R7 v3 (a v3 rule to name real over-performers). Reason: the board feeds no game model, its useful part is already in M6, and Scouting is hidden on the site.

Logging: each daily run logs every unplayed, confirmed game of any round whose first tip-off is within 48 h (`round_lead_hours`, default 48), so rounds are logged 24–48 h before their first game. A game with unconfirmed time is logged once confirmed, before its tip-off. The latest row before tip-off is the one scored (`predict.upcoming_games` selects games).

---

## 9. Open items

1. BasketHotel PBP: endpoint, fields, substitutions present? Coordinates?
2. EuroLeague shot coordinate system (origin, units, orientation): plot a season of shots.
3. GBL old-season box-score availability (spot-check 2018-19, 2014-15).
4. 2026-27 formats and tiebreak rules (EuroLeague play-in, GBL phases).
5. OddsPortal feasibility (one-day timebox).
6. Stint validation pass rate on a sample of 50 EL games.

---

## 10. Resume bullets

Fill with real numbers at the end:
- Built an automated ML platform forecasting EuroLeague & Greek Basket League games; live, season-long predictions achieved log loss X vs Y for Elo (Z% improvement, 95% CI [..]).
- Developed a shot-quality (xPTS) model on 19 seasons / N shots of EuroLeague data (calibrated, ECE = …) and a Bayesian RAPM player-impact model; transferred impact estimates to the GBL via a box-score prior.
- Engineered ingestion and entity resolution across bilingual (Greek/Latin) sources (precision P / recall R), with data contracts, CI, MLflow registry, and a FastAPI service.

---

## 11. Out of scope (v1)

Deep learning models, tracking-data methods, in-game live win probability (stretch goal after the season), injury prediction, betting recommendations/staking, GBL seasons before 2018-19, Greek A2 league, women's leagues.

---

## Sources
- EuroLeague API: `live.euroleague.net/api/*`, `api-live.euroleague.net` · [euroleague_api (GitHub)](https://github.com/giasemidis/euroleague_api) · [Shot charts in Python](https://g-giasemidis.medium.com/create-euroleague-shot-charts-in-python-7ba4aa574644)
- [ESAKE / GBL](https://www.esake.gr/)
- R1 [Kubatko et al. 2007](https://www.researchgate.net/publication/4985986_A_Starting_Point_for_Analyzing_Basketball_Statistics)
- R4 [Manner 2016](https://static.uni-graz.at/fileadmin/_Persoenliche_Webseite/manner_hans/Publikationen/NBA_revision2.pdf)
- R5 [FiveThirtyEight NBA Elo](https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings)
- R6 [Sill 2010](https://supermariogiacomazzo.github.io/STOR538_WEBSITE/Articles/Basketball/Basketball_Sill.pdf)
- R7 [Deshpande & Jensen 2016](https://arxiv.org/abs/1604.03186)
- R8 [Dummy RAPM 2026](https://arxiv.org/pdf/2608.19454)
- R9 [Chang et al. 2014](https://www.semanticscholar.org/paper/Quantifying-Shot-Quality-in-the-NBA-Chang-Maheswaran/2ef041e6d5b83979d37cb0526b7bcc9f63c5b59e)
- R10 [Franks et al. 2016](https://arxiv.org/abs/1609.09830)
- R13 [Terner & Franks 2021](https://arxiv.org/pdf/2007.10550)
- R14 [Walsh & Joshi 2024](https://arxiv.org/abs/2303.06021) · [corrigendum](https://www.sciencedirect.com/science/article/pii/S2666827025000106)
- R15 [Hubáček et al. 2019](http://ida.felk.cvut.cz/zelezny/pubs/ijf.2019.pdf)
- R16 [Giasemidis 2020](https://arxiv.org/abs/2002.08465)
- R17 [Lampis et al. 2023](https://journals.sagepub.com/doi/10.3233/JSA-220639)
- R18 [Ballı & Özdemir 2021](https://www.sciencedirect.com/science/article/abs/pii/S0960077921004732)
- R19 [Ranking all Major European Basketball Leagues](https://germanbasketballanalytics.substack.com/p/ranking-all-major-european-basketball)
- R3 Glickman & Stern (1998) JASA 93:25–35; R11 Efron & Morris (1975) JASA 70:311–319; R12 Vaci et al. (2019) Behav. Res. Methods 51
