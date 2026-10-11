# 6.75 Analytics

**EuroLeague game forecasts for the 2026-27 season, committed to a public log before tip-off and scored afterwards.** The pipeline ingests official EuroLeague data, builds team, shot, player and roster models, and publishes the forecasts with their scorecards. Forecasts are append-only, so results cannot be tuned after the fact. Every model is compared with a home-team baseline and Elo, and for EuroLeague also with bookmaker odds recorded before each game. Misses and weak weeks stay on the scorecard.

- Live site: https://675hoops.com/
- The repository also has a Greek Basket League (GBL) pipeline, logged in `predictions/`. The site shows EuroLeague only.

[![ci](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/ci.yml) [![daily predictions](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/daily.yml/badge.svg)](https://github.com/straf10/EuroHoops-Analytics/actions/workflows/daily.yml)

"6.75" is the EuroLeague and FIBA three-point distance in metres. The repository, package and CLI are named `eurohoops`.

## Why the numbers can be trusted

- **Pre-registered.** Forecast and odds logs are append-only. The daily run commits each forecast before tip-off, and git history dates every row. Late rows are shown, flagged and not scored.
- **Gates declared in advance.** Each model card states its validation rule before the test seasons (2024-25, 2025-26) are scored, once. Post-hoc choices are labelled: M1 v2 and M7 gate v2 are not clean hold-outs.
- **Promotion rule fixed in advance.** Elo is the published forecast. M5 replaces it only if the rule in [`docs/models/m5.md`](docs/models/m5.md) is met at one of two checkpoints (after EuroLeague round 19, and after the last game): a mean log-loss gain of at least 0.01 with the 97.5% paired-bootstrap interval below zero. `uv run eurohoops promote-check --competition euroleague --look 1|2` refuses to run before a look is due. A promoted model is not demoted within the season.
- **Proper scoring first.** Log loss is primary, then Brier score, calibration (ECE, reliability diagrams), margin RMSE and MAE, totals error and CRPS. Accuracy is secondary.
- **Honest about the ceiling.** Published pre-game EuroLeague work reports at most about 67% test accuracy ([R16](#references)). A reported 98.9% ([R18](#references)) is far above that and cannot plausibly be reached pre-game, so such figures usually mean features that see the game being predicted. Per-model leakage tests are kept (`tests/test_m2_leakage.py`, `tests/test_m3_leakage.py`, `tests/test_m5_leakage.py`).

## Models

**Published** means shown on the site. **Shadow** means logged next to Elo, not shown as the forecast. Headline numbers are EuroLeague unless marked GBL. Log loss is lower-is-better.

| Model | What it does | Status | Headline result |
|---|---|---|---|
| **Elo** ([card](docs/models/elo.md)) | MOV-adjusted Elo after FiveThirtyEight ([R5](#references)) | Published (EuroLeague); GBL logged | Test log loss 0.6292 (2024-25 and 2025-26, 732 games) |
| **M1** ([card](docs/models/m1.md)) | Possession-based team model: offense, defense and pace ratings | Shadow; GBL flagship candidate | Test log loss 0.6232, against re-tuned Elo 0.6246; the difference is not significant. Validation gate passed. |
| **M2** ([card](docs/models/m2.md)) | Shot quality (xPTS) from location and game state, never shooter identity | Research; no live forecast | Validation log loss 0.6333 against 0.6353 for the spline baseline. Gate failed: misses its calibration target (ECE 0.0104 against 0.01). |
| **M3** ([card](docs/models/m3.md)) | Player impact: regularised adjusted plus-minus with a box-score prior, 90% intervals | Research; feeds M5 | Validation RMSE 11.48, best of its set; test RMSE 11.68, level with box-score-only. Validation gate passed by a narrow margin. |
| **M4** ([card](docs/models/m4.md)) | League translation between GBL and EuroLeague for box-score rates | Reported; not live | Gate failed. Difference −0.14 against same-stats baseline, 95% CI [−0.43, +0.02], six movers only. |
| **M5** ([card](docs/models/m5.md)) | Roster-aware predictor: projected minutes times player ratings, home court | Shadow; EuroLeague flagship candidate | Validation log loss 0.5838 against M1 0.5877 (interval includes zero). Test tie with M1: 0.6232 each. GBL check failed. |
| **M6** ([card](docs/models/m6.md)) | Player projections with 80% intervals, over/under board, comparables | Live (2026-27 projections and board) | Test projection loss 5.90 against Marcel 6.06 (difference −0.16, CI excludes zero). Validation tie with Marcel. |
| **M7** ([card](docs/models/m7.md)) | Season simulator: Monte Carlo of the rest of the season, then playoff and title odds | Published (EuroLeague; labelled gated); GBL not gated | Gate v2 passed on 372 team-checkpoints: Brier 0.1117, against 0.1828 for current standings, and not worse than the point simulator. Gate v1 failed on one validation season. |

Phase D audit ([`docs/models/audit_phase_d.md`](docs/models/audit_phase_d.md)): no model beats Elo on win probability yet, since every M1 and M5 comparison with Elo has a 95% CI that includes 0 (M5 minus Elo on test log loss: −0.001351, CI [−0.011383, 0.008787]). M5's totals gain is the clear one: CRPS against Elo on test is −0.914002, CI [−1.220227, −0.576823].

EuroLeague test-season baseline (log loss): home team 0.6600; re-tuned Elo 0.6246 (published Elo 0.6292); M1 and M5 0.6232 each ([M1 card](docs/models/m1.md), [M3 card](docs/models/m3.md)). Each card lists its code, reports and quoted numbers, and a test checks them against the committed reports.

## Data

- **EuroLeague.** Official public API (`live.euroleague.net`, `api-live.euroleague.net`): play-by-play, shot coordinates, box scores, schedules and rosters from 2007-08. Undocumented and may change, so every raw response is cached.
- **Greek Basket League.** HTML from [esake.gr](https://www.esake.gr/): results, box scores and play-by-play. Throttled to at least 2 s between requests; raw pages are cached and never re-fetched. Coverage 2018-19 onward; box scores before 2020-21 are less reliable.
- **Betting odds.** The Odds API, EuroLeague only. No verified free historical source exists, so odds are recorded forward in `odds/` from 2026-09-25 (round 1). A market benchmark, not a betting product.
- **Injury reports.** BasketNews EuroLeague injury report, snapshotted on each run (`eurohoops injuries`).
- **Player identity.** A crosswalk links players across leagues, since GBL names mix Greek and Latin script ([`docs/data/entity.md`](docs/data/entity.md)).
- **Shots.** About 612,000 field-goal attempts, 2007-08 to 2025-26; M2 is fitted from 2011-12. Exclusions are listed with reasons ([`docs/data/shots.md`](docs/data/shots.md)).

## Pipeline

`ingest` → `build` → `backtest` → `predict` → `score` → `publish`

Outputs: raw cache; `data/marts/eurohoops.duckdb` (pandera-validated staging); `reports/*.json` from backtests; `predictions/*_2026-27.csv`; `reports/live_scorecard*.json`; `web/` (Astro), deployed daily to Cloudflare.

**Daily run.** [`daily.yml`](.github/workflows/daily.yml) runs at 08:00 UTC and can be started by hand. It ingests both leagues, builds the marts, records odds and injuries, logs forecasts and simulations, scores, publishes, and commits the logs to `main`, replaying its commit if `main` has moved. Backtests are not part of it. `possessions` and `continuity` are local only.

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

- A missing past season is an error, so an empty cache fails. The full history needs the raw cache from the release archive used by [`seed-el-history.yml`](.github/workflows/seed-el-history.yml) (`euroleague-raw-2007-2022.tar.gz`, release `data-el-raw-2007-2022`).
- `ingest --current-only` stages only the live season, for fast local runs. Run a plain `ingest` before `build`, or M5 cannot run.
- GBL uses the same commands with `--competition gbl`. Backtests run per model, e.g. `uv run eurohoops backtest --model m1`, and rewrite the committed report, so run them deliberately.

## Tests and quality

The CI workflow ([`ci.yml`](.github/workflows/ci.yml)) runs on every push:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest -q -n auto --dist loadfile --cov=eurohoops --cov-fail-under=85
uv run vulture src scripts/vulture_whitelist.py --min-confidence 60
```

- Coverage is at least 85%: 1,424 tests, 92.6% line coverage (as of 2026-10-11).
- pandera validates each staging table; box-score invariants are checked on each build.
- Runs are reproducible: fixed seeds and paired bootstrap intervals on every model comparison.
- The front end follows [`docs/DESIGN.md`](docs/DESIGN.md) and works at 390 px phone width in light and dark themes.

## Repository layout

`src/eurohoops/` is the pipeline; `web/` the Astro site; `tests/` the pytest suite; `scripts/` benchmarks and checks; `docs/` product, design, plan, model cards and build history; `predictions/` and `odds/` the append-only logs; `reports/` backtests, scorecards and screenshots. Docs: [PLAN](docs/PLAN.md) (roadmap, data inventory, references) · [PRODUCT](docs/PRODUCT.md) · [model cards](docs/models/) · [build history](docs/history/).

## References

Full list in [`docs/PLAN.md`](docs/PLAN.md#sources). Cited above:

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

Also in the plan: R1 Kubatko et al. (2007), R2 Oliver (2004), R3 Glickman & Stern (1998), R11 Efron & Morris (1975), R12 Vaci et al. (2019), R13 Terner & Franks (2021).

## License

All rights reserved; see [`LICENSE`](LICENSE). Public for portfolio and reference purposes; not licensed for reuse.

<!-- Open items: confirm the 0.6600 home-team baseline covers the same 732 games; cold-cache download and extract commands for a local run; links for R2, R3, R11 and R12 (the plan has none). -->
