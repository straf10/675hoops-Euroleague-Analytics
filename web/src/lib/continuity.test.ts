import { test } from "node:test";
import assert from "node:assert/strict";
import { minutesOf, percentOf, returningPercent, type Continuity } from "./continuity.ts";

const club: Continuity = {
  last_sec: 12000,
  returning_sec: 7450,
  share: 7450 / 12000,
  returning: [{ id: "P1", name: "Nando De Colo", sec: 1500 }],
  departures: [{ id: "P2", name: "Gone Player", sec: 900 }],
};

test("a share reads as a whole percentage", () => {
  assert.equal(percentOf(0.624), 62);
  assert.equal(percentOf(1), 100);
  assert.equal(percentOf(0), 0);
});

test("seconds read as whole minutes", () => {
  assert.equal(minutesOf(1500), 25);
  assert.equal(minutesOf(59), 1);
});

test("the headline figure is the club's rounded share, or nothing without a value", () => {
  assert.equal(returningPercent(club), 62);
  assert.equal(returningPercent(null), null);
});
