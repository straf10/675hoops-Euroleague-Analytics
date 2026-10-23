# Availability and rosters

Question Q2: how should we adjust for a missing key player, and how much of that does the market already price?
Why it matters: M5's oracle-minutes gap is largest when a top-3 minute-taker is missing (31 games, RMSE +0.84, `docs/models/m5.md`). BasketNews injury snapshots exist in `injuries/euroleague_2026-27.csv` (11 snapshots since 2026-10-07), but no model uses them yet.

## What the papers say

**Absences move the market, and closing lines absorb most of it.** ([dare-2015](../papers/dare-2015-player-absence-nba-lines.md), NBA)
- Absences move lines toward the healthy team: 55.42% of moves overall, 67.95% when the absent players' value AV ≥ 5 (Table 1, p.4).
- **Opening lines** misprice absences. Betting the home team when the visitors are missing players won 57.06% at AV ≥ 10 and 64.36% at AV ≥ 20 (Table 2, p.5). The break-even is 52.38%.
- **Closing lines** remove most of it. All games: 51.30%, below break-even (Table 3, p.6).
- Lesson for us: an availability edge, if any, sits in early lines. The closing line is a hard benchmark for an availability-aware model.

**Strength models without availability data pay a price.**
- [lopez-2017](../papers/lopez-2017-how-often-best-team-wins.md): the NBA has the largest week-to-week strength noise. The authors attribute it to injuries, rest and trades (p.18). They say market prices include injuries (p.6), but they do not test it.
- [glickman-1998](../papers/glickman-1998-nfl-state-space.md): the model does not include injuries, and the authors list that as a limitation (p.6).
- [tian-2024](../papers/tian-2024-spectral-dynamic-bradley-terry.md): the authors name injuries as a reason the Bradley–Terry assumption fails (p.11).
- [baryla-2007](../papers/baryla-2007-nba-early-season-totals-bias.md): early-season forecast errors are blamed on player movement and coaching changes (fn. 3, p.2).

**Player-level structure.**
- [santosfernandez-2019](../papers/santosfernandez-2019-bayesian-sports-review.md) describes Deshpande & Jensen's lineup model: margin = home advantage + Σ player effects + team terms (Eq. 4, p.5). This is the same structure as our M3/M5. It reports no missing-player test.
- [macridemartino-2026](../papers/macridemartino-2026-dynamic-bradley-terry.md): season-to-season jumps are larger for teams with big roster turnover (Table 1, p.11, the OKC and PHI examples).

## What we do now
- M5: Σ projected-minute share × RAPM rating, from recent rotations. No injury input.
- ELOR: a roster-continuity prior at season start (passed CV).
- PLAN §5.6: report a projected-roster and an oracle-roster variant; the oracle is never logged live.

## Disagreements and gaps
- No paper measures how much a missing player costs in EuroLeague or GBL games. Dare measures market moves, not outcome effects.
- No paper tests an availability-aware model against closing odds. Dare's result implies such a model can at best match the close, and can beat early lines.
