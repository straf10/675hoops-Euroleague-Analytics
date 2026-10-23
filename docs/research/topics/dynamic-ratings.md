# Dynamic ratings: within-season drift and season-start reversion

Question Q1: how should team strength move within a season and between seasons?
Why it matters: M1 loses to Elo in EuroLeague rounds 1–5 (0.5947 vs 0.5784, `docs/models/m1.md`). Its rating carry of 0.25 sits on the grid minimum, which means a strong pull to the mean at every season start.

## What the papers say

**Within a season, strength barely drifts.**
- NFL: week-to-week AR coefficient 0.99 and noise SD 0.88 points ([glickman-1998](../papers/glickman-1998-nfl-state-space.md), Table 3, p.4).
- Four US leagues: γ_week 0.977–1.002. The NBA has the largest weekly noise (σ_week 0.166 on the logit scale) ([lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md), Table 4, p.18). The authors blame injuries, rest and trades for the NBA's extra weekly noise (p.18).
- EPL: per-round forgetting factor 0.985–0.988, a half-life of about 53 rounds ([ridall-2025](../papers/ridall-2025-epl-bayesian-state-space.md), Table 2, p.12).

**Between seasons, the papers disagree on how much to revert.**

| Paper | League | Share of last season's deviation kept | Implied reversion |
|---|---|---|---|
| [glickman-1998](../papers/glickman-1998-nfl-state-space.md) | NFL | β_s 0.82 (.52, 1.28) | ~18% |
| [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md) | NBA | γ_season 0.618 | 38% |
| [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md) | NFL / MLB / NHL | 0.69 / 0.618 / 0.542 | 31% / 38% / 46% |
| [ridall-2025](../papers/ridall-2025-epl-bayesian-state-space.md) | EPL | ω_b 0.999 | ~0% (variance grows instead) |

- Glickman and Lopez both find that season-to-season variance is much larger than week-to-week variance. Glickman's estimate is about 7× (reader's computation from σ_s 2.35 vs σ_w 0.88).
- Ridall keeps the mean and only widens the uncertainty at season start. Promoted teams get their own prior. This is the opposite of a pull to the mean.
- [macridemartino-2026](../papers/macridemartino-2026-dynamic-bradley-terry.md) (NBA) lets each team's season-to-season innovation size adapt. Teams with big roster changes get larger jumps (Table 1, p.11). It beat fixed-variance dynamic models on Brier (Table 4, p.17), but the margins are small (e.g. 0.423 vs 0.427).

**Kalman-type updates vs Elo: small gains at most.**
- [duffield-2023](../papers/duffield-2023-state-space-skill-rating.md): on EPL test log loss, Extended Kalman scored 0.965 vs Elo 0.973; on chess, 0.972 vs 1.001 (Table 2, p.22). There is no significance test, and on tennis the two were the same.
- [szczecinski-2021](../papers/szczecinski-2021-simplified-kalman-rating.md): vSKF ≈ Glicko. In noisy leagues (NHL) all methods are "merely better than the entropy" (p.18). Its main benefit is faster convergence early on (EPL: about 50 vs 200 days, Fig. 5, p.19).
- [tian-2024](../papers/tian-2024-spectral-dynamic-bradley-terry.md): a kernel-weighted ranker matched Elo on NBA accuracy (0.6382 vs 0.6355, Table 1, p.11), a gap well inside the noise.

## What we do now
- Elo: 25% reversion at each season start (`docs/models/elo.md`). This is close to the middle of the Lopez–Glickman range.
- M1: rating carry 0.25 as a row weight on last season's games, with a 1920-day half-life. In practice, last season's games count a quarter, and the ridge then pulls toward the league mean. The tuned value sits on the grid edge (`docs/models/m1.md` lines 85–89).
- ELOR (roster-prior Elo) passed its CV. It sets the season-start prior from roster continuity, which is the information Macrì-Demartino says drives the size of season-to-season jumps.

## Disagreements and gaps
- **How much to revert:** 0% (EPL), about 18% (NFL) and 31–46% (US leagues). No paper estimates this for European basketball. For our M1 carry, the literature points toward carrying more than a quarter of last season. This is a direction, not a value.
- **Pull to the mean vs widening uncertainty:** Ridall widens uncertainty, and Glickman and Lopez do both. M1 does neither in the Bayesian sense; it reweights rows.
- No paper tests early-season log loss against Elo directly. Lopez shows its sequential fits beat win percentage early in the season (p.22–23).
