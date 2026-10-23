# Score distributions and home advantage

Question Q6: Normal, Student-t or count models for margins and totals? Should home advantage vary by team?
Our setup: M1 uses a Student-t margin (EuroLeague df 7, GBL df 20) and a pace model for totals. There is one home effect for all teams and seasons. Elo's hca is frozen at 90 for the EuroLeague; `docs/models/diag_home_court.md` found the 2026 home-win shortfall consistent with noise.

## What the papers say

**Margins: Normal is adequate; Student-t gave no predictive gain.**
- [glickman-1998](../papers/glickman-1998-nfl-state-space.md): calls a Normal likelihood "not an unreasonable approximation" (p.2). A Student-t version "does not have a significant effect on the predictive performance" (p.9).
- [albert-2015](../papers/albert-2015-win-probability-player-evaluation.md) and [shimizu-2026](../papers/shimizu-2026-stats-x-realtime-wp.md): in-game models treat the lead as Normal / Brownian motion. Stern's model fit 493 NBA games well (p.322).

**Totals and points: Poisson works in the middle and fails in the tails.**
- [martingonzalez-2016](../papers/martingonzalez-2016-poisson-limits-nba.md), NBA:
  - Scoring events per 10 s window are close to Poisson (index of dispersion 0.98, Table 1, p.3).
  - In the last minute of close games, scoring is over-dispersed (negative binomial, p.5) because of fouls and free throws.
  - Over a whole game, per-minute dispersion is below 1 (ID 0.84). Scoring is more regular than Poisson for most of the game.
- [ridall-2025](../papers/ridall-2025-epl-bayesian-state-space.md): a bivariate negative binomial gave "slightly better" RPS than independent Poisson (p.21). That is football goals, a low-count regime.

**Home advantage: team-specific helps in the NBA, by in-sample criteria.**
- [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md): team-specific home advantage beat a constant by DIC in the NBA (−323.9, SE 40.5), NFL and NHL; MLB was unclear (Table 2, p.12). It was better for 80% of teams in posterior predictive checks (p.13). The NBA home-win probability vs an equal team is 62.0%, with Denver at 66.1% (p.20).
- [glickman-1998](../papers/glickman-1998-nfl-state-space.md): a single home advantage failed its diagnostic (tail probability .05). Team-specific home advantage had σ_h 2.28 points (p.4, p.9).
- [ridall-2025](../papers/ridall-2025-epl-bayesian-state-space.md): home advantage changes over time, with a fast within-season factor of 0.74–0.80 (Table 2, p.12), but is common to all teams.
- [szczecinski-2021](../papers/szczecinski-2021-simplified-kalman-rating.md) and [macridemartino-2026](../papers/macridemartino-2026-dynamic-bradley-terry.md): one global home parameter. Macrì-Demartino calls the evidence for team effects mixed (p.17).

## What we do now
- The Student-t margin goes slightly beyond what Glickman found necessary. Its df were tuned on used splits, so there is nothing to change.
- Totals come from the M1 pace and efficiency model. Totals CRPS gains are significant (M1, M5).
- One home effect.

## Disagreements and gaps
- **Team-specific home advantage:** Lopez and Glickman support it by DIC and posterior checks, which are in-sample. No paper shows an out-of-sample log-loss gain. Macrì-Demartino and Szczecinski stay with one value. EuroLeague travel distances differ more than within one US league, so the question is open for us.
- **Totals dispersion:** the NBA evidence suggests near-Poisson or under-dispersed scoring for most of a game, so the totals spread should come from pace and efficiency uncertainty. That is what M1 does.
