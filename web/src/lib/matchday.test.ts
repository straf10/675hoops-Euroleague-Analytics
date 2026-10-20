// Unit tests for the matchday plan (which rounds the home page shows) and the round scorecard.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { matchdayPlan, scorecard, type MatchdayGame, type MatchdayRound } from "./matchday.ts";

const game = (over: Partial<MatchdayGame> = {}): MatchdayGame => ({
  game_id: "g",
  tipoff_utc: "2026-10-15T17:45:00Z",
  tipoff_time_confirmed: true,
  home: { code: "A", name: "A" },
  away: { code: "B", name: "B" },
  p_home: 0.6,
  played: false,
  home_score: null,
  away_score: null,
  hit: null,
  ...over,
});
const played = (hit: boolean | null = true): MatchdayGame =>
  game({ played: true, home_score: 80, away_score: 70, hit });

const round = (n: number, games: MatchdayGame[]): MatchdayRound => ({
  round: n,
  start_utc: "2026-10-15T17:45:00Z",
  end_utc: "2026-10-16T19:30:00Z",
  games,
});
const finished = (n: number) => round(n, [played(), played(false)]);
const open = (n: number) => round(n, [played(), game()]);
const future = (n: number) => round(n, [game(), game()]);

test("one open round is the only block shown, with no recap or next round", () => {
  const rounds = [finished(8), open(9), future(10)];
  const plan = matchdayPlan(rounds, [9]);
  assert.deepEqual(
    plan.open.map((r) => r.round),
    [9],
  );
  assert.equal(plan.recap, null);
  assert.equal(plan.next, null);
});

test("a double week shows both open rounds, earliest first, whatever the input order", () => {
  const rounds = [future(11), open(10), open(9), finished(8)];
  const plan = matchdayPlan(rounds, [10, 9]);
  assert.deepEqual(
    plan.open.map((r) => r.round),
    [9, 10],
  );
  assert.equal(plan.recap, null);
});

test("with no round open, the latest finished round is the recap and the next unstarted round is next", () => {
  const rounds = [finished(7), finished(8), future(9), future(10)];
  const plan = matchdayPlan(rounds, []);
  assert.deepEqual(plan.open, []);
  assert.equal(plan.recap?.round, 8);
  assert.equal(plan.next?.round, 9);
});

test("a finished previous round is dropped once the next round is open", () => {
  const rounds = [finished(8), finished(9), open(10), future(11)];
  const plan = matchdayPlan(rounds, [10]);
  assert.deepEqual(
    plan.open.map((r) => r.round),
    [10],
  );
  assert.equal(plan.recap, null, "round 9's recap is removed while round 10 is open");
});

test("before the first round there is no recap, and the first round is next", () => {
  const plan = matchdayPlan([future(1), future(2)], []);
  assert.equal(plan.recap, null);
  assert.equal(plan.next?.round, 1);
});

test("after the last round there is a recap and no next round", () => {
  const plan = matchdayPlan([finished(1), finished(2)], []);
  assert.equal(plan.recap?.round, 2);
  assert.equal(plan.next, null);
});

test("no rounds at all gives an empty plan", () => {
  assert.deepEqual(matchdayPlan([], []), { open: [], recap: null, next: null });
});

test("an open number with no matching round is ignored", () => {
  const plan = matchdayPlan([finished(5)], [7]);
  assert.deepEqual(plan.open, []);
  assert.equal(plan.recap?.round, 5);
});

test("the scorecard counts picks right out of the scored games only", () => {
  const r: MatchdayRound = round(6, [
    played(true),
    played(false),
    played(true),
    game({ played: true, hit: null }),
    game(),
  ]);
  assert.deepEqual(scorecard(r), { right: 2, scored: 3 });
});
