# 6.75 Analytics

EuroLeague forecasts built from team ratings, player impact and 10,000 simulated seasons.

Live site: https://675hoops.com/ · "6.75" is the FIBA three-point distance in metres. The package and CLI are named `eurohoops`.

[![ci](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/ci.yml) [![daily predictions](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/daily.yml/badge.svg)](https://github.com/straf10/675hoops-Euroleague-Analytics/actions/workflows/daily.yml)

![Animated chart in three steps. First, a surface of Elo log loss over K and home-court edge builds up, then the view turns top-down into a contour map and marks the chosen setting, K 20 and home edge 90. Second, the real forecast errors of 732 test games are drawn over the spread that the model M1 expects: 11.7 points real, 12.3 points modelled. Third, 10,000 simulated games between Besiktas and Olympiacos fan out from tip-off. The model gives Olympiacos a 67% chance. The real result, Olympiacos by 8 points, lands inside the 10th to 90th percentile range.](docs/assets/readme/hero.gif)

## Live record

![Chart and totals for EuroLeague 2026-27, 118 games scored through 18 November 2026. A line chart shows log loss over the last 50 games: Elo stays well below the home-win baseline. Season totals: Elo has log loss 0.629, Brier score 0.220 and 61% called right. Always picking the home side has 0.707, 0.256 and 54%.](docs/assets/readme/record.png)

A snapshot of [`reports/live_scorecard.json`](reports/live_scorecard.json), which the daily run rebuilds. Current numbers are on https://675hoops.com/.

## Season simulator (M7)

![Animated fan chart of 10,000 simulated seasons for Olympiacos. A white line shows the real wins up to round 10. An orange density fan spreads to round 38 with median, 10th and 90th percentile lines, beside a histogram of final wins. Expected wins are 26.4, the chance of a top-6 finish is 85% and the chance of the title is 20.5%. A second view ranks the title odds of eight teams, with Olympiacos first.](docs/assets/readme/season.gif)

Each simulation draws every team's strength from its rating posterior, then plays every remaining game with Student-t noise. The odds are counts over the 10,000 seasons. The picture uses the local data of 11 November 2026 (after round 10).

## Player ratings (M3)

![Animated chart of EuroLeague 2025-26 player ratings. 335 players appear as dots on a map of offence against defence, and the six best are named. Then a range chart shows the ten best players with 500 or more minutes and the 90% range of each rating: wide ranges that overlap.](docs/assets/readme/players.gif)

M3 rates each player in points per 100 possessions. It adjusts for the nine other players and for home court, and it pulls each rating toward a box-score estimate. M5 uses these ratings to forecast games.

## How it works

![Animated diagram of the six daily steps. Ingest: 21,761 EuroLeague responses fill a local cache. Build: games, shots and lineup stints pass schema checks and load into DuckDB marts. Backtest: seasons 2007 to 2025 are replayed in order, as warm-up, tuning, check and test, and the best settings are fixed before the live season. Predict: five models forecast each upcoming game. Score: log loss and Brier score compare Elo with the home-win baseline. Publish: the site data is rebuilt and the Astro site goes live on Cloudflare. A Cloudflare Worker starts the run every day at 05:17 UTC.](docs/assets/readme/pipeline.gif)

The daily run is [`daily.yml`](.github/workflows/daily.yml). The experiment process is in [`workflow.md`](workflow.md).

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

1,816 tests run in CI (checked 2026-11-10).

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
