// Unit tests for the win-probability line helpers (lib/wp.ts): the time axis, the geometry, the
// nearest point under a pointer, and the words of the swing list and control table.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  BP,
  controlValue,
  gameClock,
  gameEnd,
  geometry,
  linePath,
  lineSummary,
  nearestIndex,
  periodAt,
  percent,
  playLabel,
  points,
  swingGain,
  xAt,
  yAt,
  type WpGame,
  type WpPoint,
  type WpSwing,
} from "./wp.ts";

test("the time axis runs to the final buzzer, overtime adds five minutes each", () => {
  assert.equal(gameEnd(0), 2400);
  assert.equal(gameEnd(2), 2400 + 2 * 300);
});

test("periods and clocks, with overtime on its own five-minute clock", () => {
  assert.deepEqual(periodAt(0), { period: 1, left: 600 });
  assert.deepEqual(periodAt(630), { period: 2, left: 570 });
  assert.deepEqual(periodAt(2399), { period: 4, left: 1 });
  assert.deepEqual(periodAt(2400), { period: 5, left: 300 });
  assert.deepEqual(periodAt(2700), { period: 6, left: 300 });
  assert.deepEqual(periodAt(2810), { period: 6, left: 190 });
  assert.equal(gameClock(1000), "Q2 03:20");
  assert.equal(gameClock(2500), "OT1 03:20");
});

test("home is on top: 100% at the top edge, 0% at the bottom, 50% in the middle", () => {
  const g = geometry(0);
  assert.equal(yAt(g, BP), g.top);
  assert.equal(yAt(g, 0), g.height - g.bottom);
  assert.equal(yAt(g, BP / 2), (g.top + g.height - g.bottom) / 2);
  assert.equal(xAt(g, 0), g.left);
  assert.equal(xAt(g, g.end), g.width - g.right);
});

test("the path starts at tip-off and visits every point in order", () => {
  const g = geometry(0);
  const pts: WpPoint[] = [
    [0, 0, 0, 5000],
    [600, 20, 18, 7000],
    [2400, 70, 60, 10000],
  ];
  const d = linePath(g, pts);
  assert.ok(d.startsWith(`M${xAt(g, 0).toFixed(1)},${yAt(g, 5000).toFixed(1)}`));
  assert.equal(d.match(/L/g)?.length, 2);
});

test("the nearest point is the last one at or before the pointer, or the next if strictly nearer", () => {
  const pts: WpPoint[] = [
    [0, 0, 0, 5000],
    [60, 0, 2, 5800],
    [60, 2, 2, 6300],
    [120, 2, 4, 5200],
    [200, 2, 4, 5400],
  ];
  assert.equal(nearestIndex(pts, -5), 0);
  assert.equal(nearestIndex(pts, 0), 0);
  assert.equal(nearestIndex(pts, 60), 2, "the last point of a second");
  assert.equal(nearestIndex(pts, 85), 2, "closer to 60 than to 120");
  assert.equal(nearestIndex(pts, 100), 3, "closer to 120 than to 60");
  assert.equal(nearestIndex(pts, 500), 4);
  assert.equal(nearestIndex([], 10), -1);
});

test("percent and signed percentage points", () => {
  assert.equal(percent(5000), "50%");
  assert.equal(percent(9996), "100%");
  assert.equal(points(807), "+8.1 pp");
  assert.equal(points(-751), "−7.5 pp");
  assert.equal(points(0), "0.0 pp");
});

test("the scoring team's gain is positive for the team that scored", () => {
  const home: WpSwing = [600, 2, 600, 1, "3FGM", 19, 19, 699];
  const away: WpSwing = [600, 2, 600, 0, "3FGM", 16, 19, -699];
  assert.equal(swingGain(home), 699);
  assert.equal(swingGain(away), 699);
});

test("play labels cover the scoring codes and the old two-point codes", () => {
  assert.equal(playLabel("3FGM"), "Three-point make");
  assert.equal(playLabel("2FGM"), "Two-point make");
  assert.equal(playLabel("LAYUPMD"), "Two-point make");
  assert.equal(playLabel("DUNK"), "Two-point make");
  assert.equal(playLabel("FTM"), "Free throw");
  assert.equal(playLabel("XXX"), "Scoring play");
});

test("control parts: signed dominance, shares as percentages, the rest to two decimals", () => {
  assert.equal(controlValue("dominance", -0.3695), "−0.37");
  assert.equal(controlValue("dominance", 0.1), "+0.10");
  assert.equal(controlValue("control", 0.225), "23%");
  assert.equal(controlValue("comeback", 0.999), "100%");
  assert.equal(controlValue("drama", 1.2888), "1.29");
  assert.equal(controlValue("crunch", 0), "0.00");
});

test("the summary names the start and the winner", () => {
  const game: WpGame = {
    pre: 6267,
    ot: 0,
    line: [
      [0, 0, 0, 6267],
      [2400, 69, 88, 0],
    ],
    swings: [],
    control: { home: [0, 0, 0, 0, 0], away: [0, 0, 0, 0, 0] },
  };
  assert.equal(
    lineSummary("Olympiacos", "Panathinaikos", game),
    "Olympiacos win chance starts at 63% at tip-off. Panathinaikos won; the line ends at the result.",
  );
});
