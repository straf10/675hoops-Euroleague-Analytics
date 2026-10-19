// Unit tests for the Teams index ranking: sort order, headings, columns and the query string.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  bestDir,
  captionOf,
  columnKeys,
  fromQuery,
  headingOf,
  phoneGroup,
  sortRows,
  toQuery,
  type IndexRow,
} from "./ranking.ts";

const row = (code: string, f: Record<string, number>): IndexRow => ({ code, name: code, w: 0, l: 0, f });
const rows: IndexRow[] = [
  row("AAA", { net: 5, drtg: 110, efg: 50 }),
  row("BBB", { net: 9, drtg: 104, efg: 48 }),
  row("CCC", { net: -2, drtg: 112, efg: 53 }),
];
const codes = (rs: IndexRow[]) => rs.map((r) => r.code).join(" ");

test("sorts by a higher-is-better metric both ways", () => {
  assert.equal(codes(sortRows(rows, "net", "desc")), "BBB AAA CCC");
  assert.equal(codes(sortRows(rows, "net", "asc")), "CCC AAA BBB");
});

test("a lower-is-better metric starts with its best end", () => {
  assert.equal(bestDir("drtg"), "asc");
  assert.equal(bestDir("net"), "desc");
  assert.equal(bestDir("pace"), "desc");
  assert.equal(codes(sortRows(rows, "drtg", bestDir("drtg"))), "BBB AAA CCC");
});

test("ties keep the input order and missing figures go last", () => {
  const tied = [row("X", { net: 1 }), row("Y", { net: 1 }), row("Z", { net: NaN }), row("W", { net: 2 })];
  assert.equal(codes(sortRows(tied, "net", "desc")), "W X Y Z");
  assert.equal(codes(sortRows(tied, "net", "asc")), "X Y W Z");
});

test("sorting does not change the input", () => {
  const before = codes(rows);
  sortRows(rows, "efg", "desc");
  assert.equal(codes(rows), before);
});

test("the heading follows the metric", () => {
  assert.equal(headingOf("net"), "By net rating");
  assert.equal(headingOf("ortg"), "By offensive rating");
  assert.equal(headingOf("efg"), "By effective FG%");
  assert.equal(headingOf("unknown"), "By net rating");
  assert.equal(captionOf("2025-26", "drtg"), "2025-26 clubs by defensive rating");
});

test("a metric outside the base columns gets a column after Pace", () => {
  assert.deepEqual(columnKeys("net"), ["ortg", "drtg", "net", "pace", "sos_played", "sos_ahead"]);
  assert.deepEqual(columnKeys("efg"), ["ortg", "drtg", "net", "pace", "sos_played", "sos_ahead", "efg"]);
});

test("the phone group that shows a metric's column", () => {
  assert.equal(phoneGroup("ortg"), 1);
  assert.equal(phoneGroup("pace"), 2);
  assert.equal(phoneGroup("net"), -1);
});

test("the query string writes only what differs from the defaults", () => {
  assert.equal(toQuery({ season: 2025, metric: "net", dir: "desc" }, 2025), "");
  assert.equal(toQuery({ season: 2024, metric: "ortg", dir: "desc" }, 2025), "?season=2024&metric=ortg");
  assert.equal(toQuery({ season: 2025, metric: "drtg", dir: "asc" }, 2025), "?metric=drtg");
  assert.equal(toQuery({ season: 2025, metric: "drtg", dir: "desc" }, 2025), "?metric=drtg&sort=desc");
  assert.equal(toQuery({ season: 2025, metric: "net", dir: "asc" }, 2025), "?sort=asc");
  assert.deepEqual(fromQuery("?metric=drtg&sort=desc", [2024, 2025], 2025), { season: 2025, metric: "drtg", dir: "desc" });
});

test("the query string reads back to the same view", () => {
  const v = { season: 2024, metric: "tov", dir: "desc" as const };
  assert.deepEqual(fromQuery(toQuery(v, 2025), [2024, 2025], 2025), v);
});

test("unknown values fall back to the defaults", () => {
  assert.deepEqual(fromQuery("?season=1999&metric=nope&sort=up", [2024, 2025], 2025), {
    season: 2025,
    metric: "net",
    dir: "desc",
  });
  assert.deepEqual(fromQuery("", [2024, 2025], 2025), { season: 2025, metric: "net", dir: "desc" });
});
