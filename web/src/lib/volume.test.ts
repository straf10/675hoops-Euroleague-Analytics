// Unit tests for the home page's rounded headline numbers (always rounded down).
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { headlineNumbers, roundedActions, roundedGames } from "./volume.ts";

test("games round down to the nearest hundred, with a plus", () => {
  assert.equal(roundedGames(5100), "5,100+");
  assert.equal(roundedGames(5199), "5,100+");
  assert.equal(roundedGames(99), "0+");
});

test("actions round down to the nearest tenth of a million, with M plus", () => {
  assert.equal(roundedActions(2_620_369), "2.6M+");
  assert.equal(roundedActions(2_699_999), "2.6M+");
  assert.equal(roundedActions(2_700_000), "2.7M+");
});

test("the headline line is seasons, games and actions, EuroLeague only", () => {
  assert.deepEqual(headlineNumbers({ games: 5100, seasons: 20, actions: 2_620_369 }), {
    seasons: "20",
    games: "5,100+",
    actions: "2.6M+",
  });
  assert.equal(headlineNumbers({ games: 1, seasons: 1 }).actions, null);
});
