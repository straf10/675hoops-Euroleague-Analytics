// Unit tests for the league and position ranks on the player page (lib/league_rank.ts).
// Run with `node --test src/lib/` from web/.

import { test } from "node:test";
import assert from "node:assert/strict";
import { rankLeague, type LeagueLine } from "./league_rank.ts";

const higher = () => "higher" as const;
const lower = () => "lower" as const;

/** Six players: two guards (G), two forwards (F), one centre (C), and one with no listing. */
const lines = (): LeagueLine[] => [
  { id: "a", pos: "G", values: { pts: 20, reb: 2 } },
  { id: "b", pos: "G", values: { pts: 10, reb: 5 } },
  { id: "c", pos: "F", values: { pts: 15, reb: 9 } },
  { id: "d", pos: "F", values: { pts: 12, reb: 7 } },
  { id: "e", pos: "C", values: { pts: 8, reb: 11 } },
  { id: "f", pos: null, values: { pts: 30, reb: null } },
];

test("league rank counts every line, position rank only its own position", () => {
  const r = rankLeague(lines(), "b", ["pts"], higher);
  assert.equal(r.pts.mine, 10);
  // Points: 30, 20, 15, 12, 10, 8 -> b is 5th of 6 in the league.
  assert.equal(r.pts.league.rank, 5);
  assert.equal(r.pts.league.of, 6);
  assert.equal(r.pts.league.average, (20 + 10 + 15 + 12 + 8 + 30) / 6);
  // Guards only: a 20, b 10 -> b is 2nd of 2.
  assert.equal(r.pts.position?.name, "guards");
  assert.equal(r.pts.position?.rank, 2);
  assert.equal(r.pts.position?.of, 2);
  assert.equal(r.pts.position?.average, 15);
});

test("a centre gets the centre pool and the plural 'centres'", () => {
  const r = rankLeague(lines(), "e", ["reb"], higher);
  assert.equal(r.reb.position?.name, "centres");
  assert.equal(r.reb.position?.of, 1);
  assert.equal(r.reb.position?.rank, 1);
  assert.equal(r.reb.league.rank, 1);
});

test("forwards are ranked among forwards, with a lower-is-better key oriented the other way", () => {
  const r = rankLeague(lines(), "d", ["reb"], higher);
  // Rebounds among forwards: c 9, d 7 -> d is 2nd of 2.
  assert.equal(r.reb.position?.name, "forwards");
  assert.equal(r.reb.position?.rank, 2);
  const low = rankLeague(lines(), "d", ["reb"], lower);
  // Lower is better: d (7) ranks ahead of c (9) among forwards.
  assert.equal(low.reb.position?.rank, 1);
});

test("a player with no listed position has no position pool", () => {
  const r = rankLeague(lines(), "f", ["pts"], higher);
  assert.equal(r.pts.position, null);
  assert.equal(r.pts.league.rank, 1);
});

test("a player not counted in a key has a null rank in it, and the key's pool is still reported", () => {
  const r = rankLeague(lines(), "f", ["reb"], higher);
  assert.equal(r.reb.mine, null);
  assert.equal(r.reb.league.rank, null);
  assert.equal(r.reb.league.of, 5);
  assert.equal(r.reb.position, null);
});

test("ties share a rank in the league and in the position", () => {
  const tied: LeagueLine[] = [
    { id: "x", pos: "G", values: { pts: 10 } },
    { id: "y", pos: "G", values: { pts: 10 } },
    { id: "z", pos: "G", values: { pts: 4 } },
    { id: "w", pos: "C", values: { pts: 20 } },
  ];
  const r = rankLeague(tied, "y", ["pts"], higher);
  assert.equal(r.pts.league.rank, 2);
  assert.equal(r.pts.position?.rank, 1);
  assert.equal(r.pts.position?.of, 3);
});

test("an unknown id gives no ranks", () => {
  assert.deepEqual(rankLeague(lines(), "nobody", ["pts"], higher), {});
});
