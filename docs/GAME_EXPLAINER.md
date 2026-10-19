# Game explainer pages: "why the model picked this" (design, not built)

Status: design only (2026-10-19). No code yet. Goal: every predicted game gets a section on its
game page (`/games/[id]/`) showing what the forecast was based on, in core numbers a fan can check.

## 1. The key fact: our forecasts are sums, so they explain exactly

Every published forecast is built as an **expected home margin**, then turned into a win chance
through a fixed distribution (Student-t for M1/M5, the Elo curve for Elo). So the explanation
works on the margin, in points, and the win chance follows from it. That needs no SHAP-style
approximation: the parts add up to the logged `exp_margin` to the decimal.

| Model | Margin is the sum of | Parts we show |
|---|---|---|
| Elo (published now) | `scale × (R_home + home court − R_away)` | home rating, away rating, home court |
| Elo-R (`elor`) | as Elo, with a roster prior fading over the rounds | ratings, roster-prior share this round, home court |
| M1 | expected possessions × (home ORtg vs away DRtg − away ORtg vs home DRtg) + home court | pace, each side's offence vs the other's defence, home court |
| M5 | player part (Σ projected minutes share × M3 rating, scaled by possessions) + team residual + home court + β·rest gap | the players' sum per team, top contributors, who is out vs usual minutes, team residual, rest gap, home court |
| M5 blend | weights × (M5 core_rest, M1, Elo) | each model's margin and its weight |

Example (M5, numbers made up):

```
PAN vs HTA: PAN by 6.8 → 70% PAN
  Home court                        +2.9
  Players expected to play          +3.1   (PAN 4.2 vs HTA 1.1 per 100 poss., × 71 poss.)
    biggest: Nunn +1.4, Sloukas +0.9 ... ; out vs usual: Lessort (−1.2)
  Team beyond its players           +1.0   (system, coaching, fit)
  Rest                              −0.2   (HTA 4 days, PAN 3 days)
  = expected margin                 +6.8   → 70% with a ±10.9-pt spread
```

## 2. Rule that decides the design: log the explanation at prediction time

`predictions/*.csv` are the pre-registered record. An explanation recomputed later would use
later data (more games played, refit residuals, a new model version) and could disagree with the
pick it claims to explain. So:

- When `predict` writes a row, it also writes the parts that produced it, to a new append-only log
  `predictions/explain/<league>_<model>_<season>.jsonl`: one JSON line per (game_id, model,
  model_version, predicted_at_utc), the same keys as the CSV row.
- Each line holds `parts: [{key, label, value_pts}]`, and `inputs` (ratings, ORtg/DRtg, pace,
  projected minutes per player, rest days), and `check: sum(parts) == exp_margin` (rounded to 0.01).
- Same rules as the CSVs: append-only, never rewritten, re-logs for a game add a line.
- `score` / `publish` only read it. Games logged before this ships show "explanation not logged"
  rather than a back-filled one (or a back-fill clearly marked "reconstructed after the fact").

JSONL, not CSV, because the M5 player list is nested and varies per game.

## 3. Where the code would go (when built)

1. **Models return their parts.** Add a `contributions(...)` function next to each predictor
   (`models/elo.py`, `elor.py`, `team_eff.py`/M1, `m5.py`) returning the parts for one game from
   the same arrays the prediction uses, never a second computation path. A test per model asserts
   `sum(parts) == exp_margin` on the backtest games (this test is the guarantee).
2. **`live*.py` writes the explain log** in the same step as the CSV row (same timestamp and
   version), behind the same gates (M1 only if its gate passed).
3. **`publish.py`** joins the log into `site.json` per game: `games[].explain[model]`, applying
   `DISPLAY_CODES` and player display names. A pandera schema covers the log (Change checklist).
4. **Front end:** a `GameExplainer.astro` section on `/games/[id]/` plus a "Why?" link from
   `MatchRow` (Matchday card and forecast log). A waterfall bar (home court → players → team →
   rest → margin), then the margin → win-chance step, then a small "inputs" table. After the game:
   the actual margin on the same axis, and which part missed most (e.g. "an absent player"
   showed up as the gap in the 'players' part).

## 4. Page content (plain words, per DESIGN.md)

- Headline: "We gave PAN a 70% chance, by about 7 points."
- Waterfall of the parts in points, colour only on the bars (home side vs away side).
- "What that means": the spread (±σ) and why a 7-point favourite still loses ~30% of the time.
- Inputs table: ratings and where they rank, last-5 form, expected rotation with minutes, rest.
- Which model: the published one by default; a switch to the others logged for the game,
  each with its own parts (they disagree for reasons we can show).
- After tip-off: result, error, and "biggest surprise" (the part furthest off, when measurable:
  e.g. projected vs real minutes of the players who played).

## 5. Open questions for the owner

1. Back-fill rounds 1–6 as "reconstructed" or leave them without an explanation? (Recommend:
   reconstruct for Elo only, where it is exact from logged ratings; label it.)
2. Show all models' parts or only the published one by default? (Recommend: published by default.)
3. Player-level detail for M5: top 3 per team plus absences, or the whole rotation?
4. GBL: same section for M1 GBL once its gate passes.

## 6. Effort estimate

Elo explain log and page: about 1 day. M1: +½ day. M5 (player list, absences): 1–2 days. Each step
ships alone; Elo first because it is the published forecast.
