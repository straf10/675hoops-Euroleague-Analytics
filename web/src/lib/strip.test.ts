// Unit tests for the strip plot layout: ticks, jitter and the Show top split.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { domainOf, isTop, niceTicks, stripLayout, valueY, STEP, STRIP_HEIGHT } from "./strip.ts";

// Games played is a whole number, so many players tie on one value. A tie stays on its exact row,
// centred on the axis, and its spacing compresses so no dot is further than maxHalfWidth from it.
const tieOf = (n: number, value = 34) =>
  Array.from({ length: n }, (_, i) => ({ key: `p${String(i).padStart(2, "0")}`, value, top: false }));

test("a 40-player tie never spreads beyond maxHalfWidth from the axis", () => {
  for (const maxHalfWidth of [18, 60, 150]) {
    const { dots } = stripLayout(tieOf(40), 0, 40, STRIP_HEIGHT, maxHalfWidth);
    assert.ok(
      dots.every((d) => Math.abs(d.dx) <= maxHalfWidth + 1e-9),
      `max |dx| ${Math.max(...dots.map((d) => Math.abs(d.dx)))} exceeds ${maxHalfWidth}`,
    );
  }
});

test("a tie keeps the exact y of its value, on one row", () => {
  const items = [...tieOf(40), { key: "lo", value: 10, top: false }];
  const { dots } = stripLayout(items, 0, 40, STRIP_HEIGHT, 60);
  for (const d of dots) {
    const value = d.key === "lo" ? 10 : 34;
    assert.ok(Math.abs(d.y - valueY(value, 0, 40)) <= 0.005, `${d.key} at ${d.y}`);
  }
  assert.equal(new Set(dots.filter((d) => d.key !== "lo").map((d) => d.y)).size, 1);
});

test("a tie is centred and spaced at STEP when it fits, and compressed when it does not", () => {
  const fits = stripLayout(tieOf(3), 0, 40, STRIP_HEIGHT, 60).dots.map((d) => d.dx);
  assert.deepEqual(fits, [0, STEP, -STEP]);
  const tight = stripLayout(tieOf(5), 0, 40, STRIP_HEIGHT, 6).dots.map((d) => d.dx);
  assert.ok(tight.every((dx) => Math.abs(dx) <= 6 + 1e-9), "five dots fit within ±6");
  assert.equal(Math.max(...tight), 6);
});

test("a small set without ties places dots exactly as the band rule always has", () => {
  // Three distinct values inside one 6 px band (y about 213 to 214): highest first, centre, right, left.
  const items = [
    { key: "z", value: 10.1, top: false },
    { key: "x", value: 10.14, top: false },
    { key: "y", value: 10.12, top: false },
  ];
  const { dots } = stripLayout(items, 0, 20, STRIP_HEIGHT, 5);
  assert.deepEqual(
    dots.map((d) => [d.key, d.dx]),
    [
      ["x", 0],
      ["y", STEP],
      ["z", -STEP],
    ],
  );
});

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
