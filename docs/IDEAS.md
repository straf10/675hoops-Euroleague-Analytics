# Ideas backlog: inspiration from other basketball analytics sites

Captured 2026-10-17 from the owner's notes (ideas 1–19), with a feasibility review against the
code as it stands today. Ideas, not committed work.

**Legend.** Status: **Have** (exists), **Partial** (some of it exists), **New**.
Effort: S (≤ 1 day), M (2–4 days), L (a week or more). Verdict: **Do**, **Later**, **Skip**.

## Summary

| # | Idea | Status | Effort | Verdict |
|---|------|--------|--------|---------|
| 5 | Show the number of simulations | Have | S | **Do** |
| 4 | Data-volume strip (games, PBP events, shots, seasons) | Partial | S | **Do** |
| 15 | Overtime counts as clutch time | Have | S (copy) | **Do** (say so) |
| 6 | ORtg vs DRtg scatter | Have | S | **Do** |
| 14 | Pace vs net rating scatter | Have | S | **Do** |
| 2 | Last matchday: predicted vs happened | Have | S | **Do** (add a summary line) |
| 3 | Strength of schedule: played, remaining, next 5, home/away, rest, travel | Partial | M | **Do** |
| 17 | Minutes-weighted roster continuity | Have | S–M | **Do** |
| 12 | Best duos and five-man units, minimum minutes | Have | M | **Do** |
| 11 | Assist network per team | Partial | M | **Do** |
| 7 | Game pages: in-game win probability, swings, runs, box score | Partial | L | **Do** (flagship) |
| 13 | Metric list (RAPM, WPA, GCI, …) | Mixed | — | See §13 |
| 9 | RAPM | Have | — | Expose on site |
| 1 | Coach pages | Have | M–L | **Later** (trim scope) |
| 10 | MVP ladder | New | M | **Later** (after 7) |
| 16 | Referee metrics | New | M | **Later** (careful framing) |
| 18 | Elo carried over + home/away net ratings | Partial | M | Test as a shadow model |
| 8 | Scan the Laloudakis repo | Done | — | See §8 (borrow WP recipe, sim backtest) |
| 19 | Scan GN Basketball Intelligence | Done | — | See §19 |

Suggested order: quick wins (5, 4, 15, 6, 14, 2) → team-page batch (3, 17, 12, 11) → in-game win
probability model and game pages (7, then WPA and game-control metrics) → MVP ladder, coaches,
referees.

## What the data already holds (checked 2026-10-17)

- **Box scores** (`data/raw/euroleague/boxscore/E*/`): `Coach` per team per game, a `Referees`
  string per game (three names), `Attendance`, points by quarter (`ByQuarter`), team and player
  lines. Every cached season since 2007-08.
- **Play-by-play** (`data/raw/euroleague/playbyplay/`): substitutions (`IN`/`OUT`), shots, `AS`
  assists (a separate row next to the made shot), `TOUT` timeouts and `TOUT_TV` TV timeouts, fouls
  by kind (`CM`, `OF`, `CMT`, `CMU`, `C` coach, `B` bench), and `CCH` coach challenges.
  **Challenges are logged from 2023-24 only, and no field records whether a challenge succeeded.**
- **Shot coordinates** (`points/`), season roster lists (`people/`), schedules, standings.
- **Built marts and models:** stints with per-game checks, possessions, on/off and clutch
  (`stats/onoff.py`), rest features (`models/rest.py`), RAPM with a box-score prior
  (`models/rapm.py`, `spm.py`, `rapm_posterior.py`), M1 decayed-ridge team ratings
  (`models/team_eff.py`), projected minute shares (`models/minutes.py`, `rotation.py`), M7 season
  simulator (`sim/season.py`, 10,000 simulations live).

## 1. Coach pages — Done, trimmed

| Part | Feasible? | Notes |
|------|-----------|-------|
| All-time W/L | Yes | `Coach` per game in every box score; mid-season changes are handled because it is per game. Needs name normalisation ("KOKOSKOV, IGOR"), like `parse/player_names.py`. |
| W/L by quarter | Yes | `ByQuarter` gives quarters won, lost, tied. Descriptive only. |
| Challenges won | **No** | `CCH` exists from 2023-24, but there is no outcome field. Inferring it from what follows (a foul removed, possession change) is unreliable. Show "challenges used" at most. |
| After-timeout (ATO) scoring | Yes | `TOUT` by the coach's team, then points per possession on the next possession, from the possessions parse. Compare with the team's overall points per possession; samples are about 20 timeouts per team per game-week, so use season totals with an interval. |
| Rotation use | Yes, needs a definition | Proposal: **minutes quality** = the share of minutes given to the coach's better players, i.e. the correlation (or minutes-weighted mean) of minutes with the player's pre-game RAPM. Add descriptive depth (players above 10 min, top-8 minute share). "How well" is otherwise subjective. |
| Clutch record | Weak | Close-game records are mostly noise. If shown, show wins **above expectation** in games within 5 points at 5:00, with a sample size. |
| Coach H2H | Yes | Trivial from the per-game coach column. |
| Best single metric | — | **Wins above expectation**: actual wins minus the sum of pre-game Elo win probabilities. This one number answers "does this coach beat what the roster says". Roster-aware expectation (M5) is better still. |

Verdict: Later. Build it after team pages; start with W/L, H2H, wins above expectation and ATO.

## 2. Last matchday recap — Done (small)

The Forecast record page already has a "Latest round" block (each forecast beside the result) and
a round recap share card (`lib/cards/site`). Missing: a one-line headline above it, e.g. "Round 5:
7 of 10 called, Brier 0.19 vs home-win baseline 0.24; biggest miss: X beat Y at 22%." Data is
already in the scored log.

## 3. Strength of schedule — Do

Today: one number on team pages (`api/readmodel.py:_schedule_strength`): mean **current** Elo of
every opponent on the schedule, played and remaining together.

Proposal:
- **SoS played**, **SoS remaining**, **SoS next 5**: mean opponent Elo (current ratings — the best
  estimate of how strong the opponent is; pre-game ratings would mix in rating drift).
- Adjust each game for venue: express it as the opponent's rating ± home-court Elo (hca 90), or as
  the expected win probability of an average team in that game. The second is easier to read:
  "an average team would win 46% of these games".
- **Rest**: mean days of rest vs opponent, from `models/rest.py` (already computed for M5; covers
  both competitions, which matters for Olympiacos and Panathinaikos).
- **Travel**: needs a small static table of arena coordinates (about 25 cities); great-circle km
  between consecutive away venues. Cheap, but descriptive only until a model shows it matters.
- Show on team pages; add **SoS played** and **SoS remaining** as two sortable columns in the
  Teams "By net rating" table (beside ORtg, DRtg). Also usable on the Season projection table.

## 4. Data-volume strip — Partial (no shot count)

A single line on the home or About page: games analysed, play-by-play events, shots with
coordinates, seasons. Count at publish time from the marts; no new data needed.

## 5. Number of simulations — Done (trivial)

`live_sim.LIVE_SIMS = 10_000`, and `sim.n_sims` is already in the payload, but it is only shown
inside column tooltips on the Season projection page. Put it in the lede: "Based on 10,000
simulated seasons, updated daily."

## 6 and 14. ORtg/DRtg and Pace/Net scatters — Done

Both use the team factors already published for the Teams page. One chart each on the Teams index,
season selector shared with the table. Design rules: neutral marks, colour only on the data,
labels by display code; DRtg axis reversed so "up and right" is good on both axes; league averages
as quadrant lines. Consider M1's **adjusted** ratings (schedule-adjusted, decayed) as a toggle:
that is the KenPom-style rating from §13, already built.

## 7. Game pages with in-game win probability — Partial, no per-player WPA (flagship, large)

What is needed:
1. **In-game win probability model** (new). Features: score margin, seconds remaining, pre-game
   Elo difference (or pre-game P(home) from the published forecast), home, possession if
   derivable, `margin / sqrt(time fraction)` (see §8). Logistic regression with time interactions
   first, gradient boosting second; train on 2007–2022 play-by-play, validate and test on later
   seasons, isotonic calibration on out-of-fold predictions, check calibration by time bucket.
   Start every game's chain at the published pre-game P(home), not 0.5. The closed-form fallback `WP = Φ(margin_adj / (11 · sqrt(t/2400)))` is the baseline to
   beat.
2. **Per-game outputs:** the win-probability line, top swings (largest WP change per play or per
   run), scoring runs (top 3 per team; runs need no model), and the box score per team.
3. **Player impact in that game:** WPA per player (sum of WP changes on his events) next to
   plus-minus and the box score.
4. **Game pages:** five seasons × ~330 games ≈ 1,700 static pages; the site build already handles
   per-player pages at that scale. Link from Results, team schedules and forecast rows.

This unlocks WPA (§13), the game-control metrics (§13) and part of the MVP ladder (§10).

## 8. Laloudakis euroleague-analytics repo — scanned (Sonnet subagent)

Read-only scan of github.com/KonstantinosLaloudakis/euroleague-analytics (nothing executed). It is
the source of most of the metric list in §13. Their reported accuracy numbers were not checked.

| Technique | How they do it | Pitfalls | For us |
|-----------|----------------|----------|--------|
| In-game WP (`train_wp_model.py`) | One row per scoring event, 2007–2025. Features: margin, seconds left, time fraction, OT flag, margin × time, **`margin / sqrt(time_frac)`**, pre-game Elo diff, last-10-events scoring run, lead changes. `GradientBoostingClassifier` (300 trees, depth 4, lr 0.05). Train 2007–22, val 2023, test 2024–25. **Isotonic** calibration on out-of-fold expanding-window predictions (not Platt, despite the site text). | `is_home` is always 1 (dead feature); OT clock hard-coded; the WPA chain starts at 0.5, not the pre-game WP. | **Adopt the recipe for §7**, fixing those three. |
| WPA (`calculate_wpa.py`) | ΔWP of each PBP row goes to that row's player, sign-flipped for the away team, × 100. | Shooter takes all credit; no assist or defender split. | Adopt with an assist split (e.g. share ΔWP of an assisted make). |
| RAPM (`calculate_rapm.py`) | Pass 1 ridge α 100; box-score ridge fitted on pass-1 output; pass 2 `RidgeCV` shrinks toward that prior. | Prior fitted on the same season it shrinks (circular); CV not grouped by game (leaks); one season; no intervals. | **Nothing to borrow**: our `rapm_spm` is walk-forward, multi-season, with intervals. |
| Season sim (`simulate_monte_carlo.py`) | Margin = 3 + s_home − s_away + N(0, 12²). Strengths: joint Gaussian posterior, prior mean from last season's Elo (75% carry), prior weight ≈ 7 games, tuned on 2016–24. One strength vector drawn per simulation. EuroLeague tiebreakers. | H2H tiebreak approximated. | Ours (M7) has the same structure (M1 posterior, per-sim draws, rule tiebreakers). **Borrow their backtest**: checkpoints at rounds 4/8/12/20 since 2016, log loss on Top 4/6/10, a cap on wrong extreme calls (p ≥ 0.95 or ≤ 0.05 wrong ≤ 3%), binned calibration. Useful for diagnosing why M7 v1 failed its check, and an **Elo-based prior** is a cheap variant to try. |
| Elo (`calculate_elo.py`) | K 10, HCA 50, 75% carry, no margin-of-victory multiplier. | — | Cross-check only; ours is tuned by backtest. |
| Adjusted ratings | KenPom-style multiplicative iteration, decay 0.97 per round. | Not possession-based, not venue-adjusted. | No: M1 is better. Per-round decay is a variant at most. |
| Remaining SoS | Opponent's **home** win % when we play away, **away** win % when we play home. | Raw win %, noisy early. | Same idea as the venue adjustment in §3; do it with Elo. |
| Home-court decomposition | Home-minus-away split into shooting, free throws, turnovers, offensive rebounds, opponent "squeeze", residual. | Crude PPP 1.0; per-team values noisy. | Later, descriptive site piece only. |
| Game Control Index (`calculate_gci.py`) | Dominance, control (> 0.6), drama (total variation), comeback (1 − min winner WP), crunch (ΔWP last 300 s), killer instinct; composite 35/25/20/20. | Composite weights arbitrary. | **Adopt the parts after §7**; skip the composite. |
| Clutch (`clutchStats.py`) | Period ≥ 4, ≤ 300 s left, margin ≤ 5 **before** the play; OT included. | — | Identical to ours (§15). |
| Assist network (`shot_creation_network.py`) | Passer → scorer edges weighted by an expected-FG% table (zone, shot type, distance). | — | **Adopt in §11 using our M2 xPTS** instead of a lookup table: "expected points created" per passer and per pair. |
| MVP score, WIR | Hand-weighted composites. | Arbitrary. | No (§10, §13). |
| Matchup calibration | Postseason probabilities were badly overconfident (Platt slope 0.37 on n = 71) because the in-game model was reused at t = 2400 s for pre-game odds. | Fit on tiny n. | Lesson: never use the in-game model as a pre-game forecaster; keep the published Elo forecast as the WP chain's starting point. |
| Referees, coaches | None (coaches: after-timeout CSVs only). | — | — |

Their weakest point is ours strongest: they have no live, logged record, and their
accuracy tracker replays with current ratings (look-ahead).

Top things to borrow, ranked:
1. The WP model recipe (with fixes) → §7, WPA, game-control metrics.
2. The season-sim backtest at round checkpoints, plus an Elo-prior variant of M7.
3. Game-control parts (drama, comeback) as game-page content.
4. xPTS-weighted assist network → §11.
5. Venue-aware remaining SoS → §3.

## 9. RAPM — Have

We already run RAPM with an informed box-score prior (`rapm_spm`): O and D parts, time decay,
walk-forward fits, posterior intervals (M3 card). That is the same idea as the "two-pass informed
prior" described on the other site, but our prior is fitted walk-forward, so it is leak-free.
What is missing is exposure: M3 "feeds no live prediction and no site page" apart from the player
projection block. Proposal: a RAPM leaderboard (O, D, total, interval, minutes) and a RAPM line on
player pages.

## 10. MVP ladder — Later

Composite scores with hand-picked weights (PIR + WPA + win% + consistency + clutch) are arbitrary.
Better: a transparent ladder from components we can defend — RAPM (or SPM) per minute × minutes
played, team win% or team rating, availability — and **backtest it against past MVP winners
(2007–2026)**: report the winner's rank on each season's ladder. Add WPA once §7 exists. Label it
"not a forecast of the vote" unless the backtest supports that. Over/under-performing team = actual
wins minus Elo-expected wins (same as §1).

## 11. Assist network — Partial, no xPTS weighting

Pair each `AS` row with the made shot it belongs to (same team, same clock, adjacent row) to get
passer → scorer counts and the points they produced. Chart: an arc or chord diagram per team-season,
arc width = assists between the pair, minimum threshold to keep it readable. Validate pairing
against box-score assist totals (target ≥ 98% matched). Extra layer from §8: weight each assist by
the M2 xPTS of the shot it set up, giving "expected points created" per passer and per pair.

## 12. Best duos and units — Done

From the stints mart: net rating per 100 possessions for every pair and five-man unit, with a
minimum (e.g. 100 minutes for pairs, 50 for units) and the sample shown. Raw lineup net ratings are
very noisy; show possessions and an interval, and optionally the RAPM-based expected net rating of
the unit next to the observed one.

## 13. Metric list from the other site

| Metric | Status | Verdict |
|--------|--------|---------|
| RAPM with informed prior | Have (`rapm_spm`) | Expose (§9) |
| WPA | New | After the WP model (§7) |
| WIR (reweighted PIR) | No | Skip: hand-picked weights; our SPM fits the weights to impact |
| True plus-minus per 40 | Have as on/off (`onoff.json`) | Add per-40 view next to RAPM: shows who context helps |
| MVP score | New | §10 |
| Adjusted ratings, KenPom-style | Have (M1 decayed ridge, schedule-adjusted) | Show on Teams (§6) |
| Elo | Have (K 20, HCA 90, 25% reversion, tuned by backtest) | Nothing to borrow; their K 10 / HCA 50 were not tuned |
| Strength of schedule | Partial | §3 |
| Home-court decomposition per team | No | Later, descriptive only; per-team home edges are mostly noise (see `docs/models/diag_home_court.md`) |
| In-game WP model (GBM + Platt) | New | §7 |
| Logistic-regression game forecaster | Have more (Elo, M1, M5, POOL) | Nothing to borrow |
| Monte Carlo season sim | Have (M7: strength drawn per simulation, tiebreakers per rules, 10,000 sims) | Borrow: clinch/elimination logic (show 100%/0% only when mathematically settled) and their calibration framing; M7 v1 failed its check, so compare their backtest method with ours |
| RAPM ridge details | Have | — |
| Game Control Index (dominance, control, drama, comeback, crunch-time swing, killer instinct) | New | Cheap after §7; show per game and per team. Skip the 0–100 composite (arbitrary weights); show the parts |
| Glossary (per 100, stint, ridge, TS%, four factors) | Have (`lib/glossary.ts`) | Add any new terms |

## 15. Overtime in clutch time — Have

`stats/onoff.py` counts period ≥ 4 (the 4th quarter and every overtime); in an overtime the
"last 5 minutes" window is the whole period. Both clutch on-court stints and clutch points follow
this rule. Action: say "including overtime" in the glossary and the Clutch block.

## 16. Referee metrics — Later, careful framing

Data: three referee names per game in every box score. Metrics: fouls and free-throw attempts per
100 possessions, home-minus-away foul differential, technical and unsportsmanlike fouls,
challenges in their games. Adjust for the teams playing (a ridge with team and referee columns),
otherwise a crew that works Olympiacos games looks strict. Show samples; describe tendencies, never
"bias". Referees are not modelled anywhere today.

## 17. Roster continuity, minutes-weighted — Done

Returning-minutes share: of last season's minutes for the club, the share played by players on
this season's roster (roster from `people/E{season}`). A
25-minute starter leaving counts about 25× a 1-minute player. Variant: weight by
minutes × RAPM ("returning impact"). Show on team pages and in the Teams table. The ELOR build
already produces both inputs, so this is mostly a publish step. Note: `parse/continuity.py` is about
club codes, not players.

## 18. Elo from previous seasons + home/away net ratings

- **Cold start:** already handled. Elo carries 75% of last season's rating (reversion 0.25), M7's
  prior comes from M1's committed parameters, and ELOR (built, not run) adds a roster-based
  preseason rating.
- **Home/away split net ratings:** new. Worth one shadow model: Elo + per-team home and
  away net ratings, shrunk toward the league home edge. Expect little: per-team home advantage is
  mostly noise in most leagues, and our own diagnostic could not even pin down the league-wide
  value. Test it, do not assume it.

## 19. GN Basketball Intelligence — scanned (Haiku subagent)

The page is a marketing page: one static HTML file with inline JS, no API or data files, and
every EuroLeague chart uses **mockup data** (labelled "Illustrative · mockup data"). So there is no
real method to reverse-engineer; the value is in the presentation ideas.

Features it lists for EuroLeague: lineup net rating, Win Shares and VORP (cross-checked), two-way
value map, momentum index, clutch, after-timeout, quarter flows, rotation and subs, rebounding
zones, assist → scorer links, possession quality, skill curves (efficiency vs usage), live
win-probability tracker (external demo, not reviewed).

Seen in their code: a six-axis player-archetype radar with cosine-similarity "style match"
(≥ 90% near-identical, ≥ 80% cousin); a two-way quadrant with thresholds at 60/100; a league
translation projector with fixed scale factors (not fitted); a projected-vs-actual scatter drawn
from a seeded random generator.

Worth borrowing:
1. **Calibration plot from our own logged predictions** (predicted vs observed by bin, with the
   diagonal and counts). We have the real data they only mock up.
2. **Two-way quadrant** for players: O-RAPM vs D-RAPM, quadrant lines at league average.
3. **Quarter flows** per team (who starts slow, who closes): from `ByQuarter`, cheap.
4. **Skill curve**: efficiency vs usage per player, binned. Cheap from box scores.
5. Plain-language similarity bands on Shot Profile Twin ("near-identical", "cousin").

Not worth borrowing: fixed translation factors (our M4 is fitted), hand-typed profiles.
