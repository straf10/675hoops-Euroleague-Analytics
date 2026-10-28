# Win Shares per player (R9)

Status: built for EuroLeague only. It is a descriptive stat on the Players page, player pages and Leaders. It feeds no forecast, and the greatest caveat is the scale (see Results).

## What it is
Code: `src/eurohoops/stats/win_shares.py` (formulas and the points-per-win fit), `scripts/fit_points_per_win.py` (re-derives the constant from the cached schedules), `tests/test_win_shares.py` (a hand-computed two-team example). The export runs through `stats/export.py` and `api/readmodel.py`.

Dean Oliver's method (*Basketball on Paper*, 2004), as Basketball-Reference publishes it. The reference is datafield.dev, *Professional Basketball Analytics*, part 3 chapter 13. The chapter's formulas disagree in places (two versions each of the forced-miss weight, the individual stops and the marginal defense). The code follows its section 13.12 derivation, the one with the full defensive stop model.

**Offense (OWS).** Points produced = PProd_FG + PProd_AST + PProd_ORB.
- PProd_FG: 2 × unassisted 2-pointers + 3 × unassisted 3-pointers, plus half the points of his assisted makes. The assist links from the play-by-play split the assisted makes into 2s and 3s.
- PProd_AST = AST × league points per assisted FG × 0.5.
- PProd_ORB = ORB × team points per possession × 1.2.
- Possessions used = FGA + 0.44 × FTA + TOV − ORB.
- Marginal offense = PProd − 0.92 × league PPP × possessions used. OWS = marginal offense / points per win.

**Defense (DWS).** Per team-season, from the opponents' totals: DFG%, DOR% and the forced-miss weight FMwt. Individual stops = STL + BLK × FMwt × (1 − 1.07 DOR%) + DRB × (1 − FMwt), plus his minutes' share of the team's remaining stops, and his fouls' share of the team's foul stops. Stop% and DRtg follow Oliver's definitions (DRtg = team DRtg + 0.2 × (100 × D points per scoring possession × (1 − Stop%) − team DRtg)). Marginal defense = MIN / team MIN × team possessions × (1.08 × league PPP − DRtg / 100). DWS = marginal defense / points per win.

**Totals.** WS = OWS + DWS. WS/40 = WS / minutes × 40, since EuroLeague games are 40 minutes. A season total sums each club's box scores (the games the Players page uses). A player who moved clubs gets the sum of his clubs.

**Points per win: 35.50** (95% bootstrap CI 33.92 to 37.11), fitted on the EuroLeague regular seasons 2007-08 to 2025-26 (392 team-seasons). Win % = 0.5001 + 0.02817 × point differential per game, and points per win is the inverse of the slope. The NBA's 0.32 × league PPG is not used. `scripts/fit_points_per_win.py` reproduces the value.

**Offensive rebound weight: 1.2.** The chapter gives no value and uses 1.2 in its worked example. It is not fitted or checked.

## Results
Team check, on the box scores of each season (all phases, the same games as the wins). Sum of player WS per team against the team's wins:

| Season | Teams | Correlation | MAE (wins) | Sum of WS / wins |
|---|---|---|---|---|
| 2007-08 | 24 | 0.90 | 5.4 | 102 / 231 |
| 2008-09 | 24 | 0.92 | 4.6 | 78 / 188 |
| 2009-10 | 24 | 0.96 | 4.8 | 74 / 188 |
| 2010-11 | 24 | 0.92 | 4.2 | 88 / 189 |
| 2011-12 | 24 | 0.94 | 4.3 | 85 / 188 |
| 2012-13 | 24 | 0.92 | 5.0 | 133 / 253 |
| 2013-14 | 24 | 0.93 | 4.2 | 153 / 253 |
| 2014-15 | 24 | 0.93 | 4.6 | 142 / 251 |
| 2015-16 | 24 | 0.93 | 4.7 | 137 / 250 |
| 2016-17 | 16 | 0.92 | 7.0 | 148 / 259 |
| 2017-18 | 16 | 0.82 | 7.2 | 150 / 260 |
| 2018-19 | 16 | 0.90 | 6.8 | 150 / 259 |
| 2019-20 | 18 | 0.89 | 5.8 | 148 / 252 |
| 2020-21 | 18 | 0.89 | 8.0 | 184 / 328 |
| 2021-22 | 18 | 0.90 | 6.3 | 185 / 299 |
| 2022-23 | 18 | 0.84 | 8.1 | 181 / 328 |
| 2023-24 | 18 | 0.90 | 6.5 | 214 / 331 |
| 2024-25 | 18 | 0.81 | 6.8 | 208 / 330 |
| 2025-26 | 20 | 0.91 | 7.2 | 257 / 402 |

Correlations are high (0.81 to 0.96), so the ranking of teams holds. The totals do not match the wins, and the mean absolute error is 4 to 8 wins. The shortfall is structural, not a bug. Per game, the sum of WS is 0.39 to 0.65 wins, not 1. The two causes are:
1. Under Oliver's identity, the total WS per game is 0.16 × (points scored by both teams per game) / points per win. That is 1 win per game only when points per win = 0.32 × league PPG per team, which is the NBA's constant. For EuroLeague's roughly 80 points per team that constant is about 25.6, and the fitted 35.5 is 1.4 times as large, so each win here is worth more points.
2. Free-throw points are not credited. The spec's offense has three components, and free throws are 17.7% of EuroLeague points in the cached box scores. Crediting them would raise the total toward the identity.

For 2025-26 the check reproduces the total exactly: 0.16 × 172 points per game × (1 − 0.177) / 35.5 = 0.64 wins per game, against 257 / 402 = 0.64 observed.

**Top five by WS, 2025-26** (season totals, all phases): Milutinov, Nikola 8.3 (WS/40 0.39); Miller-McIntyre, Codi 7.3 (0.24); Walkup, Thomas 6.4 (0.29); Satoransky, Tomas 5.2 (0.22); Oturu, Dan 5.1 (0.20).

## Files
- `src/eurohoops/stats/win_shares.py`: the formulas, `fit_points_per_win`, `win_shares`, `box_win_shares` (validated against `WIN_SHARES_SCHEMA`), `team_check`.
- `scripts/fit_points_per_win.py`: re-derives the points per win constant from the cached schedules.
- `tests/test_win_shares.py`: formula checks and the two-team hand example.
- `src/eurohoops/stats/export.py`, `src/eurohoops/api/readmodel.py`: the `win_shares` input, the `ws` object on each players row, the WS fields on each splits row.
- `web/src/lib/measures.ts` (WS, OWS, DWS, WS/40 on the Players page), `web/src/lib/player.ts` (season table), `web/src/lib/leaders.ts` (a Win shares board), `web/src/lib/glossary.ts`.
- `tests/fixtures/stats/` (regenerated), `tests/test_stats.py`, `tests/test_api_app.py`, `scripts/checks/api_export.py`.

## Limitations
- **DWS rests on box-score proxies.** The stops (steals, blocks, defensive rebounds, forced misses) are estimated from the box score. DWS is the weakest of the four figures, and the glossary says so.
- **Scale.** See Results: the total is about 0.6 wins per game, so a team's WS does not sum to its wins. Ranking by WS is still meaningful.
- **Free throws** are left out of the offense, as the spec lists it.
- **Offensive rebound weight** (1.2) is the chapter's example value, not a fitted one.
- Win Shares are season totals and do not follow the rate control of the Players page.
