// Unit tests for the team page's coach list: the current coach first, then the most recent, and
// the rest counted as "+N more".

import { test } from "node:test";
import assert from "node:assert/strict";
import { shownCoaches, type ClubCoach } from "./team_coaches.ts";

const coach = (slug: string, last: number): ClubCoach => ({ slug, name: slug, last });

test("the current coach comes first, then the most recent previous coaches", () => {
  const out = shownCoaches([coach("a", 2015), coach("b", 2024), coach("c", 2020)], "a");
  assert.deepEqual(
    out.shown.map((c) => c.slug),
    ["a", "b", "c"],
  );
  assert.equal(out.more, 0);
});

test("four are named, and the rest are counted", () => {
  const rows = [coach("a", 2025), coach("b", 2024), coach("c", 2023), coach("d", 2020), coach("e", 2010), coach("f", 2008)];
  const out = shownCoaches(rows, "a");
  assert.deepEqual(
    out.shown.map((c) => c.slug),
    ["a", "b", "c", "d"],
  );
  assert.equal(out.more, 2);
});

test("with no current coach, the newest previous coach leads", () => {
  const out = shownCoaches([coach("old", 2008), coach("new", 2022)], undefined);
  assert.deepEqual(
    out.shown.map((c) => c.slug),
    ["new", "old"],
  );
});

test("no coaches, nothing to name", () => {
  assert.deepEqual(shownCoaches([], undefined), { shown: [], more: 0 });
});
