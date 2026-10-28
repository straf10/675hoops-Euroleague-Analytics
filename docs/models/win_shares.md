# Win Shares per player (R9)

Status: built for EuroLeague only. It is a descriptive stat on the Players page, player pages and Leaders. It feeds no forecast.

## What it is
Code: `src/eurohoops/stats/win_shares.py` (formulas, points per win, the fit kept for comparison), `scripts/fit_points_per_win.py` (the fitted comparison constant), `tests/test_win_shares.py` (a hand-computed two-team game). The export runs through `stats/export.py` and `api/readmodel.py`.

Dean Oliver's method (*Basketball on Paper*, 2004), as Basketball-Reference publishes it. The formulas are from [ws](https://www.basketball-reference.com/about/ws.html) and [ratings](https://www.basketball-reference.com/about/ratings.html). Oliver's book and datafield.dev part 3 chapter 13 give the derivations.

**Points per win.** Basketball-Reference's rule: `0.32 × league PPG × (team pace / league pace)`, per season, where PPG and pace are per team-game. It is not a fitted number. The league's win shares sum to its wins only with this rule: the replacement levels in the formulas (0.92 and 1.08 points per possession) leave 0.16 × points scored as marginal points, and that equals wins only when points per win = 0.32 × league PPG. In 2025-26 the league PPG was 86.0, so the league value is 27.5 points per win (pace 73.8, league pace).

**Offense (OWS).** Points produced (PProd) follows Oliver's full formula, as Basketball-Reference computes it:
- Field-goal part: 2 × (FGM + 0.5 × 3PM) × (1 − 0.5 × (PTS − FTM) / (2 × FGA) × qAST). The free-throw points are added as FTM.
- Assist part: AST × the team's points per assisted make, with the team's points net of free throws.
- Offensive-rebound part: ORB × Team_ORB_Weight × Team_Play% × team points per scoring possession.
- The whole field-goal, assist and free-throw part is scaled by (1 − Team_ORB / Team_Scoring_Poss × Team_ORB_Weight × Team_Play%).
- Team_ORB_Weight = ((1 − Team_ORB%) × Team_Play%) / ((1 − Team_ORB%) × Team_Play% + Team_ORB% × (1 − Team_Play%)); Team_ORB% = Team_ORB / (Team_ORB + Opp_DRB); Team_Play% = Team_Scoring_Poss / (Team_FGA + 0.4 × Team_FTA + Team_TOV).
- qAST is the share of the player's made field goals that were assisted, from his minutes and his team's assists and makes.
- Possessions used = scoring possessions + missed field goals (1.07 × Team_ORB% adjusted) + missed free throws + turnovers.
- Marginal offense = PProd − 0.92 × league points per possession × possessions used. OWS = marginal offense / points per win.

**Defense (DWS).** Per team-season, from the opponents' totals: DFG%, DOR%, the forced-miss weight FMwt and the team's defensive rating.
- Stops1 (the player's own): STL + BLK × FMwt × (1 − 1.07 × DOR%) + DRB × (1 − FMwt).
- Stops2 (his share of the team's): (MIN / team MIN) × the team's stops from the opponents' misses, turnovers and blocks, plus (PF / team PF) × the team's foul stops.
- Stop% = (Stops × team MIN) / (team possessions × MIN). DRtg = team DRtg + 0.2 × (100 × opponents' points per scoring possession × (1 − Stop%) − team DRtg).
- Marginal defense = MIN / team MIN × team possessions × (1.08 × league points per possession − DRtg / 100). DWS = marginal defense / points per win.

**Totals.** WS = OWS + DWS. WS/40 = WS / minutes × 40, since EuroLeague games are 40 minutes. A season total sums each club's box scores, all phases (the games the Players page uses). A player who moved clubs gets the sum of his clubs.

**Comparison: the fitted constant, not used.** Fitting win % on point differential per game over EuroLeague regular seasons 2007-08 to 2025-26 (392 team-seasons) gives 35.50 points per win (95% bootstrap CI 33.92 to 37.11). It is 1.3 to 1.5 times the Basketball-Reference value for these seasons (24.1 to 27.5). With it the league's win shares sum to about 0.6 of its wins, so it breaks the identity above. `scripts/fit_points_per_win.py` reproduces it.

**Offensive rebound weight.** Not a constant: Team_ORB_Weight is computed from each team's Team_ORB% and Team_Play% (Oliver's formula), so there is no fixed 1.2.

## Results
Team check, on all played games of each season (regular season and playoffs, the same games as the wins). Sum of player WS per team against the team's wins, per season:

| Season | Teams | Correlation | MAE (wins) | Sum of WS / wins |
|---|---|---|---|---|
| 2007-08 | 24 | 0.97 | 1.8 | 234 / 231 |
| 2008-09 | 24 | 0.97 | 1.4 | 191 / 188 |
| 2009-10 | 24 | 0.96 | 1.4 | 191 / 188 |
| 2010-11 | 24 | 0.98 | 1.3 | 192 / 189 |
| 2011-12 | 24 | 0.98 | 1.4 | 191 / 188 |
| 2012-13 | 24 | 0.96 | 1.9 | 258 / 253 |
| 2013-14 | 24 | 0.97 | 1.6 | 262 / 253 |
| 2014-15 | 24 | 0.97 | 1.6 | 251 / 251 |
| 2015-16 | 24 | 0.98 | 1.4 | 251 / 250 |
| 2016-17 | 16 | 0.97 | 1.3 | 262 / 259 |
| 2017-18 | 16 | 0.93 | 1.8 | 267 / 260 |
| 2018-19 | 16 | 0.97 | 1.9 | 264 / 259 |
| 2019-20 | 18 | 0.94 | 1.4 | 255 / 252 |
| 2020-21 | 18 | 0.97 | 1.7 | 337 / 328 |
| 2021-22 | 18 | 0.97 | 1.4 | 308 / 299 |
| 2022-23 | 18 | 0.95 | 2.0 | 337 / 328 |
| 2023-24 | 18 | 0.96 | 1.6 | 339 / 331 |
| 2024-25 | 18 | 0.94 | 1.9 | 338 / 330 |
| 2025-26 | 20 | 0.97 | 1.5 | 412 / 402 |

Correlations are 0.93 to 0.98 and the league sums are 0 to 3% above the wins. The mean absolute error is 1.3 to 2.0 wins per team (4 to 8 wins before the rule change). The small excess is a residual in the defensive terms. The 2026-27 season was in progress when this was run (60 wins), so it is left out.

**Top five by WS, 2025-26** (season totals, all phases): Vezenkov, Sasha 6.7 (WS/40 0.25); Milutinov, Nikola 6.5 (0.30); Oturu, Dan 5.2 (0.21); Francisco, Sylvain 5.0 (0.17); Montero, Jean 4.7 (0.22).

## Files
- `src/eurohoops/stats/win_shares.py`: the formulas, `win_shares`, `points_per_win`, `box_win_shares` (validated against `WIN_SHARES_SCHEMA`), `team_check`, and the fitted comparison (`fit_points_per_win`).
- `scripts/fit_points_per_win.py`: re-derives the comparison constant from the cached schedules.
- `tests/test_win_shares.py`: formula checks and the two-team hand example.
- `src/eurohoops/stats/export.py`, `src/eurohoops/api/readmodel.py`: the `win_shares` input, the `ws` object on each players row, the WS fields on each splits row.
- `web/src/lib/measures.ts` (WS, OWS, DWS, WS/40 on the Players page), `web/src/lib/player.ts` (season table), `web/src/lib/leaders.ts` (a Win shares board), `web/src/lib/glossary.ts`.
- `tests/fixtures/stats/` (regenerated), `tests/test_stats.py`, `tests/test_api_app.py`, `scripts/checks/api_export.py`.

## Limitations
- **DWS rests on box-score proxies.** The stops (steals, blocks, defensive rebounds, forced misses, and the foul and turnover stops) are estimated from the box score. DWS is the weakest of the four figures, and the glossary says so.
- **Pace and possessions** are the box-score possession counts (the `poss` field), not play-by-play possessions. Pace is per team-game, from those counts.
- **Playoffs are included**, as the Players page includes them, so season totals cover more games than the regular season.
- **Win Shares are season totals** and do not follow the rate control of the Players page.
