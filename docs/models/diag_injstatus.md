# Diagnostic: played rate by BasketNews status (B3)

Status: diagnostic. Spec: `experiments/injstatus.md`. Result: 2026-11-11 (rounds 1-10).

## Results
Played rate, EuroLeague 2026-27 (`reports/diag_injstatus.json`):

| Status | Player-games (n) | Played | Rate | 95% CI |
|---|---|---|---|---|
| Out | 154 | 1 | 0.6% | 0.1% to 3.6% |
| Uncertain | 167 | 35 | 21.0% | 15.5% to 27.7% |
| Expected | 37 | 31 | 83.8% | 68.9% to 92.3% |

Below 30 player-games, n only: Doubtful 18, Game-time 18, Ready 11.

- Coverage: rounds 1-10, 100 games, 200 club sides. 92 of 200 club sides had a snapshot inside 24 hours before tip-off.
- 65 of 470 listings (14%) did not match a roster player. They are not in the rates.
- The numbers are descriptive and change no model.

## What it is
This diagnostic asks one question. When BasketNews lists a player with a status, how often does he play in his club's next game?

It changes nothing. No model, log, `predictions/`, `odds/` or `injuries/` file is changed. It never goes live.

## Rules
- **Games.** Every finished, non-forfeit EuroLeague game of the season. Each game gives two club sides.
- **Box score.** A game with no cached box score is dropped before the snapshot step. Its two sides are counted in `sides_without_box` and nowhere else.
- **Snapshot.** For each side, use the latest injury snapshot stamped strictly before the game's tip-off. Use it only if it is at most 24 hours before tip-off. If not, the side has no snapshot. It is counted in `sides_without_snapshot`, and no older snapshot is used. The recorder appends a snapshot only when the BasketNews page changed, so the stamp is the last change, not the last check. A quiet stretch of more than 24 hours leaves a side without a snapshot, the same behaviour as M5-INJ.
- **Players.** Each matched player listed for that club in the chosen snapshot gives one player-game.
- **Matching.** Same rule as M5-INJ (`docs/models/m5_inj.md`). Unmatched rows are not counted in the rates. Their count is reported.
- **Played.** A player played when his seconds in that game are more than 0. A matched player with no box-score row did not play.

## Metric
Per status: `n` (player-games), then `played`, `rate` and a 95% Wilson interval. The rate is given only when `n` is at least 30. Below that, only `n` is given.

`listed_unmatched` counts listings per club side and game, not distinct injury rows. A row listed in two snapshots, or for two games, counts once per side and game it appears in.

## Files
- Code: `src/eurohoops/eval/injstatus.py`, `scripts/diag_injstatus.py`.
- Reused: `models/availability.py` (`match_injuries`, `latest_snapshot`, `read_injuries`, `read_roster_names`), `stats/box.py` (`build_box_games`), `marts.py` (`read_games`), `logs.py` (`write_json`).
- Data read: `data/marts/eurohoops.duckdb` (games), `injuries/euroleague_2026-27.csv`, the cached people listing, the cached box scores.
- Player seconds come from `stats.box.build_box_games` (the cached box scores), the same loader M5 uses, because no mart table holds per-player minutes. Games come from the games mart.
- The script stops with an error if a snapshot lists one player twice for one club (checked 2026-11-11: 0 of 3,628 rows, so none has been seen).
- Output: `reports/diag_injstatus.json`.
- Tests: `tests/test_injstatus.py`.
