import assert from "node:assert/strict";
import { test } from "node:test";

import { lines, minimumNote, PAIR_SIZE, range, sortLines, UNIT_SIZE, type LineupRow } from "./lineups.ts";

const pair: LineupRow = ["P1", "P2", 120.5, 210, 250, 230, 8.6, 13.1];
const unit: LineupRow = ["A", "B", "C", "D", "E", 55, 90, 80, 95, -16.7, 21.4];

test("pair rows read as ids then six numbers", () => {
  const [line] = lines([pair], PAIR_SIZE);
  assert.deepEqual(line.ids, ["P1", "P2"]);
  assert.equal(line.minutes, 120.5);
  assert.equal(line.poss, 210);
  assert.equal(line.pf - line.pa, 20);
  assert.equal(line.net, 8.6);
  assert.equal(line.ci, 13.1);
});

test("unit rows read five ids", () => {
  const [line] = lines([unit], UNIT_SIZE);
  assert.deepEqual(line.ids, ["A", "B", "C", "D", "E"]);
  assert.equal(line.minutes, 55);
  assert.equal(line.net, -16.7);
});

test("the range is net plus and minus ci", () => {
  const [line] = lines([pair], PAIR_SIZE);
  const { low, high } = range(line);
  assert.equal(Number(low.toFixed(1)), -4.5);
  assert.equal(Number(high.toFixed(1)), 21.7);
});

test("sort by net, largest first; minutes break ties", () => {
  const list = lines(
    [
      ["P1", "P2", 100, 100, 0, 0, 5, 9],
      ["P3", "P4", 150, 120, 0, 0, 5, 9],
      ["P5", "P6", 90, 300, 0, 0, 12, 4],
    ],
    PAIR_SIZE
  );
  assert.deepEqual(
    sortLines(list, "net").map((l) => l.ids[0]),
    ["P5", "P3", "P1"]
  );
});

test("sort by minutes, largest first; net breaks ties", () => {
  const list = lines(
    [
      ["A", "B", 80, 0, 0, 0, 1, 1],
      ["C", "D", 120, 0, 0, 0, -2, 1],
      ["E", "F", 120, 0, 0, 0, 3, 1],
    ],
    PAIR_SIZE
  );
  assert.deepEqual(
    sortLines(list, "minutes").map((l) => l.ids[0]),
    ["E", "C", "A"]
  );
});

test("sorting does not change the input", () => {
  const list = lines([pair, ["X", "Y", 300, 10, 0, 0, 0, 1]], PAIR_SIZE);
  const before = list.map((l) => l.ids[0]);
  sortLines(list, "net");
  assert.deepEqual(
    list.map((l) => l.ids[0]),
    before
  );
});

test("the table notes state the season's minimum minutes", () => {
  const minimums = { pair: 100, unit: 50 };
  assert.equal(minimumNote("duos", minimums), "Duos with at least 100 minutes on court together.");
  assert.equal(minimumNote("units", minimums), "Units with at least 50 minutes on court together.");
});
