import { test } from "node:test";
import assert from "node:assert/strict";
import { rate, seasonRange, share, signed, winPct } from "./coaches.ts";

test("per-game rates and shares print with their precision, dash without a value", () => {
  assert.equal(rate(1.0483), "1.05");
  assert.equal(rate(10.275, 1), "10.3");
  assert.equal(rate(null), "-");
  assert.equal(share(0.5395), "54%");
  assert.equal(share(0.4286), "43%");
  assert.equal(share(null), "-");
});

test("win percentage with one decimal, dash without games", () => {
  assert.equal(winPct({ games: 279, wins: 167 }), "59.9%");
  assert.equal(winPct({ games: 0, wins: 0 }), "-");
});

test("signed figures always print their sign", () => {
  assert.equal(signed(17.36), "+17.4");
  assert.equal(signed(-3), "-3.0");
  assert.equal(signed(0), "0.0");
  assert.equal(signed(-0.04), "0.0");
});

test("season range runs from the first to the last season", () => {
  assert.equal(seasonRange([2026, 2015, 2019]), "2015-16 to 2026-27");
  assert.equal(seasonRange([2021]), "2021-22");
  assert.equal(seasonRange([]), "-");
});
