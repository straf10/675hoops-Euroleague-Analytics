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

## Player status at the cutoff
- A player's status is the status in the **latest snapshot before the cutoff in which he is listed**.
- Within that snapshot, if the player has several listed rows, he is `Out` when any of them says `Out`.
- A player not listed in any snapshot before the cutoff has no status (no effect).
- Disclosed risk: a player who recovers and is dropped from the list keeps his last listed status.
  The report counts how often that happens once the feed has history; it is not corrected in v1.

## Player matching rule (declared before any scoring)
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
- **Rule:** an injury row matches a roster player iff the roster player has the **same club code**
  and the **same key**. The club must match, so a name shared by two clubs is never confused.
- **Ties:** two or more roster players with the same club and key: **unmatched** (reason
  `ambiguous`). Nothing is picked.
- **Misses:** no roster player with that club and key: **unmatched** (reason `no_roster_match`).
  Nothing is guessed, and no fuzzy match is used.
- **`bn_player_id` is recorded but not used.** No BasketNews-to-EuroLeague id crosswalk exists in
  the repository, so the id cannot be checked against anything.
- **Unmatched rows** have no effect on any forecast. They are counted and listed in this card below
  (section "Unmatched rows"), before any scoring.

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

## Unmatched rows
(Filled in after the matching rule was committed, from `injuries/euroleague_2026-27.csv` and the
2026 roster listing. Matching only; no score is computed.)
