import { test } from "node:test";
import assert from "node:assert/strict";
import { pct, pctPair } from "./format.ts";

test("a win chance rounds to whole percents, capped at <1% and >99%", () => {
  assert.equal(pct(0.5), "50%");
  assert.equal(pct(0), "0%");
  assert.equal(pct(1), "100%");
  assert.equal(pct(0.9962), ">99%");
  assert.equal(pct(0.995), ">99%");
  assert.equal(pct(0.9949), "99%");
  assert.equal(pct(0.0038), "<1%");
  assert.equal(pct(0.005), "1%");
});

test("a pair totals 100% after rounding", () => {
  assert.deepEqual(pctPair(0.625), ["63%", "37%"]);
  assert.deepEqual(pctPair(0.5), ["50%", "50%"]);
  assert.deepEqual(pctPair(0.9962), [">99%", "<1%"]);
  assert.deepEqual(pctPair(0.0038), ["<1%", ">99%"]);
  assert.deepEqual(pctPair(1), ["100%", "0%"]);
});
