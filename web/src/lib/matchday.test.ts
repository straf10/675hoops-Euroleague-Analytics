// Unit tests for the matchday state: live round, or the last and next round between rounds.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { matchdayState, scorecard, type MatchdayRound, type RoundWindow } from "./matchday.ts";

const at = (iso: string) => Date.parse(iso);
const windows: RoundWindow[] = [
  { round: 5, start_utc: "2026-10-13T17:45:00Z", end_utc: "2026-10-14T20:45:00Z" },
  { round: 6, start_utc: "2026-10-15T17:45:00Z", end_utc: "2026-10-16T19:30:00Z" },
  { round: 7, start_utc: "2026-10-21T16:00:00Z", end_utc: "2026-10-23T18:45:00Z" },
];

test("a round is live from its first tip-off until its last tip-off plus a game length", () => {
  assert.deepEqual(matchdayState(windows, at("2026-10-15T17:44:59Z")), {
    kind: "between",
    last: 5,
    next: 6,
  });
  assert.deepEqual(matchdayState(windows, at("2026-10-15T17:45:00Z")), { kind: "live", round: 6 });
  assert.deepEqual(matchdayState(windows, at("2026-10-16T19:29:59Z")), { kind: "live", round: 6 });
  assert.deepEqual(matchdayState(windows, at("2026-10-16T19:30:00Z")), {
    kind: "between",
    last: 6,
    next: 7,
  });
});

test("between rounds the last completed and the next round are shown", () => {
  // Athens day of 2026-10-19: Round 6 ended on the 16th, Round 7 tips off on the 21st.
  assert.deepEqual(matchdayState(windows, at("2026-10-19T08:00:00Z")), {
    kind: "between",
    last: 6,
    next: 7,
  });
});

test("before the first round there is no last round, and after the last none next", () => {
  assert.deepEqual(matchdayState(windows, at("2026-09-01T00:00:00Z")), {
    kind: "between",
    last: null,
    next: 5,
  });
  assert.deepEqual(matchdayState(windows, at("2027-05-01T00:00:00Z")), {
    kind: "between",
    last: 7,
    next: null,
  });
  assert.deepEqual(matchdayState([], at("2026-10-19T08:00:00Z")), {
    kind: "between",
    last: null,
    next: null,
  });
});

test("rounds are picked by number, not by the order they arrive in", () => {
  const shuffled = [windows[2], windows[0], windows[1]];
  assert.deepEqual(matchdayState(shuffled, at("2026-10-19T08:00:00Z")), {
    kind: "between",
    last: 6,
    next: 7,
  });
});

const game = (hit: boolean | null) => ({
  game_id: "g",
  tipoff_utc: "2026-10-15T17:45:00Z",
  tipoff_time_confirmed: true,
  home: { code: "A", name: "A" },
  away: { code: "B", name: "B" },
  p_home: 0.6,
  played: hit !== null,
  home_score: 80,
  away_score: 70,
  hit,
});

test("the scorecard counts picks right out of the scored games only", () => {
  const round: MatchdayRound = {
    round: 6,
    start_utc: windows[1].start_utc,
    end_utc: windows[1].end_utc,
    games: [game(true), game(false), game(true), game(null), game(null)],
  };
  assert.deepEqual(scorecard(round), { right: 2, scored: 3 });
});
