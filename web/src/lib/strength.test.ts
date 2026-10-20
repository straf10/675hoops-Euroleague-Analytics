import { test } from "node:test";
import assert from "node:assert/strict";
import { days, elo, hasSchedule, sosOf, winPct, type Strength } from "./strength.ts";

const none = { games: 0, reason: "no games left to play" };
const full: Strength = {
  played: { games: 5, home: 3, away: 2, mean_opponent_elo: 1523.7, mean_opponent_elo_adjusted: 1505.7, average_team_win_pct: 0.5014, rest_days: 5.2, opponent_rest_days: 4.9, reason: null },
  remaining: none,
  next5: none,
};

test("the schedule tab shows when the team has played or has games left", () => {
  assert.equal(hasSchedule(full), true);
  assert.equal(hasSchedule({ ...full, played: { games: 0, reason: "x" }, remaining: { games: 2, home: 1, away: 1 } }), true);
  assert.equal(hasSchedule({ ...full, played: { games: 0, reason: "x" } }), false);
  assert.equal(hasSchedule(null), false);
  assert.equal(hasSchedule(undefined), false);
});

test("the average team's win share is a whole percentage", () => {
  assert.equal(winPct(0.4612), "46%");
  assert.equal(winPct(0.5), "50%");
  assert.equal(winPct(0.5014), "50%");
});

test("Elo has one decimal and a thousands separator; days have one decimal", () => {
  assert.equal(elo(1506.8258), "1,506.8");
  assert.equal(elo(1490), "1,490.0");
  assert.equal(days(4.966), "5.0");
  assert.equal(days(5.1875), "5.2");
});


test("the Teams index SoS figures are the team page's venue-adjusted Elo, NaN (a dash) with no games", () => {
  const left = sosOf(full);
  assert.equal(left.played, 1505.7);
  assert.ok(Number.isNaN(left.ahead));
  const done = sosOf({ ...full, remaining: { games: 0, reason: "no games left to play" } });
  assert.equal(done.played, 1505.7);
  assert.ok(Number.isNaN(done.ahead));
});
