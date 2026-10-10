# Agent Task: 6.75 Analytics — Phase C (page redesigns)

## Role & goal
You are the **orchestrator** (Opus 5.5, `claude-opus-5-5`). Phase C is four page redesigns
(Teams, Players list, Player page, Forecasts) that share data exports, components and design
tokens. You plan the contracts, fan out to **Sonnet 5.5** (`claude-sonnet-5-5`) and **Haiku 5.5**
(`claude-haiku-5-5`) subagents in **parallel, each on its own branch and worktree**, then review,
merge and verify. You run every real command that decides a merge yourself (checks, builds, the
live check); you own the result.

**Goal:** the live site at https://675hoops.com has a Teams page with a header block and
Four Factors-style graphics, a decluttered Players list, a Player page with the owner's section
order, and a readable Forecasts page. All colour follows `docs/DESIGN.md` (orange data accent,
blue opposite pole, green/red only as the Delta Rule arrow glyph).

Read first: `CLAUDE.md`, `memory.md` (entries 2026-10-09 and 2026-10-10), `docs/SITE_FEEDBACK.md`
(Round 2 notes, "Owner answers", "Phase C" and the Decided sections are the spec),
`docs/DESIGN.md` (Quiet Reference + Delta Rule), `docs/PRODUCT.md`, `docs/PLAN.md` §8.1 (R1 rule),
`src/eurohoops/stats/export.py`, `web/src/pages/{teams,players,forecasts}/`, `web/src/lib/`
(`cols.ts`, `tip.ts`), `web/src/components/`.

## What is already true (verify, do not redo)
- Phases A, B, E are done and live: GBL off the site, 5-season window (`SITE_SEASONS = 5`),
  brand "6.75 Analytics", orange tokens (`--data-1` / `--brand-orange`, blue opposite pole,
  `--delta-up` / `--delta-down` defined but not yet used), Downloads, Methodology, Glossary,
  `validation.json`, Cloudflare Worker hosting at the apex.
- Pages exist today: `teams/index.astro`, `teams/[code].astro`, `players/index.astro`,
  `players/[slug].astro`, `forecasts/index.astro`, `compare/`, `leaders/`, `standings/`.
  Scouting and Shots are hidden (`_scouting`, `_shots`) and redirect.
- The **build-site job has no Python and no data**: it only gets the `site-data` artifact from
  the `predict` job (`web/src/data/site.json`, `web/src/data/stats/`, `web/src/data/api/`,
  `web/public/api/`, `web/public/downloads/`). Any new data file must be produced in the
  `predict` job's "Export the site data" step and be covered by the artifact `path:`.
- Pages other than About/Methodology/Glossary stay free of methodology prose. Tooltips/labels
  must use terms in the Glossary (add a term there if a new label needs one).
- Team codes: site shows display codes (`DISPLAY_CODES` in `publish.py`); data stays source codes.
- Reference sites (boxscorelab.com) are for **layout and section order only**: write every label
  and sentence fresh for EuroLeague data; do not name or link them anywhere on the site.

## Owner rules for all copy and colour (hard)
No AI disclosures, no "gate / gated / shadow log / benchmark / Place" wording. GBL is not on the
site. Colour only on data (Quiet Reference). Green/red only as the arrow glyph on vs-league
deltas, arrow follows the sign, colour follows better/worse (a lower turnover rate is "better");
the figure itself stays ink; never colour as the only cue.

## Spec summary (the full text is in SITE_FEEDBACK.md; these are the decisions)
- **Teams** (`teams/[code]`): season switcher; header follows it. Sub-boxes, each its own box:
  record + season ("25–19 · 2025-26", regular season only), net rating with delta arrow and an
  "108.6 off · 113.9 def" muted line, pace, seasons in the EuroLeague, league rank = standings
  place, playoff box (past seasons: actual result; current season: only the standing).
  Per-stat graphics follow the Four Factors layout idea with league marks; replaces the unclear
  per-stat chart; vs-league deltas use the Delta Rule.
- **Players list** (`players/index`): filters reduced to **Metric, Season, Min/game (typed or
  presets), Show top (5, 10, 25, 50, 100, all), Position (Guard / Wing = Forward / Big =
  Center)**. Remove the rest. Position is the owner's priority.
- **Player page** (`players/[slug]`): keep the header (name, number, team, "N EuroLeague seasons,
  first to last", Compare link, one-line season summary). Summary numbers first; season-by-season
  table **moves to the bottom**. Sections in order: (1) against-the-league graph for key metrics
  with a leaderboard beside it (season top players in that metric, this player highlighted),
  (2) Form (recent games), (3) shot chart frequency + attempts heatmap in the regular style
  (makes ○, misses ×), (4) shot quality, (5) on/off, (6) clutch (5 and 6 only for seasons whose
  stints are already processed; otherwise the section is omitted, no placeholder), (7) projection
  = projected season-end points per game, (8) shot profile vs league, beside the other graphs,
  (9) shot twin, hidden below a shot-count threshold.
- **Forecasts**: the best published model's predictions up front; an accuracy-over-time chart
  against the bookmaker (de-vigged odds); overall score; the raw-log link small, at the bottom;
  plain wording. **Must respect PLAN §8.1 R1**: Elo is the published forecast until M5 (EL)
  beats it at the round-19 look or at season end. "Show the best model" therefore means Elo for
  now; build the page so the model shown is one config value, and do not change what is
  published or logged.

## Contracts to fix **before** you launch anyone (write them into each agent's prompt)
1. **Delta component:** one `Delta.astro` (arrow glyph + sign, props: value, better-is
   `"higher" | "lower"`, format) using `--delta-up/--delta-down`. WP-A builds it first and merges
   it to the phase base before B/C/D use it (or they stub the same prop signature and you
   reconcile). One place decides "better".
2. **Position mapping:** one helper (`web/src/lib/position.ts`) mapping source positions to
   Guard / Wing / Big, used by the Players list filter and the Player page. WP-B owns it; WP-C
   imports it. Decide from the data which source values map where; list unmapped values in the
   report.
3. **Team page data** (WP-A, from `stats/export.py` or the team JSON): per season and team:
   `{record, net_rtg, off_rtg, def_rtg, pace, el_seasons, standing_place, playoff:
   null | {"result": str}}`, league mean/median/rank per stat. Fixture shape written first.
4. **Player page data** (WP-C, mostly exists): add `projection_ppg` per player (projected per-100
   rate × projected possessions per game = minutes share × team pace; **a new derivation, not a
   new model**, you document it in the Methodology "Derived metrics" yourself after merging;
   no WP edits that page), `processed_stint_seasons`, `shot_count` per season for the shot-twin
   threshold, and the leaderboard top-N per metric. Fixture shape written first.
5. **Forecast accuracy series** (WP-D): `web/src/data/…/forecast_accuracy.json`: per
   week or round: model Brier/log-loss/hit-rate, bookmaker de-vigged same metrics, n games.
   Derived from `predictions/` and `odds/` read-only. State the shape first as a fixture.
6. **Files you will not let two agents edit:** `Base.astro`, `global.css`, `docs/DESIGN.md`,
   `daily.yml`, `web/src/lib/cols.ts` (one agent per file: assign WP-A for cols.ts additions
   from the others via your merge, or sequence them), `stats/export.py` schema sections touched
   by more than one WP (assign each WP its own function/module and one registration line that
   you merge).

## Work packages (parallel; branch from **current main**, `git pull --rebase` first)
| WP | Model | Branch | Scope |
|---|---|---|---|
| A Teams (C1) | Sonnet | `phase-c-teams` | Delta component (contract 1), team page data (contract 3), header sub-boxes, season switcher, Four Factors-style per-stat graphics with league marks, vs-league Deltas; teams index adjustments if needed. Tests + fixture refresh (`UPDATE_STATS_FIXTURE=1 uv run pytest tests/test_stats.py`). |
| B Players list (C2) | Sonnet | `phase-c-players` | Filters reduced to the five (spec); position helper (contract 2); typed/preset minutes per game; Show top; keep URL state if the page already has it; remove all other filters and their dead code. |
| C Player page (C3) | Sonnet | `phase-c-player` | Section order and layout (spec), summary first, season table last, regular shot chart style, projection (contract 4), leaderboard beside the key-metric graph, omit-when-unprocessed rules, shot twin threshold (pick the threshold from the data, state it in the report). May split in two agents (C1: layout + sections 1–4, C2: sections 5–9) if the file is too large for one; then C2 branches from C1's merged result. |
| D Forecasts (C4) | Sonnet | `phase-c-forecasts` | Accuracy series (contract 5), page redesign per spec, model shown from one config value (Elo), raw-log link small at the bottom, plain wording. Read-only on `predictions/` and `odds/`. |
| H Sweeps | Haiku | `phase-c-sweeps` (after A–D merge) | Mechanical checks on built `site/`: forbidden words (gate, shadow, benchmark, Place, GBL, "boxscorelab"), every `href` resolves, titles under 60 chars, every new label/term has a Glossary entry, green/red appear only inside `Delta`, no `:hover`-only information, pages with an empty section show no heading. Report only. |
| R Review | **you** (Opus) | — | Per-branch diff review; design pass with `impeccable` and `taste-skill` on the four redesigned pages (screenshots light and dark, desktop and 390 px) before merge; `dataviz` skill for the new charts. |

## Worktrees and subagent hygiene (learned the hard way — put these in every prompt)
- Create worktrees **outside** `Sports_Project` (e.g. `C:\Python\wt\phase-c-<name>`), explicitly
  from current `main`: earlier agents started from a stale base. First command in each agent:
  `git fetch && git switch -c <branch> origin/main`.
- A worktree needs `data/` (gitignored marts and raw cache) and `web/node_modules`: junction them,
  or `npm ci` in `web`. **Before deleting a worktree, remove the junctions first**
  (`cmd /c rmdir <junction>`, never recursive delete through them). A Windows folder delete fails
  while the shell's cwd is inside it.
- Windows: `bash` on PATH is the WSL launcher; put `C:\Program Files\Git\bin` first or four
  `tests/test_workflow.py` tests fail. Piping pytest through `tail` hides the exit code: capture
  to a file and echo `$?`. Run robocopy from PowerShell.
- Agents never touch `predictions/`, `odds/`, `injuries/` (append-only), never commit
  `web/src/data/site.json` or `site/`, never push, never use bare `git stash`.
- `export-stats --from-cache`: no network needed for this phase. esake.gr is not used.
- Commits and PRs carry **no** `Co-Authored-By` or any AI attribution line (CLAUDE.md overrides
  the default attribution). Check every commit message with a grep before merging.
- `git pull --rebase` on a branch with merge commits replays them and conflicts: abort and merge.

## Merge, verify, deploy
1. Review each branch's diff yourself; merge locally `--no-ff` in the order **A → B → C → D → H**
   (A first: it ships the Delta component). Make the `daily.yml` artifact `path:` edit and the
   `tests/test_workflow.py` assertion yourself if any new data directory appears.
2. Full checks from `CLAUDE.md` ("Before commit"), Git Bash first on PATH: ruff check, ruff
   format --check, mypy src, pytest `-n auto --dist loadfile --cov=eurohoops --cov-fail-under=85`
   (about 7 minutes, ~1,368 tests, 92.6% before this phase), vulture (whitelist code written
   ahead of its step). Then `npm run build` in `web` (693 pages before this phase) and a real-data
   review build (`WEB_REAL_DATA=1`) to look at actual pages.
3. **Do not push until the owner says so.** Then: `git pull --rebase` first (the daily bot
   commits to main), push, wait for `ci`, `gh workflow run daily.yml`, watch it
   (`gh run watch`; a dispatch started before the push runs the old workflow), check the live
   pages with curl. The apex can serve the old page for a few seconds after a deploy; the
   workers.dev address updates first.
4. Append a `memory.md` entry and update `docs/PLAN.md` / `SITE_FEEDBACK.md` if a decision changed.

## Open decisions to put to the owner (ask once, early, in one message)
1. Shot-twin threshold (minimum shots) once you have seen the data distribution.
2. Position mapping edge cases (players with mixed or missing positions).
3. Forecasts: which accuracy metric leads the headline (hit rate, Brier, or both); default
   hit rate headline + Brier in the chart.
4. Design review: show screenshots of the four pages (light/dark, desktop/mobile) before merge.

## Report
Branches and commits per WP; the contracts as shipped; check results (counts, coverage); page
count; list of positions that did not map; the shot-twin threshold; screenshots reviewed;
sweep findings; live-site verification (URLs and status); anything deferred. Phase D (models
audit) comes next; do not start it.
