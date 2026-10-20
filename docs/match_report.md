# Match report (owner request 2026-10-20)

A dropdown under each game on the main page (Matchday) that shows why the published model ("Our
model", Elo) gave its win probability and margin, then context the model does not use. Reports stay
for finished games. Each report is one small JSON file loaded only when its dropdown is opened, so
the page weight does not change.

## 1. Model-input snapshot (pre-registered)

`predictions/<comp>_inputs_<season>.csv`, append-only like every log in `predictions/`. Written by
`predict.predict_upcoming` in the same run, with the same `predicted_at_utc`, for the same rows it
appends to the Elo log. Columns:

| column | meaning |
|---|---|
| game_id, season, round, phase, tipoff_utc, home, away | as in the Elo log (source codes) |
| home_rating, away_rating | pre-game Elo ratings, 1 decimal |
| hca | home-court advantage added to the home side (0 when neutral), 1 decimal |
| neutral | `true` / `false` |
| diff | home_rating - away_rating + hca, 1 decimal |
| margin_scale | the tuned divisor: exp_margin = diff / margin_scale, 4 decimals |
| p_home, exp_margin | exactly the strings logged in the Elo log |
| model, model_version, predicted_at_utc | as in the Elo log |
| source | `logged` (written at prediction time) or `replayed` (backfill, see below) |

Backfill (`eurohoops backfill-inputs`): for Elo rows already logged without a snapshot, replay Elo
over the games known at that row's `predicted_at_utc` (games tipped off before it), with the
current tuned params, and append a row with `source=replayed` **only** when the model_version
equals the row's and the recomputed `p_home` and `exp_margin` strings equal the logged ones exactly.
Otherwise the game gets no snapshot (the report then says the inputs were not recorded).

## 2. Report JSON

Route `/reports/{competition}/{game_id}`, exported to `web/src/data/api/reports/<comp>/<game_id>.json`
for every live-season game with a row in the competition's Elo log. Codes are **display** codes
(`DISPLAY_CODES`). All context is as of the game's tip-off: only games that tipped off before it
count, so a finished game's report shows what was known before the game. Target size < 8 KB.

```json
{
  "game_id": "E2026_061", "competition": "euroleague", "season": 2026, "round": 7, "phase": "RS",
  "tipoff_utc": "2026-10-22T17:45:00Z",
  "home": {"code": "PAO", "name": "Panathinaikos AKTOR Athens"},
  "away": {"code": "FBT", "name": "Fenerbahce Beko Istanbul"},
  "result": {"home": 88, "away": 80} ,
  "model": {
    "available": true, "reason": null,
    "home_rating": 1612.4, "away_rating": 1588.0, "hca": 90.0, "neutral": false, "diff": 114.4,
    "margin_scale": 28.1234, "p_home": 0.6573, "exp_margin": 4.07,
    "model_version": "0.2.0+425e6393", "predicted_at_utc": "2026-10-20T08:12:00Z", "source": "logged"
  },
  "other_models": [
    {"key": "m1", "label": "Possession model", "p_home": 0.61, "exp_margin": 3.2},
    {"key": "m5", "label": "Player model", "p_home": 0.58, "exp_margin": 2.4},
    {"key": "elor", "label": "Elo + roster", "p_home": 0.64, "exp_margin": 3.9}
  ],
  "form": {
    "home": [{"date": "2026-10-16", "opp": "BAR", "venue": "A", "for": 81, "against": 77, "won": true}],
    "away": []
  },
  "h2h": {
    "since": 2007, "games": 31, "home_wins": 17, "away_wins": 14,
    "last": [{"date": "2026-04-10", "season": 2025, "home": "PAO", "away": "FBT", "home_score": 79, "away_score": 84}]
  },
  "team_stats": {
    "games": {"home": 6, "away": 6},
    "rows": [
      {"key": "net_rtg", "label": "Net rating", "home": 6.1, "away": 3.4, "better": "high", "format": "signed1"},
      {"key": "off_rtg", "label": "Offensive rating", "home": 118.2, "away": 115.0, "better": "high", "format": "num1"},
      {"key": "def_rtg", "label": "Defensive rating", "home": 112.1, "away": 111.6, "better": "low", "format": "num1"},
      {"key": "pace", "label": "Pace", "home": 71.2, "away": 69.8, "better": null, "format": "num1"},
      {"key": "efg_pct", "label": "Effective FG%", "home": 0.552, "away": 0.531, "better": "high", "format": "pct1"},
      {"key": "tov_pct", "label": "Turnover rate", "home": 0.141, "away": 0.150, "better": "low", "format": "pct1"},
      {"key": "orb_pct", "label": "Offensive rebound rate", "home": 0.301, "away": 0.287, "better": "high", "format": "pct1"},
      {"key": "ft_rate", "label": "Free-throw rate", "home": 0.312, "away": 0.270, "better": "high", "format": "pct1"},
      {"key": "rest_days", "label": "Days of rest", "home": 3.0, "away": 2.0, "better": "high", "format": "num0"}
    ]
  },
  "players": {
    "home": [{"name": "Kendrick Nunn", "slug": "kendrick-nunn", "gp": 6, "min": 28.4, "pts": 18.2, "reb": 3.1, "ast": 4.0, "pir": 17.5}],
    "away": []
  },
  "injuries": {
    "snapshot_utc": "2026-10-20T09:30:00Z",
    "home": [{"player": "Juancho Hernangomez", "status": "Out", "return": "Round 9", "comment": "Ankle"}],
    "away": []
  },
  "coaches": {
    "home": {"name": "Ergin Ataman", "slug": "ergin-ataman", "season": {"wins": 4, "losses": 2}, "career": {"wins": 310, "losses": 190}},
    "away": {"name": "Sarunas Jasikevicius", "slug": "sarunas-jasikevicius", "season": {"wins": 5, "losses": 1}, "career": {"wins": 250, "losses": 120}},
    "h2h": {"games": 14, "home_wins": 6, "away_wins": 8},
    "style": [
      {"key": "timeouts", "label": "Timeouts per game", "home": 4.1, "away": 3.6, "format": "num1"},
      {"key": "ato_ppp", "label": "Points per possession after timeout", "home": 1.05, "away": 0.98, "format": "num2"},
      {"key": "clutch_win", "label": "Clutch win %", "home": 0.67, "away": 0.5, "format": "pct0"},
      {"key": "challenges", "label": "Challenges per game", "home": 0.8, "away": 1.1, "format": "num1"}
    ]
  }
}
```

Rules:
- Any block may be `null` when its data is missing; the page then hides that block. `model` is never
  null: when there is no snapshot, `available` is false and `reason` says why.
- `result` is null until the game is played.
- `form`: each team's last 5 EuroLeague games before tip-off, newest first (any season).
- `h2h.last`: the last 5 meetings, newest first; counts are all EuroLeague meetings since 2007-08.
- `team_stats`, `players`, `coaches.style`: the live season's games before tip-off; `players` is the
  top 5 by minutes per game with at least 2 games (fewer when the team has fewer).
- `injuries`: the latest snapshot stamped at or before tip-off; `null` when there is none.
- `coaches`: each side's coach in its latest game before tip-off; `h2h` counts games where the two
  coaches faced each other (any team).

## 3. Page

`web/src/pages/data/reports/[comp]/[id].json.ts` serves each file as `/data/reports/<comp>/<id>.json`.
`MatchRow` shows a "Match report" toggle under the row when a report exists for the game; the first
open fetches the JSON and renders it (`web/src/lib/match_report.ts`). Without JavaScript the toggle
is hidden.
