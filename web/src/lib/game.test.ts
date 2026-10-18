// Unit tests for the game page helpers: the box score per team, the clock and the phase labels.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { clockText, gameBox, lineStats, phaseLabel, periodName, type LogEntry } from "./game.ts";

const FIELDS = [
  "game_id", "team", "starter", "sec", "pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
  "oreb", "dreb", "ast", "stl", "tov", "blk", "blka", "pf", "fd", "pir", "pm",
];

// game_id, team, starter, sec, pts, fg2m, fg2a, fg3m, fg3a, ftm, fta, oreb, dreb, ast, stl, tov, blk, blka, pf, fd, pir, pm
const line = (team: string, starter: number, sec: number, pts: number, pm: number, extra: Partial<Record<string, number>> = {}) => {
  const v: Record<string, number> = { sec, pts, pm, ...extra };
  return ["G1", team, starter, sec, pts, v.fg2m ?? 0, v.fg2a ?? 0, v.fg3m ?? 0, v.fg3a ?? 0, v.ftm ?? 0, v.fta ?? 0, v.oreb ?? 0, v.dreb ?? 0, v.ast ?? 0, v.stl ?? 0, v.tov ?? 0, v.blk ?? 0, 0, v.pf ?? 0, 0, 0, pm];
};

const people = {
  p1: { name: "Ann Guard", slug: "ann-guard" },
  p2: { name: "Bo Forward", slug: "bo-forward" },
  p3: { name: "Cy Centre", slug: "cy-centre" },
  p4: { name: "Di Bench", slug: "di-bench" },
  p5: { name: "Ed Other", slug: "ed-other" },
};

test("a line reads the box columns by their field names", () => {
  const s = lineStats(FIELDS, line("PAO", 1, 600, 10, -3, { fg2m: 3, fg2a: 5, fg3m: 1, fg3a: 2, ftm: 1, fta: 2, oreb: 1, dreb: 4, pf: 2 }));
  assert.deepEqual(s.fg, [4, 7]);
  assert.deepEqual(s.tp, [1, 2]);
  assert.deepEqual(s.ft, [1, 2]);
  assert.equal(s.reb, 5);
  assert.equal(s.pm, -3);
  assert.equal(s.pf, 2);
});

test("a team box lists its players starters first, leaves out DNPs and sums every line", () => {
  const entries: LogEntry[] = [
    { id: "p4", line: line("PAO", 0, 300, 6, 2, { fg2m: 3, fg2a: 4 }) },
    { id: "p1", line: line("PAO", 1, 1200, 20, 5, { fg2m: 6, fg2a: 9, fg3m: 2, fg3a: 4, ast: 7 }) },
    { id: "p2", line: line("PAO", 1, 900, 12, -1, { dreb: 6, oreb: 1 }) },
    { id: "p3", line: line("PAO", 0, 0, 0, 0) },
    { id: "p5", line: line("OLY", 1, 1500, 30, 9) },
  ];
  const { players, totals } = gameBox(FIELDS, entries, "PAO", people);
  assert.deepEqual(players.map((p) => p.slug), ["ann-guard", "bo-forward", "di-bench"]);
  assert.equal(players[0].starter, true);
  assert.equal(players[2].starter, false);
  assert.equal(totals.pts, 38);
  assert.equal(totals.sec, 1200 + 900 + 300);
  assert.deepEqual(totals.fg, [11, 17]);
  assert.equal(totals.ast, 7);
  assert.equal(totals.reb, 7);
  assert.equal(totals.pm, 5 - 1 + 2);
});

test("an unknown player id falls back to the id and an empty slug", () => {
  const { players } = gameBox(FIELDS, [{ id: "zz", line: line("PAO", 0, 60, 2, 0) }], "PAO", people);
  assert.equal(players[0].name, "zz");
  assert.equal(players[0].slug, "");
});

test("clock labels show the period and time left, overtimes counted from one", () => {
  assert.equal(clockText(2, 271), "Q2 04:31");
  assert.equal(clockText(4, 0), "Q4 00:00");
  assert.equal(clockText(5, 299), "OT1 04:59");
  assert.equal(clockText(6, null), "OT2 --:--");
  assert.equal(periodName(1), "Q1");
  assert.equal(periodName(7), "OT3");
});

test("phase codes read as labels", () => {
  assert.equal(phaseLabel("RS", 3), "Regular season, round 3");
  assert.equal(phaseLabel("PO", 1), "Playoffs");
  assert.equal(phaseLabel("FF", 0), "Final Four");
  assert.equal(phaseLabel("XX", 0), "XX");
});
