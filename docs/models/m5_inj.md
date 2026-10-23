# M5-INJ: M5 with the BasketNews "Out" status (EuroLeague, shadow)

**Status: draft, not committed by the owner.** Drafted 2026-10-22 (PLAN §8.1 backlog, IDEAS.md A1).
Nothing here is a promotion or a gate until the owner commits it. Logging stays off
(`M5INJ_LIVE_ENABLED = False`, config) until then, so the gate's evaluation games are the games
logged after the gate commit.

## Question
M5 (`docs/models/m5.md`) projects minutes from recent box scores only, so it reacts to an absence
after the first missed game. The BasketNews EuroLeague injury report (`injuries/euroleague_2026-27.csv`,
`src/eurohoops/injuries.py`) can flag a player as `Out` before that. Does M5 with the `Out` players'
minutes set to zero beat M5 on EuroLeague home-win log loss in live games?

## What changes, and what does not
- **Changed (one step):** before M5's minutes projection is used, the projected minutes (shares)
  of every player whose status is `Out` are set to zero, and the remaining shares of that
  team-side are renormalised to the same team total (the rule `proj_avail` uses in
  `models/rotation.py`, `_drop_absent`), capped at 1 as there.
- **Not changed:** the M5 choice (`proj_hc | core`, residual half-life 180 days, ridge 40, totals
  M1 + rest), the M3 player ratings, the margin distribution, the team residual fit, rest, and
  every fit. No parameter is re-tuned, and no model is re-fitted on the injury data.
- **Uncertain** and any other status: unchanged (declared, not tuned; v1).
- **Kept as M5's rule:** if the rule would remove every player of a team-side, the shares stay
  unchanged.

## Information cutoff (no lookahead)
A logged row's cutoff is its own `predicted_at_utc`, the instant the forecast is made and stamped
(before tip-off, `refuse_late`). A snapshot is used only if its `snapshot_utc` is **strictly
earlier** than that cutoff. Snapshots at or after the cutoff are ignored. The cutoff is taken before
the injury status is read, so the status and the stamp refer to the same instant.

## Player status at the cutoff (amended 2026-10-23, owner)
- The status is read from the **latest snapshot stamped strictly before the cutoff, taken as a whole**.
- A player is `Out` when he is listed `Out` in that snapshot (matched rows only).
- A player who is **not listed** in that snapshot has no status, so he is not Out, even if an older
  snapshot had him `Out`. An older `Out` never carries forward.
- Unmatched rows are never Out.

## Player matching rule (declared before any scoring; aliases confirmed by the owner 2026-10-23)
Matching is only for the status to reach the right EuroLeague player. It is not part of the score.

- **Roster source:** the cached EuroLeague people listing of the live season,
  `data/raw/euroleague/people/E2026.json.gz` (the same cache `models/roster.py` reads; never fetched
  here). Only rows with `type == "J"` (players) count. Player id: `"P" + person.code`, which is the
  box-score player id in the games marts (`ingest/bios.py`). Club: `club.code` (the source code).
- **Injury rows:** the `team` column (source code, mapped from the BasketNews team name by
  `injuries.team_name_map`) and the `player` name (BasketNews, "First Last").
- **Key:** `eurohoops.entity.translit.latin_key` of the name. It folds accents and case, keeps A-Z,
  drops generational suffixes (JR/SR/II/III/IV) and sorts the tokens, so "Isaia Cordinier" and
  "CORDINIER, ISAIA" give the same key, whatever the order of the name.
- **Aliases (owner-confirmed 2026-10-23, before any scoring):** `src/eurohoops/models/injury_aliases.csv`
  holds exactly these eight (club, BasketNews id) to roster name pairs, confirmed by the owner as the
  same players. For these rows the alias name replaces the BasketNews name in the key. The club must
  still match.
  - ASV 6183 Patrick Mills to MILLS, PATTY
  - IST 40764 D. Karutasu to KARUTASU, DARIUS
  - IST 21746 P.J. Dozier to DOZIER, PJ
  - MAD 39042 Max Shulga to SHULGA, MAKSYM
  - OLY 35250 Antonios Karagiannidis to KARAGIANNIDIS, ANTONIS
  - PAN 19143 Juan Hernangomez to HERNANGOMEZ, JUANCHO
  - PAN 24143 Nikos Rogkavopoulos to ROGKAVOPOULOS, NIKOLAOS
  - PRS 17092 T.J. Warren to WARREN, TJ

  No other alias. The owner confirmed that every other unmatched player is a different existing
  player (class A below), so none is aliased and all stay unmatched.
- **Rule:** an injury row matches a roster player iff the roster player has the **same club code**
  and the **same key** (the alias name's key where an alias applies).
- **Ties:** two or more roster players with the same club and key: **unmatched** (reason
  `ambiguous`). Nothing is picked.
- **Misses:** no roster player with that club and key: **unmatched** (reason `no_roster_match`).
  Nothing is guessed, and no other fuzzy match is used.
- **`bn_player_id` is used only for the alias lookup.** It is not checked against any roster id, since
  no BasketNews-to-EuroLeague id crosswalk exists in the repository.
- **Unmatched rows** have no effect on any forecast from the status path (see the M5 section below
  for what that means for M5's own projection).

## Logging (when switched on)
- File: `predictions/euroleague_m5inj_2026-27.csv` (the M1/M5 column shape, `model = m5inj`).
- Written by `eurohoops predict` only when `M5INJ_LIVE_ENABLED` is True, and only if M5's own
  validation gate passed (the M5 report). The same upcoming-game rule as M5 (`predict.upcoming_games`).
- Version: `tagged_version("m5inj", <M5 version> + the rule's name)`.
- Append-only, like every log. The logged row keeps only the forecast; the matched status is
  recomputed from `injuries/` at the row's `predicted_at_utc` when needed.

## Draft gate (IDEAS.md A1, unchanged)
- **Question:** does `M5-INJ` beat M5 on EuroLeague home-win log loss on live games?
- **Evaluation data:** EuroLeague 2026-27 games that both M5 and `M5-INJ` logged after the gate
  commit, through season end (about 250 games).
- **Primary metric:** mean per-game log-loss difference (`M5-INJ` − M5), paired bootstrap over
  games, 10,000 resamples, fixed seed.
- **Secondary metric:** the same on the subset where at least one player with a projected share
  ≥ 0.10 was marked `Out` (declared before the run; counts reported). The share is M5's projected
  share at the row's cutoff, recomputed from the frozen M5 inputs.
- **Pass rule:** 95% CI upper bound of the primary difference < +0.002 (non-inferiority) **and** a
  negative mean on the secondary subset. Report margin RMSE too.
- **Matching rule:** declared above; unmatched rows reported below.

## Risks (from IDEAS.md A1, plus this card)
- Snapshot timing: a status can change after the last snapshot before the cutoff.
- The feed is unofficial and may stop. Then the model has no status and equals M5.
- The daily job runs at 08:00 UTC from the committed `injuries/` log, which may be a few hours
  behind the latest snapshot. This is safe for lookahead but reduces the signal.
- Small affected subset: the secondary test has low power (see E1).
- The market already prices absences (dare-2015), so the gain against the benchmark may be zero.

## Unmatched rows (rerun 2026-10-23, after the aliases; matching only, no score computed)
Source: the 1,031 rows of `injuries/euroleague_2026-27.csv` (11 snapshots, 2026-10-07 to 2026-10-22)
against the 2026 people listing (327 players, type `J`, 20 clubs).

**Totals.** 886 rows matched (the 824 of the first run plus 62 from the eight aliases); **145 rows
unmatched**; 0 ambiguous. The 145 rows are **22 distinct (team, player) pairs**. In the latest snapshot
(2026-10-22 11:00Z), 86 of 102 rows match and 16 do not, 13 of them `Out` (of 43 `Out` rows).

| Status | Matched rows | Unmatched rows |
|---|---|---|
| Out | 280 | 119 |
| Uncertain | 510 | 21 |
| Expected | 48 | 1 |
| Game-time | 12 | 4 |
| Ready | 30 | 0 |
| Doubtful | 6 | 0 |

**The 22 unmatched pairs.** All are class A: no player of that name is in the 2026 people listing
for that club. Some have a same-surname entry for another first name or another club (for example
"SHULGA, MAKSYM", "LARKIN, SHANE"), which the owner confirmed are different players. None is aliased.
The owner's note said 21 class-A players. The list has 22 pairs; the extra one is George Papas (OLY,
Uncertain, 11 snapshots). Flagged for the owner; the rule is applied as listed here.

| Team | BasketNews name | BN id | Rows (snapshots) | Statuses seen |
|---|---|---|---|---|
| ASV | Juhann Begarin | 35892 | 10 (10) | Game-time, Uncertain |
| BES | Lonnie Walker IV | 22564 | 5 (5) | Expected, Uncertain |
| BES | Mady Sissoko | 39046 | 3 (3) | Out |
| DUB | Mouhammadou Jaiteh | 14688 | 11 (11) | Out |
| DUB | Tomislav Vuckovic | 40316 | 11 (11) | Out |
| HTA | Frederic Bourdillon | 24348 | 1 (1) | Out |
| HTA | Itay Segev | 12194 | 1 (1) | Out |
| HTA | Max Heidegger | 35310 | 1 (1) | Out |
| HTA | Tamir Blatt | 21168 | 4 (4) | Out |
| HTA | Yiftach Ziv | 35088 | 1 (1) | Out |
| IST | Burak Can Yildizli | 14714 | 1 (1) | Out |
| OLY | George Papas | 35869 | 11 (11) | Uncertain |
| PAR | Jabari Parker | 15928 | 11 (11) | Out |
| PAR | Mitar Bosnjakovic | 37625 | 11 (11) | Out |
| PRS | Nobel Boungou-Colo | 16649 | 11 (11) | Out |
| RED | Aleksej Nedeljkovic | 40277 | 11 (11) | Out |
| RED | Christian Koloko | 36365 | 4 (4) | Out |
| RED | Jovan Bikic | 39633 | 11 (11) | Out |
| RED | Ognjen Simjanovski | 40278 | 11 (11) | Out |
| RED | Vojin Medarevic | 39021 | 11 (11) | Out |
| TEL | Gabriel Lundberg | 24128 | 3 (3) | Out |
| TEL | Shane Hunter | 38648 | 1 (1) | Out |

## Does the people listing gate M5's minutes? (checked in code, 2026-10-23)
**No.** M5's projected minutes (`eval/m5_backtest.py` `_projected`, which calls `models/rotation.py`
and `models/minutes.py` `projected_shares`) read only the box-score `player_games` rows of earlier
games. The people listing (`models/roster.py`) is read by ELOR (`elor.py`, `live_elor.py`), not by
M5. So a player absent from the listing but with recent box-score minutes receives M5's projected
minutes, and M5-INJ can only zero him if he can be matched.

Consequence: the 22 unmatched pairs can change M5 forecasts through M5's box-score projection, and
M5-INJ does not zero them (no match, so no status). Whether any of the 22 has 2026 box-score minutes
was not checked (no score or box-score query was run for this card).

## Owner decisions (2026-10-23)
- Eight aliases confirmed as the same players (above); the other unmatched players are different
  players and stay unmatched.
- Stale status: the status is read from the latest snapshot as a whole; an older `Out` does not
  carry forward (above).

## Open items for the owner
1. The class-A count: 21 in the owner's note, 22 pairs in the list (George Papas, OLY, is the extra).
2. Coverage: the 22 unmatched pairs keep their projected minutes in M5-INJ, as the M5 section says.
3. Switch-on: logging stays off (`M5INJ_LIVE_ENABLED = False`); flipping it is the owner's step, done
   with the gate commit.
4. Feed freshness: the daily job uses the committed `injuries/` log, which may be hours old at 08:00 UTC.
