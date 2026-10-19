// Unit tests for the previous-round margin check: predicted vs final margin, the off-by gap and
// the round's average miss. Run with `node --test "src/lib/**/*.test.ts"` from web/.

import { test } from "node:test";
import assert from "node:assert/strict";
import { averageMiss, marginCheck, marginText, type MatchdayGame } from "./matchday.ts";

const game = (over: Partial<MatchdayGame> = {}): MatchdayGame => ({
  game_id: "g1",
  tipoff_utc: "2026-10-15T17:45:00Z",
  tipoff_time_confirmed: true,
  home: { code: "PAN", name: "Panathinaikos" },
  away: { code: "OLY", name: "Olympiacos" },
  p_home: 0.6,
  played: true,
  home_score: 80,
  away_score: 71,
  hit: true,
  ...over,
});

test("off by is the gap between the rounded predicted and the final home margin", () => {
  // Predicted home by 4 (4.4 rounds to 4), final home by 9: off by 5.
  assert.deepEqual(marginCheck(game(), 4.4), { predicted: 4, actual: 9, off: 5 });
  // Predicted away by 3, final home by 9: off by 12.
  assert.deepEqual(marginCheck(game(), -2.6), { predicted: -3, actual: 9, off: 12 });
});

test("no check without a final score or a logged margin", () => {
  assert.equal(marginCheck(game({ played: false, home_score: null, away_score: null }), 4), null);
  assert.equal(marginCheck(game({ home_score: null }), 4), null);
  assert.equal(marginCheck(game(), undefined), null);
  assert.equal(marginCheck(game(), null), null);
});

test("a predicted margin that rounds to zero is an even call, never -0", () => {
  assert.deepEqual(marginCheck(game({ home_score: 70, away_score: 70 }), 0.3), {
    predicted: 0,
    actual: 0,
    off: 0,
  });
  const negative = marginCheck(game(), -0.2);
  assert.equal(negative?.predicted, 0);
  assert.equal(Object.is(negative?.predicted, -0), false);
});

test("the round's average miss is the mean over the games that have a check", () => {
  const checks = [
    marginCheck(game(), 4), // off by 5
    null, // unplayed or unforecast: left out
    marginCheck(game(), -3), // predicted away by 3, final home by 9: off by 12
    marginCheck(game({ home_score: 75, away_score: 73 }), 2), // predicted 2, final 2: off by 0
  ];
  assert.equal(averageMiss(checks), (5 + 12 + 0) / 3);
  assert.equal(averageMiss([null, null]), null);
  assert.equal(averageMiss([]), null);
});

test("the margin line names the predicted and the winning side", () => {
  const g = game();
  assert.equal(marginText(g, marginCheck(g, 4.4)!), "Predicted PAN by 4 · Final PAN by 9 · off by 5");
  assert.equal(marginText(g, marginCheck(g, -2.6)!), "Predicted OLY by 3 · Final PAN by 9 · off by 12");
  const away = game({ home_score: 66, away_score: 70 });
  assert.equal(marginText(away, marginCheck(away, 0.2)!), "Predicted even · Final OLY by 4 · off by 4");
});
