# 6.75 Analytics

EuroLeague win forecasts, logged live before each game. Misses stay on the scorecard.

Live site: https://675hoops.com/ · "6.75" is the FIBA three-point distance in metres. The package and CLI are named `eurohoops`.

[![ci](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/ci.yml) [![daily predictions](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/daily.yml/badge.svg)](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/daily.yml)

## Live record

Data through **8 November 2026**. **98 EuroLeague games** scored in the 2026-27 season.

| Forecaster | Games | Log loss (lower is better) | Brier (lower is better) | Called right |
|---|---:|---:|---:|---:|
| **Elo** (our published model) | 98 | 0.639 | 0.225 | 60% |
| Home-win baseline (always the home side) | 98 | 0.718 | 0.262 | 52% |

Source: the figures on https://675hoops.com/ as read on 10 November 2026. The game count matches a local count of the scored rows in `predictions/euroleague_2026-27.csv` (100 games logged, 2 not scored because their forecast was not public before tip-off).

## How it works

The pipeline runs in this order:

`ingest` → `build` → `backtest` → `predict` → `score` → `publish`

- **Ingest** stores every raw EuroLeague response (and injury report) in a local cache. The cache is never fetched again.
- **Build** parses the cache, checks each table with pandera, and loads DuckDB marts. Everything downstream reads the marts.
- **Backtest** replays history offline. Its report fixes the settings the live models use.
- **Predict** writes one forecast per model for each game in rounds starting within 48 hours. It appends rows to `predictions/`.
- **Score** compares the forecasts with the results, using log loss, Brier score and calibration.
- **Publish** writes the site data. The Astro site in `web/` then deploys to Cloudflare.

![Daily pipeline: sources, raw cache, DuckDB marts, predict, append-only logs, score, site; the offline backtest feeds parameters and the promotion test picks the published model](docs/assets/readme/overview-light.svg)

The daily workflow ([`daily.yml`](.github/workflows/daily.yml)) commits `predictions/`, `reports/` and `odds/` to `main`. The git history shows when each forecast was published, so anyone can check it came before its game.

## Rigour rules

These rules apply to every model and experiment. The experiment process is in [`workflow.md`](workflow.md).

1. **Logs are append-only.** Rows in `predictions/`, `odds/` and `injuries/` are never edited or deleted.
2. **Walk-forward only.** A forecast uses only data from before its game. Settings are chosen on earlier seasons than the ones scored.
3. **Pass bar first.** Each experiment writes its pass bar in `experiments/<id>.md` and commits it before the result is computed.
4. **Only live games promote.** A backtest can start a shadow model. A shadow replaces the published Elo model only after a paired bootstrap test on live games, run at fixed checkpoints (after EuroLeague round 19, and at season end). The test uses 10,000 resamples and a 97.5% interval. The shadow must have an interval upper bound below 0 and a mean log-loss gap of at most −0.01.

![Promotion flow: write the pass bar, walk-forward backtest, live shadow log, checkpoint, paired bootstrap; promoted only if the CI upper bound is below 0 and the mean gap is at most -0.01](docs/assets/readme/promotion-light.svg)

Log loss is the score used for every decision. It is a proper scoring rule, so the best long-run score comes from stating your true belief. A 0.65 call costs 0.431 if the home team wins and 1.050 if it loses. Always saying 0.5 costs 0.693.

## Models

| Name | What it is | Status |
|---|---|---|
| **Elo** | Margin-adjusted Elo rating, after FiveThirtyEight's NBA method. One rating per team, with a home-court advantage. | Published. The reference that every other model is compared with. ([card](docs/models/elo.md)) |
| **M1** | Team efficiency model. It rates offence, defence and pace from box-score possessions. | Live shadow. ([card](docs/models/m1.md)) |
| **M5** | Roster-aware model. It uses the players expected to play, with their player ratings from M3. | Live shadow. ([card](docs/models/m5.md)) |
| **M5-INJ** | M5 with players marked "Out" in the injury report set to zero minutes. Nothing is re-tuned. | Live shadow. ([card](docs/models/m5_inj.md)) |
| **ELOH** | Elo with a per-team home-court advantage, shrunk toward zero. | Live shadow. ([card](docs/models/eloh.md)) |
| **SIM** (M7) | Season simulator. It plays out the rest of the season 10,000 times and gives playoff and title chances. | Published on the Standings page. ([card](docs/models/m7.md)) |
| **MKT** | Bookmaker prices, with the margin removed, used as a benchmark. It is not a forecast we publish. | Benchmark. ([card](docs/models/mkt.md)) |

Retired on 3 November 2026 by owner decision: **POOL**, **POOL3** and **ELOR**. Their logged rows stay in `predictions/`, and they no longer run.

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run eurohoops ingest      # EuroLeague history to the live season (past seasons: raw cache only)
uv run eurohoops build       # DuckDB marts
uv run eurohoops predict     # live forecasts, appended to predictions/
uv run eurohoops score       # scorecards
uv run eurohoops publish     # site data for web/
```

- An empty cache fails. The full history needs the raw archive used by [`seed-el-history.yml`](.github/workflows/seed-el-history.yml).
- `eurohoops possessions` and `eurohoops continuity` run locally only.

## Tests and quality

CI ([`ci.yml`](.github/workflows/ci.yml)) runs these checks on every push:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest -q -n auto --dist loadfile --cov=eurohoops --cov-fail-under=85
uv run vulture src scripts/vulture_whitelist.py --min-confidence 60
```

TESTCOUNT_PLACEHOLDER tests run in CI.

## Repository layout

- `src/eurohoops/` the pipeline
- `web/` the site
- `tests/` the tests
- `scripts/` one-off and check scripts
- `docs/` the plan ([`docs/PLAN.md`](docs/PLAN.md)), the product brief ([`docs/PRODUCT.md`](docs/PRODUCT.md)), model cards ([`docs/models/`](docs/models/))
- `predictions/`, `odds/`, `injuries/` the append-only logs
- `reports/` backtests and scorecards

## Data terms and license

- **EuroLeague statistics** belong to Euroleague Basketball. They are shared for non-commercial analysis and are not covered by our licence.
- **Our outputs** (forecast logs, scorecards, model outputs) are CC BY 4.0, attributed as "6.75 Analytics (https://675hoops.com)". See [`LICENSE-DATA`](LICENSE-DATA).
- **Code:** all rights reserved. See [`LICENSE`](LICENSE). The code is public for reference and is not licensed for reuse.
