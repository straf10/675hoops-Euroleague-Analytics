# Diagnostic: played rate by BasketNews status (B3)

Status: diagnostic. Spec: `experiments/injstatus.md`. Results: none yet.

## What it is
This diagnostic asks one question. When BasketNews lists a player with a status, how often does he play in his club's next game?

It changes nothing. No model, log, `predictions/`, `odds/` or `injuries/` file is changed. It never goes live.

## Rules
- **Games.** Every finished, non-forfeit EuroLeague game of the season. Each game gives two club sides.
- **Snapshot.** For each side, use the latest injury snapshot stamped strictly before the game's tip-off. Use it only if it is at most 24 hours before tip-off. If not, the side has no snapshot. It is counted in `sides_without_snapshot`, and no older snapshot is used.
- **Players.** Each matched player listed for that club in the chosen snapshot gives one player-game.
- **Matching.** Same rule as M5-INJ (`docs/models/m5_inj.md`). Unmatched rows are not counted in the rates. Their count is reported.
- **Played.** A player played when his seconds in that game are more than 0. A matched player with no box-score row did not play.

## Metric
Per status: `n` (player-games), then `played`, `rate` and a 95% Wilson interval. The rate is given only when `n` is at least 30. Below that, only `n` is given.

## Files
- Code: `src/eurohoops/eval/injstatus.py`, `scripts/diag_injstatus.py`.
- Reused: `models/availability.py` (`match_injuries`, `latest_snapshot`, `read_injuries`, `read_roster_names`), `stats/box.py` (`build_box_games`), `marts.py` (`read_games`), `logs.py` (`write_json`).
- Data read: `data/marts/eurohoops.duckdb` (games), `injuries/euroleague_2026-27.csv`, the cached people listing, the cached box scores.
- Output: `reports/diag_injstatus.json`.
- Tests: `tests/test_injstatus.py`.
