// Unit tests for the strip plot layout: ticks, jitter and the Show top split.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { domainOf, isTop, niceTicks, stripLayout, valueY, STEP, STRIP_HEIGHT } from "./strip.ts";

test("nice ticks use a 1, 2, 2.5, 5 or 10 step and cover the domain", () => {
  assert.deepEqual(niceTicks(0, 30), [0, 5, 10, 15, 20, 25, 30]);
  assert.deepEqual(niceTicks(0, 100), [0, 20, 40, 60, 80, 100]);
  const ticks = niceTicks(-3.2, 17.9);
  assert.ok(ticks.length >= 3 && ticks.length <= 8, `count ${ticks.length}`);
  assert.ok(ticks.every((v) => v >= -3.2 - 1e-9 && v <= 17.9 + 1e-9));
  const step = ticks[1] - ticks[0];
  assert.ok(ticks.every((v, i) => i === 0 || Math.abs(v - ticks[i - 1] - step) < 1e-9));
});

test("the domain pads 8% and keeps non-negative measures at zero", () => {
  assert.deepEqual(domainOf([], false), [0, 1]);
  const [lo, hi] = domainOf([10, 20], true);
  assert.ok(Math.abs(lo - 9.2) < 1e-9 && Math.abs(hi - 20.8) < 1e-9);
  assert.equal(domainOf([-0.5, 1], true)[0], 0);
  assert.ok(domainOf([-4, 2], false)[0] < -4);
});

test("the highest value sits at the top of the plot", () => {
  assert.equal(valueY(20, 0, 20), 0);
  assert.equal(valueY(0, 0, 20), STRIP_HEIGHT);
  assert.ok(valueY(15, 0, 20) < valueY(5, 0, 20));
});

test("jitter is deterministic and does not depend on input order", () => {
  const items = [
    { key: "b", value: 12, top: true },
    { key: "a", value: 12, top: false },
    { key: "c", value: 3, top: false },
    { key: "d", value: 12.01, top: true },
  ];
  const first = stripLayout(items, 0, 20);
  const again = stripLayout(items, 0, 20);
  const shuffled = stripLayout([...items].reverse(), 0, 20);
  assert.deepEqual(first, again);
  assert.deepEqual(first, shuffled);
});

test("dots in one 6 px band alternate out to the right and the left", () => {
  const same = [1, 2, 3, 4, 5].map((i) => ({ key: `p${i}`, value: 10, top: false }));
  const { dots } = stripLayout(same, 0, 20);
  assert.deepEqual(
    dots.map((d) => d.dx),
    [0, STEP, -STEP, 2 * STEP, -2 * STEP],
  );
  assert.ok(dots.every((d) => d.y === dots[0].y));
});

test("a dot far from its neighbours keeps the centre line", () => {
  const { dots } = stripLayout(
    [
      { key: "hi", value: 20, top: true },
      { key: "lo", value: 0, top: false },
    ],
    0,
    20,
  );
  assert.deepEqual(
    dots.map((d) => [d.key, d.dx]),
    [
      ["hi", 0],
      ["lo", 0],
    ],
  );
});

test("Show top marks the first N ranked items, and 0 marks all", () => {
  assert.deepEqual([0, 1, 2, 3, 4].map((i) => isTop(i, 3)), [true, true, true, false, false]);
  assert.ok([0, 50, 200].every((i) => isTop(i, 0)));
  const { dots } = stripLayout(
    [1, 2, 3].map((i) => ({ key: `p${i}`, value: 30 - i, top: isTop(i - 1, 2) })),
    0,
    30,
  );
  assert.deepEqual(
    dots.map((d) => d.top),
    [true, true, false],
  );
});
