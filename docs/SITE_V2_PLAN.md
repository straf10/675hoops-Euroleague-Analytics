# Site v2 plan: declutter, new metrics, Compare, Play (draft 2026-10-18)

Owner feedback of 2026-10-18 (items 1–11), checked against the code and the earlier decisions, then merged with
yesterday's backlog waves (`docs/IDEAS.md`; Wave 1 shipped 2026-10-17). Nothing here is approved work yet. Model
changes still need a protocol and a gate, and `predictions/` is untouched by all of it.

Research inputs (Haiku subagents, 2026-10-18): boxscorelab `/players/` (strip plot), `/visualize/?t=shape`
(percentile polygon), `/teams/detroit-pistons/shots/` (team shot chart); a notes check for the Form window.

**Effort:** S ≤ 1 day, M 2–4 days, L a week or more.

---

## 0. Decisions needed from you (blocking items are marked ●)

| # | Decision | My recommendation |
|---|----------|-------------------|
| ●D1 | **Sign colours.** The Delta Rule (`DESIGN.md:180`, your decision of 2026-10-10) says green/red appear only as the ▲▼ arrow and figures stay ink. Colouring +/-, Net and clutch net needs a new rule. | Add a **Sign Colour Rule**: signed "for minus against" figures (+/-, Net rating, on/off net, clutch net) colour the figure green when positive and red when negative, and always keep the sign. Nothing else changes. |
| ●D2 | **Per 36 / per 100 on Players.** You removed Rate on 2026-10-09 (`SITE_FEEDBACK.md:204`, decision 8). | Bring it back. `rated()` in `lib/players.ts` already computes all three rates, and Compare uses it. |
| D3 | **Form window.** Your note of 2026-10-09 (`SITE_FEEDBACK.md:205`, decision 9) says "last 10". The page showed "last 6" only because six games have been played so far. Nothing in the models uses this number (`form.ts:23`, `Form.astro:15`; `export.py` `WINDOWS` and `config.projection_games` are separate). | Change it to 5, as you asked. It matches the glossary's Last 5/10/20. |
| ●D4 | **Against the league:** (a) two graphs, league and position, or (b) one graph with a League / Position switch. | **(b)**, with the graph widened into the space the top-ten list leaves. A cheaper option (c): one graph whose rails carry two reference ticks, league average and position average, so no switch is needed. |
| D5 | **Positions:** Wing → Forward, Big → Centre. The EuroLeague listing already says Guard/Forward/Center; we renamed them on 2026-10-10. | Do it: one map in `lib/position.ts`, plus the glossary. Do it before D4, because the Position label reads "against the other forwards". |
| D6 | **Intervals (80%/90%).** `PRODUCT.md:35` says every model number shows its interval. After the removals, intervals remain only on the RAPM line, shot-making and Forecast calibration. | Keep them and add a "?" hint. The 80% labels leave with Projection anyway. |
| D7 | **Share cards.** | Hide the link now. Use Cloudflare analytics to count `/cards/*` hits and og:image fetches for 3 weeks, then delete them unless the number is meaningful. Deleting them needs a fallback og:image for players (`og.png`). |
| ●D8 | **Leaders.** Keep it as a separate page or merge it with Compare? | Keep it, but rebuilt as an **overview**: about 15 small boards on one screen (NBA-style), each linking to Players with that metric preselected. Drop the court lineup. Compare stays head-to-head (players **and** teams). The two pages do different jobs; merging them would make one page do both badly. The MVP ladder (IDEAS #10) later gives Leaders a second reason to exist. |
| ●D9 | **Team logos on the charts.** We can technically: the API returns crest URLs (`club.images.crest`). Two things block it: your rule "no crests" (`PRODUCT.md:45`), and the clubs' trademarks on a site that is not affiliated. Hotlinking a third-party CDN would also break the self-hosting rule. | Don't use crests. Use two-tone club-colour discs (from `lib/jersey.ts`) with the code on hover. That extends the Club-Colour Exception to scatter marks only. If you accept the trademark risk, the other route is self-hosted 24 px crests, after amending `PRODUCT.md`. |
| ●D10 | **Play: accounts and backend.** The site is static on Cloudflare today, so logins need a server and a database. They also bring personal data from EU users (GDPR: privacy page, account deletion). | Run it in two phases. **Phase 1:** no accounts; games and daily streaks live in the browser. **Phase 2:** Cloudflare Pages Functions + D1 (same account, free tier), sign-in with Google/GitHub only (no passwords, no email sending), and the server scores leaderboard runs. Start phase 2 only if phase 1 brings people back (check return visits in analytics). |
| D11 | **Shot-making colours.** The map is orange ↔ **teal**, not green. | Keep teal and write the caption with the colours actually on screen. Add a small legend bar: worse ← league → better. |
| D12 | **Methodology text you sent.** It says "NBA season". It says the pipeline "stops out of season", but `daily.yml` has no season guard and runs every day. It says "nothing is scraped from another site", but M5's injury snapshots come from BasketNews. The Corrections text you pasted is the Refresh text again. | Say "EuroLeague season". Either build the off-season stop (task M2) or cut that sentence. Credit BasketNews for injuries. Send me the Corrections text you meant. |
| D13 | **RAPM as a Players metric.** RAPM exists for finished seasons only (latest 2025-26, 500-minute floor). The Players page opens on 2026-27. | List RAPM in Metric only for seasons that have a board, with a note. A live-season RAPM from the daily M3 fit is possible but would be a new published model number, so it is a separate decision. |
| D14 | **WP protocol (yesterday, still open).** The assist split: the pre-study's validity gate failed (r = −0.05). | 100% of the credit to the scorer, as a stated convention. This unblocks yesterday's Wave 3. |

### Owner answers (2026-10-18)
| # | Answer |
|---|--------|
| D1 | Sign Colour Rule approved. It applies to every Net and +/- figure on the Players, Teams, player and team pages. |
| D2 | Bring back per game / per 36 / per 100. |
| D3 | Last 5 (done in Wave A). |
| D4 | (b): one graph with a League / Position switch. |
| D5 | Rename to Guard / Forward / Centre. |
| D6 | Keep the intervals and add a "?" hint. |
| D7 | Measure before deciding. The links must be visible to be measured, so put them back (task S1). |
| D9 | Club-colour discs now (T3). Crests only through the legitimate route in §0.1, never as a "loophole". |
| D10 | Two phases agreed. **Play moves to a late wave**, so no Play work in Waves B–D. |
| D11 | Teal kept, caption done. |
| D12 | "EuroLeague season" everywhere. Checked: the only NBA mention left is the 0.44 free-throw comparison on Methodology, which is correct. |
| D13 | RAPM in Players for past seasons only. |
| D14 | 100% of the assist credit to the scorer (yesterday's pre-study result). Write the settled values into the WP protocol, then the owner gives final approval. |

### 0.1 Notes on D7 and D9
- **D7, measuring share cards.** Hiding the links stopped any measurement, so you were right. A second problem: Cloudflare Web Analytics counts page views through a script, and a PNG download runs no script, so even visible PNG links would go uncounted. Fix (S1): the share link opens a small HTML page per card (`/cards/players/{slug}/`) that shows the image with a download button. Web Analytics counts those views. The PNG routes and og:image stay as they are. Decide after 3–4 weeks of data.
- **D9, crests.** Non-commercial use is not an exemption: crests are trademarks and also copyrighted artwork, and that holds whether or not the site makes money. (I'm not a lawyer.) The routes that are actually defensible:
  1. **Ask.** Email Euroleague Basketball's media/licensing contact, and the clubs if needed, for permission to show crests as identifiers on a free, non-commercial stats site. This is the clean route.
  2. **Referential use**, as many fan stats sites do: small, self-hosted, unaltered crests used only to identify the club; a line saying the marks belong to their owners and the site is not affiliated; a promise to remove them on request. EU law allows referential use "in accordance with honest practices", but whether a logo (rather than the name) qualifies is unsettled. That makes this a moderate risk you would be accepting, not a safe harbour.

  Plan: ship the discs now behind a `CLUB_MARK = "disc" | "crest"` switch, so crests can replace them in one change if you get permission or accept route 2. `PRODUCT.md:45` changes only when that happens.

---

## 1. What each request becomes

### 1. Players page (`pages/players/index.astro` 949 lines, `lib/players.ts`)

| ID | Task | How | Size |
|----|------|-----|------|
| P1 | Table on the left, chart on the right | Swap the grid order. On a phone the table comes first and the chart sits below it. | S |
| P2 | **New chart, boxscorelab style** | boxscorelab `/players/` has no x/y scatter: it is a vertical **strip plot** of every player who passes the filters (value axis, nice ticks), with simple jitter (sort by value, bin per 6 px, alternate ±6 px). The top-N dots (Show top) are in the accent colour and the rest are grey. There are no names on the dots. Hovering a dot or a row highlights the other, and clicking a dot opens the player page. Our version: new pure `lib/strip.ts`, shared by the build and the page (same pattern as `lib/scatter.ts`). It replaces `chart()/chartHtml()/ticksHtml()/gridHtml()`, which removes the duplicate names. Dots slide on a filter change (existing 200 ms convention). | M |
| P3 | +/- coloured | `signClass()` from F1, applied only to the `pm` column | S |
| P4 | Min/game control | Remove the typed `<input type=number>` (lines 97–106) and keep the preset segment with "Min/game" as its heading. `fromQuery` keeps accepting any `minMin` value, so old links still work. | S |
| P5 | New metrics | **Net rating** = 100·pm/poss (both already exported). **AST/TOV** = ast/tov. **AST%** and **REB%** need on-court team totals the export lacks: F5. **RAPM** per D13. Each needs a `Measure` entry, a column set or Metric group ("Advanced"), a poss floor so tiny samples don't rank, and a glossary entry. | M |
| P6 | Per game / per 36 / per 100 switch | Add `rate` to `View`, the query string and a segment control. `rated()` already exists. Percentages and fixed values ignore the rate, as on Compare. | S |

### 2. Player page (`pages/players/[slug].astro`)

| ID | Task | How | Size |
|----|------|-----|------|
| Q1 | Remove the two-row Last N / Season table next to Form | Remove `table.form-avg` and its `cells` from `Form.astro` | S |
| Q2 | Form window 5 | `recentGames(season, 5)`, and update the comment and copy (D3) | S |
| Q3 | Attempts: All / 2PT / 3PT | `playerDots()` (`stats.ts:224`) keeps only the made bit. Keep the `three` bit too (`attempt_flags` already packs it), so dots become `[x, y, flags]`. Add a small segment that shows only in the Attempts view and filters the two paths in `markChart()`. The count line follows the filter. | S |
| Q4 | Shot-making caption | "Points per shot from each spot against the league's from the same spot. The more orange, the worse he shoots there than the league; the more teal, the better." Plus a legend bar (D11). | S |
| Q5 | Against the league: remove the list, add position | Delete the top-ten side list. Add the position pool to `lib/league.ts` through F6, then the D4 option. The rank reads "12th of 280 · 4th of 90 guards". | M |
| Q6 | Remove Projection | Delete `SeasonEnd.astro`, `ProjectionBlock.astro`, `lib/season_end*.ts` and their tests, after checking with grep that the cards don't use them. The M6 pipeline and its reports stay; the over/under board is already hidden. | S |
| Q7 | On/off and Clutch season switch | `onoff.json` already holds 2022–2025 for each player. Render every season at build time and switch panels the way Shot quality does. **Gap:** the live season (2026) is missing from `onoff.json`. Check why (the stints are probably processed only for finished seasons) before promising the current season. | M |
| Q8 | Clutch net coloured | `signClass()` (F1) | S |
| Q9 | Remove Shot twins | Delete `Comparables.astro`. The M6 `similar` report stays in the pipeline. If D7 keeps the cards, the cards' twins line goes too. | S |
| Q10 | "?" hints on intervals | `InfoTip` (F2), placed on the RAPM line and shot-making rails | S |
| Q11 | Share card | Per D7 | S |

### 3. Leaders (`pages/leaders/index.astro` 646 lines, `lib/leaders.ts` 292)

| ID | Task | How | Size |
|----|------|-----|------|
| L0 | Remove "The Greek Basket League has no RAPM." | One line (`leaders/index.astro:165`). Ship it now in the copy batch. | S |
| L1 | Leaders overview (D8) | Season select (2022-23 → live) plus a Career switch. A grid of about 15 boards: PTS, REB, AST, STL, BLK, **PIR**, total points, minutes, TS%, eFG%, FG%, 3P%, FT%, USG%, Net rating, AST%. Each board shows the leader (one shirt, the only club colour), then ranks 2–5 as text, the qualified count, and "Full list →" to `/players/?metric=…&season=…`. Qualifiers come from the existing `failsFloor` / `most` logic, scaled to EuroLeague game counts (an NBA 300-FGM bar means nothing here). This removes the court lineup, the bench and the RAPM table, so the page gets much shorter. | M |
| L2 | RAPM table leaves Leaders | Only after P5 has put RAPM on Players, so it is never missing from the site | S |

### 4. Compare (`pages/compare/index.astro` 531 lines, `lib/compare.ts`)

| ID | Task | How | Size |
|----|------|-----|------|
| C1 | 3 random curated comparisons per visit | `lib/compare_presets.ts` (list in §5). The build renders all of them hidden, and a tiny script shows 3 at random. Without JS, the first 3 show. A build test fails if a slug or season does not exist. | S |
| C2 | Achievements | New export F7: per player-season, the phase his club reached (RS, play-in, playoffs, Final Four, final, champion) from `games.json` phases. A player counts only if he played at least one game in that phase. Career rows: EuroLeague titles, Final Four appearances and rate, playoff appearances and rate, seasons. Caveat on the page: **since 2007-08**, so for a veteran who started earlier (Spanoulis, Navarro) the career numbers are incomplete. | M |
| C3 | Percentile polygon | Copied from boxscorelab: 7 default axes (PTS, TS%, USG%, AST%, REB%, TOV% inverted, Net rating), rings at 25/50/75/100, one polygon per player (fill 12%, 2 px stroke), axis picker of 3–8 from a list, presets (All-round, Scoring, Creation, Interior, Efficiency). Pool: qualified players of that season, or career pool (≥ `CAREER_GAMES`) in Career mode, with an optional position pool from F6. Raw values stay in the table below. **Design:** it needs a 5-colour categorical series palette, which the site doesn't have (Compare's only colour today is the orange leader dot). It needs a `DESIGN.md` entry and a colour-blind check (dataviz skill validator). | M |
| C4 | Compare teams | A Players / Teams switch on the same page. Team-seasons side by side (ratings, four factors, shot profile), with a team polygon of percentiles among that season's clubs. Uses F6 and `teams.json`. | M |

### 5. Play page (new) — the largest item; phased per D10

| ID | Task | Needs | Size |
|----|------|-------|------|
| G0 | `/play/` shell and game framework: daily seed from the date (same puzzle for everyone), streaks and history in `localStorage` wrapped in try/catch, a shareable emoji-style result line. Static puzzle banks built by `publish` into `/data/play/*.json`. `DESIGN.md` gets a short Play section (same paper and type; green/amber/grey only as answer feedback). | — | M |
| G1 | **Higher or Lower**: two player-seasons and one stat, endless streak plus a daily 10-question run | G0 | S |
| G2 | **Shot chart guess**: a player's attempts chart (`markChart`) from the current or last season, 4 options (distractors from the same club or position) | G0 | S |
| G3 | **Guess the player** (Poeltl-style): each guess reveals club, position, number, EuroLeague seasons, country, height and age, each marked correct, or higher/lower. Needs F8. Pool: live-season players with complete data. Height is 0 for some people records, so check coverage first. | G0, F8 | M |
| G4 | Accounts (D10 phase 2): Pages Functions + D1, Google/GitHub OAuth, HTTP-only session cookie, display name, account deletion, privacy page. Leaderboards (daily, weekly, all-time streak) and friends through invite codes or private leagues. **The server keeps the daily answers and scores the runs**; phase 1 banks ship answers in the static JSON, which is fine only while nothing is ranked. Needs a security review before launch. | D10, G0 | L |
| G5 | **Connections** (16 players, 4 groups of 4): teammates in a season, same club ever, same head coach, same country… A generator plus a solver that rejects any grid where a player fits two groups, then your curation, one per day. Needs W4a (coach-name normalisation). | G0, F8, W4a | M |
| G6 | **38-0 Draft**: each round, pick an era or club, then a player, with one reroll per pick. The five-man (or 8-man) roster's season is simulated from player-season ratings (box-score SPM since 2007 already exists in `models/spm.py`) → team net → 38 game win chances → record. A display-only ratings table: not a model in `predictions/`, no gate. | G0, ratings export | L |

### 6. About

| ID | Task | Size |
|----|------|------|
| A1 | Rewrite in the first person. Purpose: "the EuroLeague hub for the European basketball community." Cut the name sentence. Replace the forecast-pledge paragraph with one line: "Every forecast is logged before tip-off; the full log with its timestamps is on GitHub." Who: "I built this and run it on my own; every mistake is mine." Keep the free/no-account line but change it to "no account needed to read" (G4 adds optional accounts). Update the meta description ("made by one person"). | S |
| A2 | **Pledge sweep.** The same pledge phrasing also appears in `index.astro`, `Tonight.astro`, `lib/forecasts.ts`, `lib/glossary.ts`, `downloads/index.astro` and the cards. Keep one short mention on Forecasts and one in Methodology, and cut the rest. | S |
| F3 | Missing spaces before links (site-wide): see Foundations | S |

### 7. Glossary
D5 only (plus entries for the new metrics, which go in the glossary batch F9).

### 8. Methodology

| ID | Task | Size |
|----|------|------|
| M1 | Source and Refresh text, per D12. The build stamp comes from the build (`20261017T1305` style plus the long date), never hard-coded. "Every page carries the date… in its opening sentence" is not true today: either drop that clause or add the date to every lede (I recommend dropping it; the footer already has it). Corrections: link spacing (F3), and the text once you send it. | S |
| M2 | (Only if you want the "stops out of season" sentence.) A season guard in `daily.yml`/CLI: skip publish when no game was played or scheduled since the last build. | S |

### 9. Downloads

| ID | Task | Size |
|----|------|------|
| DL1 | Group by season (one block per season, its 4 files), with "Download season (zip)" per block and one "All seasons (zip)". Built in `publish` with `zipfile`, `ZIP_STORED` (the members are already gzipped). Today the files total **2.8 MB**, so the zips add about 2.8 MB to the deploy, well inside Cloudflare's 25 MiB per-file limit. Add the zips to the manifest with their sha256, and give the Dataset JSON-LD `distribution` entries. | S |

### 10. Teams index (`pages/teams/index.astro`, `lib/scatter.ts`)

| ID | Task | How | Size |
|----|------|-----|------|
| T1 | Rank by any metric | A Metric select plus sortable headers, the Players pattern (net, ORtg, DRtg, pace, eFG%, TOV%, ORB%, FT rate, 3PA rate, opponent versions). The title follows: "By offensive rating". The query string keeps the state. | M |
| T2 | Net coloured | `signClass()` (F1) | S |
| T3 | Marks | Per D9 | S |
| T4 | Corner notes | A `notes` option on `svgFrame()`: small muted text inside the plot corners. Ratings chart: "Better offence →" along x and "Better defence ↑" on y (that axis is already flipped). Pace chart: "Faster →" and "Better ↑". | S |

### 11. Team page (`pages/teams/[code].astro` 700 lines)

| ID | Task | How | Size |
|----|------|-----|------|
| U1 | Median hint | `InfoTip` (F2) by "League median": "The middle club: half the league is above it and half below. Unlike the average, one extreme club can't pull it." | S |
| U2 | **Shot attempts chart, taken and allowed** | Dots (filled circle make, × miss), `markChart`. Zone chips with multi-select, default All: At the rim, Paint, Mid-range, Corner 3, Above-break 3, Deep 3 (distance cut-off to set). They filter the dots and update a small zone table (FGA, FG%, share, pts/shot, vs league). Zones are classified from x/y in a pure `lib/zones.ts`, with no new stored field. **Reuse:** the hidden Shots explorer (`lib/shots.ts`: `run`, facets, `courtHtml`) already does taken/allowed filtering from the same `attempts.json` (team and opp per shot). Take its pure functions, not its page. **Data:** one static file per club-season with taken and allowed shots, about 5,000 shots, fetched only when the chart's season changes. The live season is inlined. This partly reverses P6's −2.9 MB, so measure the deploy delta. | M |
| U0 | Team page tabs: Overview, Shots, Lineups, Schedule | Needed before yesterday's team batch (#12 units, #11 assist network, #17 continuity) lands, or the page that should get calmer grows by four sections instead. | S |

---

## 2. Foundations (shared work that unblocks several tasks)

| ID | Task | Unblocks | Size |
|----|------|----------|------|
| F1 | Sign Colour Rule: the `DESIGN.md` amendment (D1), `signClass(v)` in `lib/delta.ts` (one place, like `deltaHtml`), CSS for both themes | P3, Q8, T2, U-tables, L1 | S |
| F2 | `InfoTip.astro`: a "?" button that opens the existing tip (`lib/tip.ts`); keyboard and touch, `aria-describedby` | Q10, U1, M1, D6 | S |
| F3 | **Link spacing.** The anchors sit on their own source line after the text ("use\n<a …>GitHub</a>"), and the HTML compression drops that whitespace. Fix: `{" "}` before or after the inline anchors that lose it, plus a build test that scans `site/**/*.html` for a letter directly against `<a` or `</a>` and fails the build | A1, M1 and every page | S |
| F4 | Position rename (D5) | Q5, C3 | S |
| F5 | **Export columns:** `TEAM_TOTALS` + `tm_fgm`, `tm_oreb`, `tm_dreb`, `opp_oreb`, `opp_dreb` (`stats/export.py:49`); player dots keep their flags. Pandera schema and `tests/fixtures/stats/` per the change checklist | P5, Q3 | S |
| F6 | `lib/percentile.ts`: pools (season, career, position, clubs), floors, a lower-is-better list read from the one "better" table in `lib/delta.ts`/`lib/team.ts`, so it is never redefined | Q5, C3, C4, L1, T1 | M |
| F7 | Achievements export (C2): the phase reached per player-season and club-season | C2, G3, L1 career boards | M |
| F8 | People export: height, country, birth date, number and position per player from the cached `people/` files (one per season since 2007; the live season is refetched daily already). Also lets the player-page header show height and nationality. | G3, G5 | S |
| F9 | Glossary batch: every new term (Net rating, AST/TOV, AST%, REB%, per 36, per 100, median, achievements, percentile polygon), written once so the parallel branches don't all edit `lib/glossary.ts` | P5, C2, C3, U1 | S |

---

## 3. Waves and dependencies

Yesterday's backlog keeps its labels (#3, #11, #12, #17, 7a–7f, #10, #1, #16 from `docs/IDEAS.md`).

```
D1 ─> F1 ─┬─> P3, Q8, T2, L1
          │
D5 ─> F4 ─┼─> F6 ─┬─> Q5 (D4)
          │       ├─> C3 ──> C4
          │       └─> L1 (D8) ─> #10 MVP ladder (+ #9 RAPM, done)
F5 ───────┼─> P5 (D13) ─> L2
          └─> Q3
F7 ─> C2
F8 ─┬─> G3
    └─> G5 <── W4a coach normalisation ──> #1 coach pages
G0 ─> G1, G2, G3 ─> (D10 + measured return visits) ─> G4 ─> leaderboards on G1–G6
U0 ─> #12 units, #11 assist network, #17 continuity, U2 sits in the Shots tab
D14 ─> 7c WP model ─> 7d game-page WP ─> 7e WPA ─> #10 WPA layer, 7f game control
7b game-page shell: no dependencies
```

### Wave A: today, no decisions needed (all parallel, all S) — DONE 2026-10-18, merged to main (not pushed)
Done as written, with three choices made along the way: the game log under Form shows 5 rows, like the chart; D7 is half done (links hidden, routes and og:image kept, counting not started); M2 was not built, so the Refresh text makes no off-season claim. The Corrections text is still waiting for the owner.
| Task | Files |
|------|-------|
| L0 GBL line | `leaders/index.astro` |
| F3 link spacing + build test | the `.astro` files with inline links, a new test |
| A1 About rewrite + A2 pledge sweep | `about/`, `index.astro`, `Tonight.astro`, `lib/forecasts.ts`, cards |
| M1 Methodology (minus Corrections text) | `methodology/` |
| Q1, Q2, Q4, Q6, Q9 player-page removals and copy | `Form.astro`, `ShotSections.astro`, `[slug].astro` |
| P1, P4 Players layout and Min/game | `players/index.astro` |
| T4 corner notes | `lib/scatter.ts` |
| DL1 Downloads by season | `publish.py`, `downloads/` |
| Hide the share-card link + start counting (D7) | `[slug].astro` |

### Wave B: foundations (parallel; all decisions answered 2026-10-18) — DONE 2026-10-18, merged to main
Results: Sign Colour Rule live in `global.css`, and the team-header Net arrow is dropped (it only repeated the sign). `InfoTip` added. Positions are Guard/Forward/Centre with `LEGACY_POSITION`. Export has `tm_fgm`, `tm_oreb`, `tm_dreb`, `opp_oreb`, `opp_dreb`, and dots are `[x, y, made, three]`. `lib/percentile.ts` and `lib/better.ts` (single direction source) exist, with `node --test` in CI. `achievements.json` covers 2007 to the season before the live one; champions and runners-up were checked against history for 2007-08 to 2024-25. Share-card HTML pages (noindex, not in the sitemap) are linked again. WP protocol v1 is approved on `wave1/wp-protocol`: ND games excluded, rule D, no possession, no killer instinct, **player WPA not published**.
One agent each:

| Task | Scope |
|------|-------|
| F1 | Sign colours: the helper, the `DESIGN.md` rule, and every existing Net and +/- figure (P3, Q8 and T2 come forward from Wave C) |
| F2 | `InfoTip`, applied to the intervals (Q10) and the team median (U1) |
| F4 | Positions renamed, with old `?pos=` links still working |
| F5 | Export columns and dot flags |
| F6 | Percentile library, plus TS unit tests (`node --test`, Node 24 strips types) in the CI web job. It uses the `Position` type and no literal names, so it needs no wait for F4. |
| F7 | Achievements export, as a new module and file |
| S1 | Share-card pages, links visible again |
| 7a-final | WP protocol values (D14) |

Changes from the draft: F8 waits for Play. F9 is dropped; each Wave C branch adds its own glossary entries, and the orchestrator resolves glossary conflicts at merge. Writing entries now would put terms in the glossary for features that don't exist yet.

### Wave C: page rebuilds, one branch per page so no two branches edit the same file — DONE 2026-10-18 (except play-0, moved late per D10), merged to main
Results:
- **Players:** strip plot (`lib/strip.ts`), a per game / per 36 / per 100 switch, and an Advanced group: Net (15 poss/g), AST/TOV (1 TOV/g), AST% and REB% (10 min/g; Basketball-Reference form on whole-game team totals), and RAPM for the board's season only (500 min).
- **Player page:** All / 2PT / 3PT filter; League / Position switch with "Nth of N · Nth of M guards" (`lib/league_rank.ts`); On/off and Clutch season panels. The live season is missing until 90% of its games pass the stint checks (`onoff.py qualifying_seasons`).
- **Teams index:** any metric (`lib/ranking.ts`); club discs behind `CLUB_MARK` (`lib/mark.ts`). Pace and 3PA rates are "neither" in `better.ts`.
- **Team page:** Overview / Shots / Schedule tabs (no Lineups tab until lineup content exists); a taken/allowed zone chart (`lib/zones.ts`: rim ≤ 1.5 m, deep ≥ 8.0 m). It adds 94 club-season files, 4.3 MB, fetched on season change.
- **Compare:** 11 curated presets. Dropped: #1, #8, #9, #11 (players not in the data) and #16. Achievements: a title counts only if he played in the final.
- **Game pages:** `/games/E{season}_{code}/` with box scores and the top 3 scoring runs per side (`stats/runs.py`, `seasons/{y}/runs.json`, from cached play-by-play; the sums match the final score in all 5,069 games). 1,431 pages. They are linked from the player game log only, since the team page has no results list. `lib/jsonld` sportsEvent hard-codes EventScheduled, so the page builds its own EventCompleted.
| Branch | Tasks | Needs |
|--------|-------|-------|
| players | P2, P3, P5, P6 | F1, F5, F9, D2, D13 |
| player-page | Q3, Q5, Q7, Q8, Q10 | F1, F2, F5, F6, D4 |
| teams-index | T1, T2, T3 | F1, F6, D9 |
| team-page | U0, U1, U2 | F2 |
| compare-1 | C1, C2 | F7 |
| game-shell (yesterday 7b) | box score and scoring runs | — |
| play-0 | G0, G1, G2 | D10 phase 1 |

### Wave D (started 2026-10-18; owner corrections of 2026-10-18 folded in)
Owner corrections after Wave C:
- **K1 (player page, Against the league):** in the legend "Him | League average", put spaces around the "|" separator, and colour the "Him" swatch like the dots in the graph (the page's club colour, e.g. Olympiacos red). This applies in both the League and the Position view.
- **K2 (Compare start):** one lead line, "Add a player by name, or start from one of these:", with the 3 random curated presets below it. The old default suggestions and the separate "Or one of these curated comparisons" section go.
- **K3 (Compare, Accolades):** rename Achievements to **Accolades** and add more data-backed accolades. **Rule change:** a player gets his club's furthest stage, title included, if he played at least one game for that club that season. He does not need to play in the Final Four or the final. This replaces the F7 rule and the Wave C title fix.
- **K4 (team page Shots):** the zone chips also filter the other two shot charts on the tab, so they show e.g. the frequency at the rim. The player page shot charts get the same zone chips.
- **K5 (Strength of schedule):** split into **strength of opponents played so far** and **strength of the upcoming schedule**. Both are recomputed on every daily build, so they change each matchday.

| Branch | Tasks | Needs |
|--------|-------|-------|
| leaders | L1, L2 | players merged (done), F6, D8 |
| compare-2 | C3 polygon, then C4 teams if time | F6, palette entry in `DESIGN.md` |
| compare-fixes | K2, K3 | F7 |
| player-fixes | K1, K4 (player page side) | Wave C |
| team-shots-sos | K4 (team side), K5 + #3 (next 5, home/away, rest) | U0, U2 |
| team-units | #12 duos and units, Lineups tab | U0 |
| team-assists | #11 assist network, Passing tab | U0 |
| continuity | #17 returning minutes (team page Overview + Teams column) | U0, T1 |
| wp-model | 7c, per the approved `docs/models/wp.md` (branch wave1/wp-protocol); no site output, no player WPA | protocol approved |

play-1 (G3) moves to the late Play wave (D10).

### Wave E
| Branch | Tasks | Needs |
|--------|-------|-------|
| mvp | #10 MVP ladder on Leaders | L1 |
| coaches | W4a coach-name normalisation, then #1 coach pages | team batch |
| play-2 | G4 accounts and leaderboards, then G5 Connections | D10 phase 2, W4a |
| wp-pages | 7d, 7e, 7f | 7c |

### Wave F (later)
G6 38-0 Draft; #16 referees; §19.2 O-RAPM vs D-RAPM quadrant (as a view of the Players page, now that RAPM lives there); the model side track (M7 diagnosis, clinch logic, #18), whenever there is time.

**Dropped or parked from yesterday because of the declutter:** §19.3 quarter flows and §19.4 skill curve. I'd rather not add sections while removing others; revisit them after Wave D with the tabs in place.

### Integration rule for every wave
Parallel branches still collide in four places: `lib/glossary.ts` (F9 takes the batch), `tests/fixtures/site.json` (regenerate, never hand-merge), `DESIGN.md`, and `publish.py`/`readmodel.py`. Merge one branch at a time and run the full checks after each, as on 2026-10-17. Each branch checks its pages at 390 px and in dark mode before merging.

---

## 4. Draft curated comparisons (C1)

You edit this list; the build fails if a slug or season is missing. Careers that start before 2007-08 are cut short in our data, so they appear as seasons only.

| # | Label | Players | Mode |
|---|-------|---------|------|
| 1 | MVP seasons | Dončić 2017-18 · Micić 2020-21 · Vezenkov 2022-23 | season |
| 2 | Real Madrid point guards | Llull · Campazzo | career |
| 3 | Rim protectors | Tavares 2022-23 · Lessort 2023-24 · Fall 2021-22 | season |
| 4 | Greek playmakers | Sloukas · Calathes | career |
| 5 | Efes title backcourt | Micić 2021-22 · Larkin 2021-22 | season |
| 6 | Pure scorers | Mike James · Shane Larkin | career |
| 7 | Stretch fours | Mirotić 2021-22 · Vezenkov 2022-23 | season |
| 8 | Olympiacos leaders, a decade apart | Spanoulis 2012-13 · Sloukas 2021-22 | season |
| 9 | Barcelona's go-to scorer | Navarro 2008-09 · Mirotić 2021-22 | season |
| 10 | Winning big men | Kyle Hines · Tavares | career |
| 11 | Fenerbahçe wings | Bogdanović 2016-17 · Nigel Hayes-Davis 2023-24 | season |
| 12 | Volume scorers | Markus Howard 2022-23 · Kevin Punter 2023-24 | season |
| 13 | Big forwards | Shengelia · Hezonja | career |
| 14 | Long-serving wings | Will Clyburn · Marius Grigonis | career |
| 15 | Scoring guards | Kendrick Nunn 2024-25 · Mike James 2023-24 | season |
| 16 | One-season wonders vs long careers | to be picked from the data (a top-PIR single season vs a 10-season career) | mixed |

Check every season and club against the data before shipping; labels make no claim the data cannot back.

---

## 5. Challenge pass (I re-read the plan and tried to break it)

What changed in the plan because of this pass is already written above; this is the reasoning.

1. **"Copy boxscorelab's graph" was not a scatter.** The Haiku report shows a one-axis strip plot. A real x/y scatter of all players would need a second metric picker and would not line up with the table. The strip plot keeps the chart tied to the sorted table, so P2 is M, not L.
2. **The duplicate names disappear with the strip plot.** No separate de-duplication task is needed.
3. **Net rating per player from `pm/poss`** has huge values for small samples. It needs its own possessions floor, not just Min/game. The same goes for AST/TOV (a player with 0 turnovers divides by zero), so show "—" and leave him unranked.
4. **AST% and REB% in the standard formulas use team totals scaled by minutes.** Our usage formula already uses `tm_* · game_sec / sec`, so they follow the same pattern. No on-court play-by-play counting is needed.
5. **RAPM in Players (D13)** would show empty on the default season. Without the "only seasons with a board" rule, the metric looks broken.
6. **Form "last 6".** You may have read 6 as a setting. It is the season's game count. With 5, the label says "last 5" from round 5 on.
7. **Sign colours versus colour blindness.** The validated green/red pair separates by only ΔE 5.3 under deuteranopia (`DESIGN.md:180`). That is why the sign stays mandatory in F1.
8. **On/off season switch (Q7)** looks free, but the live season is missing from `onoff.json`. Without checking, the switch would ship with no current season, which is the one fans want most.
9. **Removing Projection and Twins** leaves dead TypeScript (`season_end*.ts`, `Comparables`, parts of `lib/m6.ts`, card code). Vulture only covers Python. Run a one-off unused-export check (`tsc --noUnusedLocals` or `knip`) in Wave A. The site should shrink by several hundred lines.
10. **Team shot files** undo part of P6's deploy saving. Per club-season files that load only when needed keep a team page at one small fetch, not the 600 KB season file the Shots explorer uses.
11. **Leaders without a purpose versus a merge.** One page that both ranks and compares ends up with a mode switch that hides half of each. Separate pages with a clear job each (overview / explore / head-to-head) are easier to find from the menu.
12. **Compare achievements before 2007.** Career titles for Spanoulis or Navarro would be understated. Hence the visible "since 2007-08" note and season-only presets for them.
13. **Play is the riskiest item for a solo project:** auth security, GDPR, moderating display names, and cheating on leaderboards (static answers). Phase 1 brings most of the value at a fraction of the risk, and its return-visit numbers decide whether phase 2 is worth it.
14. **38-0 Draft ratings** must stay outside `predictions/` and the gated models. They are a display-only table, so no protocol is needed, but the page must not call them forecasts.
15. **The Methodology text** must be true: the NBA line, the off-season stop and the "every page's opening sentence" claim each fail today (D12). The same check applies to every new copy line.
16. **Parallel branches** collide on glossary, fixtures and `DESIGN.md`. F9 and the integration rule remove most of the hand merges that cost time on 2026-10-17.
17. **Time and space.** The strip plot jitter is O(n log n) for about 300 dots. Zone classification is O(shots) once per toggle on about 2,500 shots, so it is fine on a phone. Percentiles are computed at build time (O(n log n) per metric per pool), so the client only reads ranks. The heaviest client work left is U2's dot redraw, which reuses `markChart`'s two-path approach (two SVG paths, not 5,000 elements).
18. **Fixed on re-read:** comparison #15 was labelled "same club", but Nunn and James never shared one. #13 "point forwards" and #14 "wing stoppers" claimed things our numbers can't show, so both labels are now neutral. The shot-chart game (G2) had a false dependency on the 2PT/3PT filter (Q3), so it moved into play-0.
19. **LoC.** New: about 1,200–1,800 lines for Waves A–D without Play (strip, percentile, zones, compare polygon, leaders grid). Removed: court lineup and bench, Comparables, SeasonEnd/Projection, form-avg, the side list, the typed Min input, roughly 700–900 lines. Play phase 1 adds about 1,000–1,500.

---

## 6. Order if you work one task at a time

Wave A (copy and removals, a day) → D1, D2, D4, D5, D8, D9, D10 answered → F1, F4, F5, F9 → players → player-page → F6 → teams-index → team-page with tabs → leaders → compare (C1, C2, then C3, C4) → play-0/1 → team batch from yesterday → WP model once D14 and the protocol are approved → the rest of Waves E and F.
