// Unit tests for the pooled percentile and rank library, and the metric direction table.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { rankPool, type PoolRow } from "./percentile.ts";
import { betterOf } from "./better.ts";

const higher = () => "higher" as const;
const lower = () => "lower" as const;

test("ties share the middle of their span and the best rank", () => {
  const rows: PoolRow[] = [1, 2, 2, 4].map((v, i) => ({ id: `r${i}`, values: { x: v } }));
  const out = rankPool(rows, ["x"], higher);
  assert.deepEqual(out.get("r0")!.x, { pct: 0, rank: 4, of: 4 });
  assert.deepEqual(out.get("r1")!.x, { pct: 50, rank: 2, of: 4 });
  assert.deepEqual(out.get("r2")!.x, { pct: 50, rank: 2, of: 4 });
  assert.deepEqual(out.get("r3")!.x, { pct: 100, rank: 1, of: 4 });
});

test("competition ranking skips after a tie: 1, 2, 2, 4", () => {
  const rows: PoolRow[] = [9, 7, 7, 5].map((v, i) => ({ id: `r${i}`, values: { x: v } }));
  const ranks = rankPool(rows, ["x"], higher);
  assert.deepEqual(
    rows.map((r) => ranks.get(r.id)!.x!.rank),
    [1, 2, 2, 4],
  );
});

test("lower-is-better keys invert: the smallest value is 100 and rank 1", () => {
  const rows: PoolRow[] = [1, 2, 3].map((v, i) => ({ id: `r${i}`, values: { tov: v } }));
  const out = rankPool(rows, ["tov"], lower);
  assert.deepEqual(out.get("r0")!.tov, { pct: 100, rank: 1, of: 3 });
  assert.deepEqual(out.get("r1")!.tov, { pct: 50, rank: 2, of: 3 });
  assert.deepEqual(out.get("r2")!.tov, { pct: 0, rank: 3, of: 3 });
});

test("lower-is-better ties mirror the higher-is-better ties", () => {
  const values = [1, 2, 2, 4];
  const up = rankPool(values.map((v, i) => ({ id: `${i}`, values: { x: v } })), ["x"], higher);
  const down = rankPool(values.map((v, i) => ({ id: `${i}`, values: { x: v } })), ["x"], lower);
  for (let i = 0; i < values.length; i++) {
    assert.equal(down.get(`${i}`)!.x!.pct, 100 - up.get(`${i}`)!.x!.pct);
  }
  assert.deepEqual(down.get("0")!.x, { pct: 100, rank: 1, of: 4 });
  assert.deepEqual(down.get("3")!.x, { pct: 0, rank: 4, of: 4 });
});

test("null, undefined, NaN and infinite values leave the row out of that key only", () => {
  const rows: PoolRow[] = [
    { id: "a", values: { x: 10, y: 1 } },
    { id: "b", values: { x: null, y: 2 } },
    { id: "c", values: { y: 3 } },
    { id: "d", values: { x: NaN, y: 4 } },
    { id: "e", values: { x: 20, y: Infinity } },
    { id: "f", values: { x: 30, y: 5 } },
  ];
  const out = rankPool(rows, ["x", "y"], higher);
  assert.equal(out.get("b")!.x, null);
  assert.equal(out.get("c")!.x, null);
  assert.equal(out.get("d")!.x, null);
  assert.equal(out.get("e")!.y, null);
  assert.deepEqual(out.get("a")!.x, { pct: 0, rank: 3, of: 3 });
  assert.deepEqual(out.get("f")!.x, { pct: 100, rank: 1, of: 3 });
  assert.deepEqual(out.get("e")!.x, { pct: 50, rank: 2, of: 3 });
  assert.equal(out.get("f")!.y!.of, 5);
});

test("a lone value is 100 and rank 1 of 1", () => {
  const out = rankPool([{ id: "only", values: { x: 7 } }], ["x"], lower);
  assert.deepEqual(out.get("only")!.x, { pct: 100, rank: 1, of: 1 });
});

test("a group restricts the pool; rows outside it get null", () => {
  const rows: PoolRow[] = [
    { id: "g1", group: "G", values: { x: 10 } },
    { id: "g2", group: "G", values: { x: 20 } },
    { id: "f1", group: "F", values: { x: 99 } },
    { id: "none", values: { x: 1 } },
  ];
  const grouped = rankPool(rows, ["x"], higher, { group: "G" });
  assert.deepEqual(grouped.get("g2")!.x, { pct: 100, rank: 1, of: 2 });
  assert.deepEqual(grouped.get("g1")!.x, { pct: 0, rank: 2, of: 2 });
  assert.equal(grouped.get("f1")!.x, null);
  assert.equal(grouped.get("none")!.x, null);

  const nogroup = rankPool(rows, ["x"], higher, { group: null });
  assert.deepEqual(nogroup.get("none")!.x, { pct: 100, rank: 1, of: 1 });
  assert.equal(nogroup.get("g1")!.x, null);

  const everyone = rankPool(rows, ["x"], higher);
  assert.equal(everyone.get("f1")!.x!.of, 4);
});

test("an empty pool gives null everywhere, and no rows gives an empty map", () => {
  const blank = rankPool([{ id: "a", values: { x: null } }], ["x"], higher);
  assert.equal(blank.get("a")!.x, null);
  assert.equal(rankPool([], ["x"], higher).size, 0);
  assert.equal(rankPool([{ id: "a", values: { x: 1 } }], ["x"], higher, { group: "nope" }).get("a")!.x, null);
});

test("output is stable: same input, same map, input order, every key present", () => {
  const rows: PoolRow[] = [
    { id: "z", values: { b: 2, a: 1 } },
    { id: "y", values: { b: 2, a: 3 } },
    { id: "x", values: { a: 3 } },
  ];
  const first = rankPool(rows, ["a", "b"], higher);
  const second = rankPool(rows, ["a", "b"], higher);
  assert.deepEqual([...first.keys()], ["z", "y", "x"]);
  assert.deepEqual([...first.entries()], [...second.entries()]);
  assert.deepEqual(Object.keys(first.get("x")!), ["a", "b"]);
  assert.equal(first.get("x")!.b, null);
});

test("directions for the site's metrics: lower for turnovers, defence and opponents", () => {
  for (const key of ["tov", "pf", "fouls", "drtg", "oefg", "oftr"]) assert.equal(betterOf(key), "lower", key);
  for (const key of ["pts", "ts", "ortg", "efg", "dreb", "otov", "pir"]) assert.equal(betterOf(key), "higher", key);
  assert.equal(betterOf("usg"), "neither");
  assert.equal(betterOf("not_a_metric"), "higher");
  assert.equal(betterOf("constructor"), "higher");
});
