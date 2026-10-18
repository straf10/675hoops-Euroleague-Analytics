import { test } from "node:test";
import assert from "node:assert/strict";
import { clubShotsOf, DEEP_MIN_M, RIM_MAX_M, sideDots, zoneOf, zoneRowsHtml, zoneTotals, type RawShots } from "./zones.ts";

// Court centimetres: x sideways from the centre, y in front of the basket.
test("the rim, the paint and the mid-range", () => {
  assert.equal(zoneOf(0, 50), "rim");
  assert.equal(zoneOf(0, 150), "rim", "1.5 m is still the rim");
  assert.equal(zoneOf(0, 151), "paint");
  assert.equal(zoneOf(245, 580), "paint", "the paint's far edge is the free-throw line");
  assert.equal(zoneOf(250, 580), "mid", "just outside the paint's width");
  assert.equal(zoneOf(0, 600), "mid", "6 m out, the 2-point area");
});

test("threes: corners, above the break and deep", () => {
  assert.equal(zoneOf(690, 100), "corner3");
  assert.equal(zoneOf(-690, 0), "corner3", "the left corner");
  assert.equal(zoneOf(690, 200), "above3", "past the corner's straight part, on the arc");
  assert.equal(zoneOf(0, 700), "above3", "7 m out");
  assert.equal(zoneOf(0, 799), "above3", "just under the deep cut-off");
  assert.equal(zoneOf(0, 800), "deep3", "8 m is deep");
  assert.equal(zoneOf(0, 900), "deep3");
});

test("the cut-offs are the named constants", () => {
  assert.equal(RIM_MAX_M, 1.5);
  assert.equal(DEEP_MIN_M, 8);
});

// Two clubs, four attempts. bits: made = bit 0, three = bit 1.
const raw: RawShots = {
  teams: ["AAA", "BBB"],
  x: [0, 0, 690, 0],
  y: [50, 300, 100, 900],
  flags: [1, 0, 3, 2], // made rim; missed paint; made corner three; missed deep three
  team: [0, 0, 1, 1],
  opp: [1, 1, 0, 0],
  bits: { made: 0, three: 1 },
};

test("a club's taken and allowed shots, and the league's totals", () => {
  const f = clubShotsOf(raw, "AAA", 2024);
  assert.deepEqual(f.taken, [0, 50, 1, 0, 0, 300, 0, 0]);
  assert.deepEqual(f.allowed, [690, 100, 1, 1, 0, 900, 0, 1]);
  assert.deepEqual(f.league.rim, [1, 1, 2]);
  assert.deepEqual(f.league.corner3, [1, 1, 3]);
  assert.deepEqual(f.league.deep3, [1, 0, 0]);
  assert.equal(clubShotsOf(raw, "NOPE", 2024).taken.length, 0);
});

test("zone totals count attempts, makes and points", () => {
  const t = zoneTotals([0, 50, 1, 0, 0, 300, 0, 0]);
  assert.deepEqual(t.rim, [1, 1, 2]);
  assert.deepEqual(t.paint, [1, 0, 0]);
});

test("picked zones filter the dots; no pick keeps all", () => {
  const f = clubShotsOf(raw, "AAA", 2024);
  assert.equal(sideDots(f, "taken", new Set()).length, 8);
  assert.deepEqual(sideDots(f, "taken", new Set(["paint"])), [0, 300, 0, 0]);
  assert.deepEqual(sideDots(f, "allowed", new Set(["corner3", "deep3"])), [690, 100, 1, 1, 0, 900, 0, 1]);
});

test("the zone table: a row per zone, unpicked rows dimmed, FG% against the league", () => {
  const f = clubShotsOf(raw, "AAA", 2024);
  const html = zoneRowsHtml(f, "taken", new Set(["rim"]));
  assert.equal(html.split("<tr ").length - 1, 6);
  assert.match(html, /<tr data-zone="rim"><th scope="row">At the rim<\/th><td class="num">1<\/td>/);
  assert.match(html, /<tr data-zone="paint" class="off">/);
  // Rim: 100% against the league's 100% in the same zone, so no sign and a zero difference.
  assert.match(html, /<td class="num ">0\.0<\/td><\/tr>/);
});
