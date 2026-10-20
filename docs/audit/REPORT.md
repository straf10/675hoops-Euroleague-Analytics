# Before / after report — branch `chore/optimize-review` (2026-10-20, not pushed)

Method: the same scripts for both columns. Pipeline stages ran on identical scratch copies of the repo and data (no network; `ingest`, `odds`, `injuries` skipped), so the committed `predictions/` and `odds/` were never touched. "Before" = HEAD 02afc1b, "After" = HEAD 55cb665.

## Result in one paragraph
The repo was already clean (ruff/mypy/vulture 0, 92 % coverage, Lighthouse 1.00), so the honest gain is small: **−137 net Python lines, a vulture check that works again, 6 web tests that no CI step ran now guarded, ≈ 1 s less start-up per `predict`/`score` call, two stale docs filed.** Every published number is unchanged. The big-ticket items (export-stats 260–340 s, shared PBP parsing, persisted WP fit) were found and measured but not executed: they touch model-adjacent code and need your decision.

## Metrics
| Metric | Baseline | After | Delta | % |
|---|---|---|---|---|
| Python LoC (350 files) | 83,716 | 83,577 | −139 | −0.2 % |
| Net diff vs baseline (9 files) | – | +97 / −234 | −137 | – |
| Tracked files | 1,034 | 1,034 | 0 | 0 |
| `.md` files | 75 | 75 (2 moved to docs/history) | 0 | 0 |
| Vulture findings (min-conf 60, with whitelist) | 0 | 0 | 0 | – |
| Vulture whitelist | 294 lines / 136 names | 122 lines / 38 names | −172 / −98 | −58 % |
| ruff / mypy issues | 0 / 0 | 0 / 0 | 0 | – |
| Tests | 1,959 pass | 1,959 pass | 0 | – |
| Test time (full command, idle machine) | 406.3 s | 409.4 s | +3 s (noise) | +0.8 % |
| Coverage | 92.12 % | 92.01 % | −0.11 pt | – (lazy-import lines in research commands are not executed by tests) |
| Web unit tests executed by CI | 300 | 306 | +6 | +2 % |
| JS gzip / CSS gzip / HTML / site.json | 0.05 MB / 0.02 MB / 329.6 MB / 379 KB | not re-measured | – | no frontend file changed except one CSS comment |
| Lighthouse LCP / TBT / CLS / transfer (home) | 1,508 ms / 0 / 0 / 62.7 KB | not re-measured | – | same reason |
| Unused tracked data removed | – | 0 bytes | – | all candidates are pre-registered records or cited (F-08, F-09) |
| `import eurohoops.cli` (warm, µs, 3 runs) | ≈ 3.96 s | 3.55–3.65 s | −0.35 s | −9 % |
| `import eurohoops.research` | ≈ 2.9 s | ≈ 1.3 s | −1.6 s | −55 % |
| `eurohoops.entity.pipeline` imported by `eurohoops.cli` | yes | no | – | – |
| Stage `build` | 55.1 s | 50.4 s | −4.7 s | −8 % |
| Stage `predict` (EL / GBL) | 5.3 / 5.3 s | 4.5 / 4.5 s | −0.8 s | −15 % |
| Stage `score` (EL / GBL) | 4.8 / 4.8 s | 4.2 / 4.2 s | −0.6 s | −12 % |
| Stage `publish` | 74.5 s | 67.0 s | −7.5 s | −10 % |
| Stage `export-stats --from-cache` | 338.0 s | 293.6 s | −44 s | −13 % (WP-1 does not touch it; this is run-to-run variance, not a gain) |
| Peak RSS (build / predict / publish / export) | 347 / 229 / 429 / 1,260 MiB | 333 / 231 / 423 / 1,252 MiB | ≈ 0 | – |
| DuckDB mart | 49.3 MiB | 49.3 MiB | 0 | – |
| CI time | not measurable locally | estimate −15 to −20 s per daily run (19 CLI calls × ≈ 0.4–0.8 s) | – | – |

Stage timings have ± 10 % run-to-run noise on this machine (the same unchanged `export-stats` moved by 13 %); only the import-time numbers, which are deterministic to ± 2 %, are real gains.

## Output identity (the gate)
Same stage sequence, fresh copies of the same pristine snapshot, baseline code vs modified code:
* 118 files in `predictions/ odds/ reports/ injuries/ corrections/ entity/` — **hash lists identical**.
* 1,259 files under `web/src/data` and `web/public` — identical except `site.json`, `stats/meta.json`, `stats/validation.json` and `downloads/manifest.json`, which differ **only** in `generated_at`-style timestamp keys (equal after dropping them).
* `eurohoops --help` and nine sub-command help texts byte-identical (checked by the WP-1 agent; not re-run by me).
* Pre-existing, not caused by this work: `eurohoops build` rewrites `reports/gbl_box_gaps.csv` and `gbl_box_invariants.json` differently from the committed copies (identical in both runs).

## What changed, by finding
* **F-01 (WP-1)** `research.py`: heavy imports moved into the commands that use them. Gain smaller than planned (−0.35 s vs ≈ −1 s expected): `marts` → pandera and the other `cli/*` modules keep most of the start-up cost. Further cuts need F-01b/F-14 (moving shared helpers out of `cli/backtest.py`).
* **F-02 (WP-2)** whitelist 136 → 38 names; the docstring bullets that named removed entries were fixed by me after the agent left them stale.
* **F-32 (WP-3)** `web/scripts/sitemap-lastmod.test.mjs` is now run by `npm test` and CI.
* **F-20/F-21 (WP-4)** `DESIGN_ORANGE_PROPOSAL.md` (status line fixed: it said "awaiting approval") and `SITE_V2_PLAN.md` moved to `docs/history/`; two links updated.

## Deliberately skipped or deferred (why)
| ID | Item | Why not done |
|---|---|---|
| F-10 | One shared parsed-PBP layer for wp / on-off / units / assists / runs / coach style (est. −60…−90 s of ≈ 300 s in `export-stats`) | touches the inputs of every published stat; needs a spike and a memory budget (peak is already 1.26 GiB) |
| F-11 | Persist the fitted WP v1 instead of refitting each export (≈ −43 s) | adds a committed artifact to the pre-registered WP chain: your call (already on your open list) |
| F-12, F-13 | Cache raw-PBP action counts (−10 s publish); cache parsed ESAKE pages (−8 s build) | small gain, adds state files |
| F-01b / F-14 | Move shared input builders out of `cli/backtest.py` (−0.6…−0.9 s per call, removes private cross-imports) | wide pure refactor on the daily path |
| F-03 | Nine whitelisted, production-unused helpers (`p_over`, `p_cover`, `ridge_solution`, …; ≈ 120 LoC + tests) | your rule: only if PLAN.md shows them abandoned (0 mentions) |
| F-04, F-05 | 6 unused args (protocol signatures); import cycle `spm ↔ rapm_dummy ↔ m3_backtest` | intentional / documented deferred-import registry |
| F-08, F-09 | `reports/backtest_*.csv` (33 MB, pre-registered evidence), 12 screenshots, checklist logs | evidence or cited by history docs |
| F-16…F-19 | Front end | measured at the floor: perf 1.00, 63 KB, 8 requests, 5 dependencies all used |
| F-23 | 14 prompts + 21 progress/closeout files | `docs/history/README.md`: they are the pre-registration record |
| F-31 | `ci.yml` runs on both `push` and `pull_request` | changes required checks: yours |

## Residual risks
* WP-1 is the only change that can alter behaviour: an import that now runs later could fail at call time instead of start-up. Mitigated by ruff/mypy (undefined names), the 87 targeted + 1,959 full tests, byte-identical help texts, and the identity gate that ran `build`/`publish`/`export-stats` after the merge. The research-only commands (`shots`, `entity`, `m3-players`, …) are covered only by their unit tests, not run end-to-end.
* Coverage fell 0.11 pt for the reason above; still 7 pt over the gate.
* Lighthouse and the web build were **not** re-run after the change (no shipped file changed); the baseline numbers stand.

## Haiku subagent log (4 agents, 1 attempt each, 0 retries)
| Package | Result | What I checked / corrected |
|---|---|---|
| WP-2 whitelist | ok, exact scope (1 file, 294→122 lines) | verified vulture 0 after merge; **fixed the stale docstring bullets** it left; it also kept duplicate `render`/`media_type` pairs (harmless) |
| WP-3 web tests | ok, 2 files, 1 line each | agent saw 306 tests / 298 pass / 8 skipped and flagged it: the skips are `built_jsonld.test.ts` (needs `../site`); not a defect |
| WP-4 docs | ok, 5 files incl. 2 renames | diff matched the plan exactly |
| WP-1 lazy imports | ok, 1 file (+65/−31), help diffs empty | **missed the ≥ 0.8 s CLI target honestly (0.37 s)** — my acceptance number was too optimistic; hand-added `noqa` to 3 `as` imports ruff split |
Lessons for delegation: Haiku followed tight scope + exact acceptance commands well and reported misses truthfully; my own plan review (Pass 1) caught 3 real errors before any agent ran (SITE_FEEDBACK is cited by source; sitemap test is run nowhere; tests monkeypatch `research.MART_PATH`).

## Decisions (owner, 2026-10-20)
1. Deleted the git-ignored local files `mlruns/`, `dist/` and the `.bak` mart (not recoverable).
2. F-10 approved as a time-boxed spike on its own branch: no merge until outputs are byte-identical and peak memory is no higher.
3. `ci.yml` now runs on `push` to `main` only (pull requests still run).
4. Deleted the three unreferenced prompts (`ci-m5-history`, `perf-site-2`, `phase-c-redesigns`).
5. This report is kept; BASELINE, FINDINGS and PLAN were deleted (recoverable from this session's commit history only if committed, which they were not).
