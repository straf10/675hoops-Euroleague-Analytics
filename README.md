# 6.75 Analytics (EuroHoops)

**EuroLeague game forecasts for the 2026-27 season, committed to a public log before tip-off and scored afterwards.** The pipeline ingests official EuroLeague data, builds team, shot, player and roster models, and publishes the forecasts with their scorecards. Forecasts are append-only, so a result cannot be tuned after the fact. Every model is measured against a home-team baseline and Elo, and for the EuroLeague also against bookmaker odds recorded before each game. Misses and weak weeks stay on the scorecard.

- Live site: [TODO: URL]
- Demo video (3 min): [TODO: URL]

The repository also contains a Greek Basket League (GBL) pipeline, and its forecasts are logged in `predictions/`. The public site shows EuroLeague only.

[![ci](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/ci.yml)
[![daily predictions](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/daily.yml/badge.svg)](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/daily.yml)

"6.75" is the EuroLeague and FIBA three-point distance in metres. The repository, Python package and CLI are named `eurohoops`.

## Why the numbers can be trusted

- **Pre-registered forecasts.** `predictions/*_2026-27.csv` and `odds/*.csv` are append-only. The daily GitHub Actions run commits each forecast before the game starts, and git history gives the commit time of every row. A forecast that reaches the log after tip-off is shown, flagged and not scored.
- **Gates declared before the run.** Each model card states its validation rule before its test seasons are scored. Test seasons (2024-25 and 2025-26) are scored once. Where a choice came after results were public, the card says so: M1 v2 and M7 gate v2 are labelled as not clean hold-outs.
- **A promotion rule written in advance.** Elo is the published forecast. M5 replaces it only if a rule committed in [`docs/models/m5.md`](docs/models/m5.md) is met at one of two fixed checkpoints (after EuroLeague round 19, and after the last game). The rule requires a mean log-loss gain of at least 0.01 over Elo, with the 97.5% paired-bootstrap interval below zero. Promotion is checked only at those two looks, and a promoted model is not demoted within the season. The test is implemented as `uv run eurohoops promote-check --competition euroleague --look 1|2`, which refuses to run before a look is due.
- **Proper scoring rules first.** Log loss is the primary metric. Brier score, calibration (expected calibration error and reliability diagrams), margin RMSE and MAE, totals error and CRPS for predictive distributions come next. Accuracy is reported only as a secondary figure.
- **Honest about the ceiling.** Published pre-game EuroLeague work reports at most about 67% test accuracy ([R16](#references)), and the plan treats 67–70% as the realistic limit. A reported 98.9% ([R18](#references)) is far above that. Pre-game prediction cannot plausibly reach it, so such figures usually mean features that see the game being predicted. The project keeps per-model leakage tests (for example `tests/test_m3_leakage.py`, `tests/test_m5_leakage.py`, `tests/test_m2_leakage.py`).

## Models

Status: **Published** means the forecast shown on the site. **Shadow** means logged next to Elo but not shown as the forecast. Headline numbers are EuroLeague unless marked GBL. Log loss is lower-is-better.

| Model | What it does | Status | Headline result |
|---|---|---|---|
| **Elo** | MOV-adjusted Elo after FiveThirtyEight ([R5](#references)): margin of victory, home advantage, season-start reversion | Published (EuroLeague; GBL logged) | Test log loss 0.6246 (2024-25 and 2025-26, 732 games) |
| **M1** | Possession-based team model: offense, defense and pace ratings give margin and total distributions ([card](docs/models/m1.md)) | Shadow (EuroLeague); GBL flagship candidate | Test log loss 0.6232, against Elo 0.6246; the difference is not significant. Validation gate passed. |
| **M2** | Shot-quality model (xPTS): make probability for each field-goal attempt from location and game state, never shooter identity ([card](docs/models/m2.md)) | Research; no live forecast | Validation log loss 0.6333 against 0.6353 for the spline baseline. Gate failed: chosen model misses its calibration target (ECE 0.0104 against 0.01). |
| **M3** | Player impact: regularised adjusted plus-minus shrunk toward a box-score prior, with 90% intervals for every player-season ([card](docs/models/m3.md)) | Research; feeds M5 | Validation RMSE 11.48, best of its set; test RMSE 11.68, level with the box-score-only model. Validation gate passed by a narrow margin. |
| **M4** | League translation between GBL and EuroLeague for box-score rates ([card](docs/models/m4.md)) | Reported; not live | Gate failed. Difference −0.14 against same-stats baseline, 95% CI [−0.43, +0.02], six movers only. |
| **M5** | Roster-aware game predictor: projected minutes times player ratings, team residual, home court ([card](docs/models/m5.md)) | Shadow; EuroLeague flagship candidate | Validation log loss 0.5838 against M1 0.5877 (interval includes zero). Test tie with M1: 0.6232 each. GBL check failed. |
| **M6** | Player projections with 80% intervals, over/under board and "plays like" comparables ([card](docs/models/m6.md)) | Live (2026-27 projections and board) | Test projection loss 5.90 against Marcel 6.06 (difference −0.16, CI excludes zero). Validation tie with Marcel. |
| **M7** | Season simulator: Monte Carlo of the rest of the season, team strengths drawn from M1's posterior, then playoff and title odds ([card](docs/models/m7.md)) | Published (EuroLeague; labelled gated); GBL not gated | Gate v2 passed on 372 team-checkpoints: Brier 0.1117, against 0.1828 for current standings, and not worse than the point simulator. Gate v1 failed on one validation season. |

Phase D audit ([`docs/models/audit_phase_d.md`](docs/models/audit_phase_d.md)): no model beats Elo on win probability yet, since every M1 and M5 comparison with Elo has a 95% CI that includes 0 (M5 minus Elo on test log loss: −0.001351, CI [−0.011383, 0.008787]). M5's totals gain is the clear one: CRPS against Elo on test is −0.914002, CI [−1.220227, −0.576823].

Test-season context for the EuroLeague: home-team baseline 0.6600, Elo 0.6246, M1 0.6232 and M5 0.6232 log loss ([M1 card](docs/models/m1.md), [M3 card](docs/models/m3.md)). [TODO: check that the baseline row covers the same 732 games.]

Each model card lists its code, report files and every number it quotes. A test checks the quoted numbers against the committed reports.

## Data

- **EuroLeague.** The official public API (`live.euroleague.net`, `api-live.euroleague.net`): play-by-play with substitutions, shot coordinates, box scores, schedules and rosters. Coverage runs from 2007-08 to the current season. The API is undocumented for third parties and may change, so every raw response is cached.
- **Greek Basket League.** HTML from [esake.gr](https://www.esake.gr/): results, box scores and play-by-play, which is rendered by a widget. Requests are throttled to at least 2 s apart, the scraper identifies itself, every raw page is cached, and a cached page is never fetched again. Coverage: 2018-19 to the current season (M4 uses 2018–2025; box scores before 2020-21 are less reliable).
- **Betting odds.** The Odds API for EuroLeague only. No verified free historical source exists, so odds are recorded forward in `odds/`, and the file is append-only. They serve as a market benchmark, not a betting product. Recorded from 2026-09-25 (round 1).
- **Injury reports.** A snapshot of the BasketNews EuroLeague injury report, appended on each run (`eurohoops injuries`).
- **Player identity.** A crosswalk links players across leagues and seasons, since GBL names mix Greek and Latin script (see [`docs/data/entity.md`](docs/data/entity.md)).
- **Shots.** The shot table holds about 612,000 field-goal attempts from 2007-08 to 2025-26. M2 is fitted on 2011-12 onward. Excluded rows are listed with a reason ([`docs/data/shots.md`](docs/data/shots.md)).

## Pipeline

`ingest` → `build` → `backtest` → `predict` → `score` → `publish`

| Stage | What it does | Output |
|---|---|---|
| ingest | Fetches and caches EuroLeague and ESAKE responses | Raw cache |
| build | Parses to staging tables, validates them with pandera, builds the DuckDB marts | `data/marts/eurohoops.duckdb` |
| backtest | Re-runs a model's walk-forward backtest and rewrites its report. Not part of the daily run; the committed reports are pre-registration evidence. | `reports/*.json` |
| predict | Logs the live forecasts | `predictions/*_2026-27.csv` |
| score | Scores logged forecasts against results and baselines | `reports/live_scorecard*.json` |
| publish | Exports JSON and builds the static site | `web/` (Astro), deployed to [TODO: host] |

**Daily run.** [`.github/workflows/daily.yml`](.github/workflows/daily.yml) runs at 08:00 UTC and can also be started by hand. It ingests both leagues, builds the marts, records odds and injuries, logs forecasts and simulations, scores, publishes and commits the logs back to `main`. The workflow replays its commit on top of `main` if the branch has moved.

Some commands are local only: `possessions` and `continuity`.

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

`ingest` stages EuroLeague from 2007-08 to the live season. Past seasons are read from the raw cache and are never fetched; a missing past season is an error. `ingest --current-only` stages only the live season, for fast local runs. Its staged tables lack the history, so run a plain `ingest` before `build`, or M5 cannot run.

With an empty cache, a plain `ingest` fails on the first missing past season. `ingest --current-only` works without a cache, but the full history needs the EuroLeague raw cache restored from the release archive that [`seed-el-history.yml`](.github/workflows/seed-el-history.yml) uses (`euroleague-raw-2007-2022.tar.gz`, release `data-el-raw-2007-2022`). [TODO: cold-cache instructions for a local run: the exact download and extract commands.]

GBL commands follow the same pattern with `--competition gbl`. The first GBL ingest is slow because of the request throttle. `ingest --details` is the step that caches box scores and play-by-play.

Model backtests are run per model, for example `uv run eurohoops backtest --model m1`. Re-running one rewrites the committed report, so do it deliberately.

## Tests and quality

The CI workflow ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every push:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest -q -n auto --dist loadfile --cov=eurohoops --cov-fail-under=85
uv run vulture src scripts/vulture_whitelist.py --min-confidence 60
```

- Coverage must be at least 85%. 1,424 tests, 92.6% line coverage (as of 2026-10-11).
- pandera schemas validate each staging table, and box-score invariants are checked on each build.
- Runs are reproducible: fixed seeds, and paired bootstrap confidence intervals on every model comparison.
- The scraper enforces the throttle and caches responses, as described under Data.
- The front end follows one documented design system, [`docs/DESIGN.md`](docs/DESIGN.md), and works at 390 px phone width in light and dark themes.

## Repository layout

```
src/eurohoops/     pipeline: ingest, parse, marts, models, eval, predict, odds, publish, stats
web/               Astro static site
tests/             pytest suite
scripts/           benchmarks and checks
docs/              product, design, plan, model cards, data notes, build history
predictions/       append-only pre-registered forecast logs
odds/              append-only market benchmark logs
reports/           backtests, scorecards, screenshots (pre-registration evidence)
```

- [`docs/PLAN.md`](docs/PLAN.md): roadmap, data inventory, references and review backlog.
- [`docs/PRODUCT.md`](docs/PRODUCT.md): product brief and principles.
- [`docs/models/`](docs/models/): model cards (Elo card: [TODO: link docs/models/elo.md once merged])
- [`docs/history/`](docs/history/): build record cited as pre-registration evidence.

## References

Full list with links in [`docs/PLAN.md`](docs/PLAN.md#sources). Cited above:

- **R4** Manner (2016), *Modeling and Forecasting the Outcomes of NBA Basketball Games*, JQAS 12(1). [link](https://static.uni-graz.at/fileadmin/_Persoenliche_Webseite/manner_hans/Publikationen/NBA_revision2.pdf)
- **R5** FiveThirtyEight, *NBA Elo methodology*. [link](https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings)
- **R6** Sill (2010), *Improved NBA Adjusted +/- Using Regularization and Out-of-Sample Testing*, MIT Sloan. [link](https://supermariogiacomazzo.github.io/STOR538_WEBSITE/Articles/Basketball/Basketball_Sill.pdf)
- **R7** Deshpande & Jensen (2016), *Estimating an NBA Player's Impact on His Team's Chances of Winning*, JQAS 12(2). [link](https://arxiv.org/abs/1604.03186)
- **R8** Watts, Pipping-Gamón & Wyner (2026), *Dummy RAPM*. [link](https://arxiv.org/pdf/2608.19454)
- **R9** Chang et al. (2014), *Quantifying Shot Quality in the NBA*, MIT Sloan. [link](https://www.semanticscholar.org/paper/Quantifying-Shot-Quality-in-the-NBA-Chang-Maheswaran/2ef041e6d5b83979d37cb0526b7bcc9f63c5b59e)
- **R10** Franks, D'Amour, Cervone & Bornn (2016), *Meta-Analytics*, JQAS 12(4). [link](https://arxiv.org/abs/1609.09830)
- **R14** Walsh & Joshi (2024), *Machine Learning for Sports Betting: Accuracy or Calibration?*, MLWA 16. [link](https://arxiv.org/abs/2303.06021)
- **R15** Hubáček, Šourek & Železný (2019), *Exploiting Sports-Betting Market Using Machine Learning*, IJF 35(2). [link](http://ida.felk.cvut.cz/zelezny/pubs/ijf.2019.pdf)
- **R16** Giasemidis (2020), *Descriptive and Predictive Analysis of EuroLeague Games and the Wisdom of Basketball Crowds*. [link](https://arxiv.org/abs/2002.08465)
- **R17** Lampis, Ntzoufras, Vassalos & Dimitriou (2023), *Predictions of European Basketball Match Results with Machine Learning*, J. Sports Analytics. [link](https://journals.sagepub.com/doi/10.3233/JSA-220639)
- **R18** Ballı & Özdemir (2021), EuroLeague prediction with hybrid features, *Chaos, Solitons & Fractals*. [link](https://www.sciencedirect.com/science/article/abs/pii/S0960077921004732)
- **R19** German Basketball Analytics, *Ranking all Major European Basketball Leagues*. [link](https://germanbasketballanalytics.substack.com/p/ranking-all-major-european-basketball)

Also in the plan: R1 Kubatko et al. (2007), R2 Oliver (2004), R3 Glickman & Stern (1998), R11 Efron & Morris (1975), R12 Vaci et al. (2019), R13 Terner & Franks (2021). [TODO: add links for R2, R3, R11 and R12; the plan has none.]

## License

All rights reserved; see [`LICENSE`](LICENSE). The repository is public for portfolio and reference purposes and is not licensed for reuse.
