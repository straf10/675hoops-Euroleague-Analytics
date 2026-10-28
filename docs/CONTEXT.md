# EuroHoops


## Forecasts and the log

**Pre-registered log**:
The public CSV of forecasts (`predictions/*.csv`). Rows are added, never edited or removed.
_Avoid_: prediction file, history

**Pre-registered row**:
A game's latest log row stamped before its tip-off, from the earliest model version that logged the game. One row per game is scored.

**Provable row**:
A row stamped before tip-off that also reached the public log before tip-off.
_Avoid_: valid row (a valid row is only stamped before tip-off)

**Late row**:
A row stamped at or after its game's tip-off. Shown on the site as "Logged late"; not scored.

**Live season**:
The season being forecast (2026-27).

**B0**:
The home-win baseline: a constant home-win rate and home margin, 0.5 and 0 at a neutral venue.

**M0 / M1 / M2**:
The models. M0 is the Elo rating (the live forecast), M1 the possession-based team efficiency model, M2 the shot-quality model (expected points per shot).

**Projected roster**:
Each player's expected share of a game's minutes, from the team's games before the round's first tip-off. The input to M5.
_Avoid_: lineup, starting five

**Oracle roster**:
The minutes players actually played in the game. An upper bound for a roster-aware model; not a forecast and not logged.

**Team residual**:
What a team's results show beyond the sum of its players' ratings (coaching, system, fit), fitted walk-forward in M5.

**Rest difference**:
Home minus away of a rest feature (days since the previous game in either competition, short rest, games in the last 7 days, previous game in the other competition).

## Games and teams

**Rated game**:
A played game that is not a forfeit. Only rated games update ratings or are scored.

**Forfeit**:
A game awarded 20-0 by decision. It counts as played but carries no rating information.

**Source code**:
The team code the data source uses (EuroLeague API `ULK`). Every table, log and report uses it.
_Avoid_: team id

**Display code**:
The real-life abbreviation the site shows in place of a source code (`FBT`, `PAO`).

## Players across leagues

**Person id**:
Source ids remain the keys of every other table.
_Avoid_: player id (that is a source id)

**Dual season**:
A season a player played at least 300 minutes in both leagues (in practice for Panathinaikos or Olympiacos).

**Mover**:
A player with at least 300 minutes in one league in a season, under 100 in the other, and at least 300 in the other the next season.

**Silver pair**:
Used as matcher tuning data, not as a label.

**Confirmed time**:
A tip-off time the source has published.

## Season simulation (M7)

**Checkpoint**:
A point in a past season where the backtest stops time: after 25%, 50% or 75% of the regular-season rounds, at the next round's first tip-off. A checkpoint forecast uses only games before it.

**Strength posterior**:
M1's team ratings read as a Gaussian at a cutoff: the ridge solution as mean, σ²·(G + P)⁻¹ as covariance. Each simulation draws one strength vector from it and keeps it for the whole season.
_Avoid_: rating (the point value M1 forecasts with)

**Cut line**:
The regular-season places that decide a team's path: the direct playoffs (top 8 through 2022-23, top 6 after), the play-in (7–10) and the top 10.

**Simulation log**:
The per-team record of the live season simulation (`predictions/{competition}_sim_2026-27.csv`), one set of rows per completed round. Written only for a simulation that passed M7's backtest.

## Player projections and scouting (M6)

**Projection**:
A player's expected per-100-possession rates, shooting percentages and (EuroLeague) impact for the next season or the rest of the current one, each with an 80% interval. Past seasons are decayed and shrunk to the league, calibrated on tuning seasons. Minutes are not projected.
_Avoid_: prediction (a game forecast in the log)

**Aging curve**:
The expected year-over-year change of a rate at each age, from players with 500+ possessions in consecutive seasons (delta method on regressed rates, survivor corrected). Ages stay inside the pipeline; no age is published.

**Comparable**:
A past player-season nearest to a player's newest season in standardised box rates (and EuroLeague shot zones). The player's own seasons are excluded. Shown as "plays like".
_Avoid_: twin (the Shot Profile Twin, shot profile only)

**Read model**:
The one module (`api/readmodel.py`) that turns the marts, logs and committed reports into the JSON the API serves. The static site files are its responses, written in-process.
