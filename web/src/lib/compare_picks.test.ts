// Unit tests for Compare's player pick rules: a player is picked once, whatever his season.
// Run with `node --test "src/lib/**/*.test.ts"` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { addPlayer, uniquePlayers, unpickedNames, type PlayerPick } from "./compare_picks.ts";

test("uniquePlayers keeps the first pick of each player and drops the repeats", () => {
  const picks = [
    { slug: "a", season: 2022 },
    { slug: "b", season: 0 },
    { slug: "a", season: 2023 },
  ];
  assert.deepEqual(uniquePlayers(picks), [
    { slug: "a", season: 2022 },
    { slug: "b", season: 0 },
  ]);
});

test("addPlayer refuses a player already picked, in any season, and a full list", () => {
  const picks: PlayerPick[] = [{ slug: "a", season: 2022 }];
  assert.equal(addPlayer(picks, { slug: "a", season: 2023 }, 5), picks, "same player, other season: refused");
  assert.deepEqual(addPlayer(picks, { slug: "b", season: 2023 }, 5), [{ slug: "a", season: 2022 }, { slug: "b", season: 2023 }]);
  const full: PlayerPick[] = [1, 2, 3].map((i) => ({ slug: `p${i}`, season: 0 }));
  assert.equal(addPlayer(full, { slug: "p9", season: 0 }, 3), full, "a full list takes no more");
});

test("the player picker hides the players already compared", () => {
  const names: [string, string][] = [
    ["Sergio Llull (2007-16)", "sergio-llull"],
    ["Kyle Hines (2010-21)", "kyle-hines"],
    ["Mike James (2014-23)", "mike-james"],
  ];
  const picks: PlayerPick[] = [{ slug: "kyle-hines", season: 0 }];
  assert.deepEqual(unpickedNames(names, picks), ["Sergio Llull (2007-16)", "Mike James (2014-23)"]);
  assert.deepEqual(unpickedNames(names, []), names.map(([label]) => label));
});
