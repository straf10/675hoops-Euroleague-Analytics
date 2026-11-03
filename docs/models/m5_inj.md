# M5-INJ: M5 with the BasketNews "Out" status applied to minutes (EuroLeague)

Status: live shadow (`M5INJ_LIVE_ENABLED = True` in `config.py`; logged to `predictions/euroleague_m5inj_2026-27.csv`).

Judged by the standard promotion test (CLAUDE.md rule 4).

## What it is
M5 (`docs/models/m5.md`) projects minutes from recent box scores only, so it reacts to an absence after the first missed game. The BasketNews EuroLeague injury report (`injuries/euroleague_2026-27.csv`, `src/eurohoops/injuries.py`) can flag a player as `Out` before that.

**Change (one step).** Before M5's minutes projection is used, the projected minutes (shares) of every player whose status is `Out` are set to zero. The remaining shares of that team-side are renormalised to the same team total, using the rule `proj_avail` uses in `models/rotation.py` (`_drop_absent`), capped at 1. If the rule would remove every player of a team-side, the shares stay unchanged. `Uncertain` and all other statuses are unchanged.

**Unchanged.** The M5 choice (`proj_hc | core`, residual half-life 180 days, ridge 40, totals M1 + rest), the M3 player ratings, the margin distribution, the team residual fit, rest, and every fit. No parameter is re-tuned.

**Status at the cutoff.**
- A row's cutoff is its `predicted_at_utc`, the instant the forecast is stamped. The injury status is read before the forecast is made, so the status and the stamp refer to the same instant.
- The status comes from the latest snapshot stamped strictly before the cutoff, taken as a whole.
- That snapshot must be at most 6 hours older than the cutoff (`config.M5INJ_MAX_SNAPSHOT_AGE_HOURS`; exactly 6 h is accepted). Owner decision, 2026-11-03.
- If it is older, or there is none before the cutoff, no M5-INJ row is written for that run, and no fallback to M5 or to an older snapshot. The run logs `m5inj: latest injury snapshot <ts> is <h> h old (> 6 h); no M5-INJ rows written`. The daily job does not fail.
- A player is `Out` when he is listed `Out` in that snapshot (matched rows only).
- A player not listed in that snapshot has no status, so he is not `Out`, even if an older snapshot had him `Out`.
- Unmatched rows are never `Out`.
- If the feed stops, no status is found and the forecast equals M5's.

**Player matching.** Matching only sets the status on the right EuroLeague player. It is not part of the score.
- Roster source: the cached 2026 people listing, `data/raw/euroleague/people/E2026.json.gz` (the cache read by `models/roster.py`). Only rows with `type == "J"` count. Player id: `"P" + person.code`, the box-score player id. Club: `club.code`.
- Injury rows: the `team` column (source code, mapped from the BasketNews team name by `injuries.team_name_map`) and the `player` name (BasketNews, "First Last").
- Key: `eurohoops.entity.translit.latin_key` of the name. It folds accents and case, keeps A-Z, drops generational suffixes (JR, SR, II, III, IV) and sorts the tokens. "Isaia Cordinier" and "CORDINIER, ISAIA" give the same key.
- Aliases: `src/eurohoops/models/injury_aliases.csv` holds eight (club, BasketNews id) to roster name pairs. For these rows the alias name replaces the BasketNews name in the key. The club must still match.
  - ASV 6183 Patrick Mills to MILLS, PATTY
  - IST 40764 D. Karutasu to KARUTASU, DARIUS
  - IST 21746 P.J. Dozier to DOZIER, PJ
  - MAD 39042 Max Shulga to SHULGA, MAKSYM
  - OLY 35250 Antonios Karagiannidis to KARAGIANNIDIS, ANTONIS
  - PAN 19143 Juan Hernangomez to HERNANGOMEZ, JUANCHO
  - PAN 24143 Nikos Rogkavopoulos to ROGKAVOPOULOS, NIKOLAOS
  - PRS 17092 T.J. Warren to WARREN, TJ
- Rule: an injury row matches a roster player if the roster player has the same club code and the same key (the alias name's key where an alias applies).
- Ties: two or more roster players with the same club and key are unmatched (reason `ambiguous`).
- Misses: no roster player with that club and key is unmatched (reason `no_roster_match`). No fuzzy match is used.
- `bn_player_id` is used only for the alias lookup. No BasketNews-to-EuroLeague id crosswalk exists in the repository.

**Unmatched rows.** The 1,031 rows of `injuries/euroleague_2026-27.csv` (11 snapshots, 2026-10-07 to 2026-10-22) against the 2026 people listing (327 players, type `J`, 20 clubs): 886 matched (824 before the aliases, 62 from the eight aliases), 145 unmatched (22 distinct team and player pairs), 0 ambiguous. All 22 pairs are players with no entry under that name for that club.

**Effect on M5.** M5's projected minutes read only the box-score rows of earlier games. The people listing is read by ELOR, not by M5. So a player absent from the listing, but with recent box-score minutes, keeps M5's projected minutes. M5-INJ can only zero a player who is matched. Of the unmatched pairs, only Jabari Parker (PAR) and Iffe Lundberg (TEL) had EuroLeague minutes in 2025-26. Both are `Out` in every snapshot, so M5's two-missed-games rule already removes them.

**Logging.**
- File: `predictions/euroleague_m5inj_2026-27.csv` (the M1/M5 column shape, `model = m5inj`).
- Written by `eurohoops predict` only when `M5INJ_LIVE_ENABLED` is True and M5's validation check has passed (the M5 report). Same upcoming-game rule as M5 (`predict.upcoming_games`).
- Version: `tagged_version("m5inj", <M5 version> + the rule's name)`. The rule's name is `out-v2-max-age-6h` from 2026-11-03 (was `out-v1`, no maximum age). The `out-v1` rows stay in the log (append-only).
- Pass bar: unchanged. The standard promotion test (CLAUDE.md rule 4) on the games both logs share (M5-INJ vs M5), with no re-tuning.
- The logged row keeps only the forecast. The matched status is recomputed from `injuries/` at the row's `predicted_at_utc` when needed.
- The daily job uses the committed `injuries/` log, which may be some hours behind the latest snapshot.

## Results
Matching counts by BasketNews status (1,031 rows, 11 snapshots):

| Status | Matched rows | Unmatched rows |
|---|---|---|
| Out | 280 | 119 |
| Uncertain | 510 | 21 |
| Expected | 48 | 1 |
| Game-time | 12 | 4 |
| Ready | 30 | 0 |
| Doubtful | 6 | 0 |

Latest snapshot (2026-10-22 11:00Z): 86 of 102 rows match and 16 do not, 13 of them `Out` (of 43 `Out` rows).

No scored results yet.

## Feed audit (2026-11-03)
Checked `injuries/euroleague_2026-27.csv` (25 snapshots, 2,451 rows, 2026-10-07 to 2026-11-03 11:00Z). Read-only; no code or log changed.

**Cadence.**
- Snapshots on 18 of 28 days. No snapshot on 10-08..10-13, 10-19, or 10-30..11-01.
- Longest gap 176 h (10-07 09:30Z to 10-14 17:55Z). Other gaps over 48 h: 50 h (10-18 to 10-20) and 88 h (10-29 to 11-02).
- Rows per snapshot: min 84 (10-16), median 100, max 110. Every snapshot lists all 20 clubs.
- Page update to snapshot lag: median 2.1 h, max 30 h (the 10-25 snapshot).

**Two-week clock.** Never met. The longest run of consecutive days with a snapshot is 10 (10-20 to 10-29). If snapshots run daily from 11-02, the first full 14-day run is 11-02 to 11-15.

**Matching** (`availability.match_injuries`, rule unchanged):
- Up to 10-22: 886 matched, 145 unmatched of 1,031. Reproduces the numbers above.
- All snapshots: 2,045 matched, 406 unmatched of 2,451 (16.6%), 0 ambiguous. After 10-22 the unmatched share is 18.4% (261 of 1,420).
- Latest snapshot (11-03 11:00Z): 92 of 110 match. 11 of its 30 `Out` rows do not.
- New unmatched pairs since 10-22 (7): ASV Lorenz Sanz, OLY John Konchar, PAM Nate Reuvers, PAR Antonio Reeves, PAR Robert Franks, ULK Dwight Powell, ZAL Keenan Evans. Reuvers (PAM) is listed `Out` in some rows.

**Live forecasts** (`predictions/euroleague_m5inj_2026-27.csv`).
- All 23 rows have a snapshot stamped before their cutoff. Age: median 4.7 h, max 5.3 h. None is older than 48 h.
- Every M5 row from 10-23 on (20 games) has an M5-INJ row. The three M5-INJ rows for E2026_68 to E2026_70 are stamped 10-23, while their M5 rows are from 10-20.

**Verdict.** The two-week clock is not met (earliest 2026-11-15, if daily snapshots hold). The gaps are a risk for the live test: the rule uses the latest snapshot before the cutoff with no maximum age, so a status could come from a snapshot days old. No logged forecast has done so yet, since the last forecast (10-28) came before the 10-30 gap.

## Files
- Code: `src/eurohoops/injuries.py`, `src/eurohoops/models/injury_aliases.csv`, `src/eurohoops/models/rotation.py` (`_drop_absent`), `src/eurohoops/eval/m5_backtest.py`, `src/eurohoops/entity/translit.py` (`latin_key`), `src/eurohoops/config.py` (`M5INJ_LIVE_ENABLED`, `m5inj_prediction_log`).
- Data: `injuries/euroleague_2026-27.csv`, `data/raw/euroleague/people/E2026.json.gz`.
- Log: `predictions/euroleague_m5inj_2026-27.csv`.
- Tests: `tests/test_m5inj.py`.
