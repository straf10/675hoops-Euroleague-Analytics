# Betting markets as a benchmark

Question Q3: which de-vig method should we use, closing or earlier lines, and are there biases to account for?
Our data: `odds/euroleague_2026-27.csv` holds The Odds API snapshots for 40 EuroLeague games (rounds 1–8 so far), with a median across 13–19 books, spreads and totals. Snapshots are taken hours before tip-off, not necessarily at the close. `odds.py` uses proportional de-vig.

## What the papers say

**De-vig: proportional normalisation is the standard. No paper compares methods.**
- [robbins-2022](../papers/robbins-2022-sports-betting-efficiency.md): p_i / (p_1 + p_2) (eq. 3, p.5). The NBA booksum averages 3.77% and the hold 3.64% (Table 2, p.6).
- [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md): proportional normalisation (eq. 1, p.6). Uses the line closest to the start; average vig 1.93% (p.7). With 10 bins, Hosmer–Lemeshow shows no lack of fit (p.7).
- [miller-2026](../papers/miller-2026-mma-betting-efficiency.md) cites Berkowitz et al. (2018). None of the 32 papers compares proportional, power or Shin de-vig. **This is a gap.**

**Closing lines are hard to beat; opening lines less so.**
- [dare-2015](../papers/dare-2015-player-absence-nba-lines.md): absence mispricing at the open is mostly gone by the close (Tables 2–3).
- [baryla-2007](../papers/baryla-2007-nba-early-season-totals-bias.md): closing lines predict better than opening lines (fn. 8, p.3).
- [colquitt-2001](../papers/colquitt-2001-ncaa-betting-efficiency.md): NCAA closing lines pass the rationality test (intercept 0, slope 1 not rejected, Table 3). Errors are larger in less-covered conferences: absolute error 10.42 vs 7.75 (Table 4, p.243).
- [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md): in the NBA, its model matched the market (AUC 0.756 vs 0.756; Brier 0.194 vs 0.194, Table 5, p.24).
- [ridall-2025](../papers/ridall-2025-epl-bayesian-state-space.md): every model, including the best, was worse than bookmakers' average odds in the EPL (Table 3, p.14).
- [glickman-1998](../papers/glickman-1998-nfl-state-space.md): MSE 165.0 vs 170.5 for the Vegas spread over 110 games. The authors say this is too few games to generalise (p.6).

**Known biases.**
- **Favourite–longshot:** not found in the NBA (ANOVA p = .866) or the NHL. Found in NFL bins, college sports and MLB ([robbins-2022](../papers/robbins-2022-sports-betting-efficiency.md), p.14–18). In MMA it is significant but not profitable ([miller-2026](../papers/miller-2026-mma-betting-efficiency.md), Table 3, p.10).
- **Early-season totals:** in the NBA, totals lines are too high early in the season. Unders won 61.9% at the open and 56.7% at the close after a downward line move (Table 3, p.8). The bias fades by about the 10th home game (p.7) ([baryla-2007](../papers/baryla-2007-nba-early-season-totals-bias.md)). It is relevant to M1 totals and to our totals benchmark.
- **Less-covered markets are noisier:** Colquitt's small-conference result suggests GBL lines (if we ever get them) would be a weaker benchmark than EuroLeague lines.

## What we do now
- Proportional de-vig, median across books, EuroLeague only. This matches the literature's standard.
- The odds are a benchmark only. No model uses them as an input.

## Disagreements and gaps
- Models vs market: Glickman slightly beat it (NFL, 1993), Lopez tied it (NBA), Ridall lost to it (EPL). On average the market is at least as good as a results-only model.
- We do not know when our snapshot falls relative to the close. Dare and Baryla show that this matters for availability and totals.
- No paper covers European basketball markets.
