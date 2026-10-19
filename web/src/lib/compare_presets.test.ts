// Unit tests for the curated Compare presets: links and the check against the data.
// Run with `node --test "src/lib/**/*.test.ts"` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS, defaultPresetQuery, presetHref, presetProblems, presetQuery, usablePresets, type Preset } from "./compare_presets.ts";

const known: Record<string, number[]> = {
  "sergio-llull": [2007, 2008, 2022],
  "walter-tavares": [2022, 2023],
};
const seasonsOf = (slug: string) => known[slug] ?? null;

test("a season preset links with slug:season and a career preset with scope=career", () => {
  const season: Preset = { label: "x", scope: "season", picks: ["walter-tavares:2022", "sergio-llull:2008"] };
  const career: Preset = { label: "y", scope: "career", picks: ["sergio-llull", "walter-tavares"] };
  assert.equal(presetHref("/site/", season), "/site/compare/?p=walter-tavares:2022,sergio-llull:2008");
  assert.equal(presetHref("/", career), "/compare/?scope=career&p=sergio-llull,walter-tavares");
});

test("an unknown slug or a season the player has no lines for is a problem", () => {
  const p: Preset = { label: "z", scope: "season", picks: ["walter-tavares:2021", "luka-doncic:2022"] };
  assert.deepEqual(presetProblems(p, seasonsOf), ["walter-tavares: no 2021 season", "luka-doncic: no such player"]);
});

test("every curated player preset compares three players, each picked once", () => {
  for (const p of PRESETS) {
    assert.equal(p.picks.length, 3, `${p.label} should compare 3 players`);
    const slugs = p.picks.map((pick) => pick.split(":")[0]);
    assert.equal(new Set(slugs).size, slugs.length, `${p.label} repeats a player`);
  }
});

test("the default query opens on the first preset, with its scope", () => {
  assert.equal(defaultPresetQuery(PRESETS), presetQuery(PRESETS[0]));
  assert.equal(presetQuery(PRESETS[0]), `?scope=career&p=${PRESETS[0].picks.join(",")}`);
  assert.equal(defaultPresetQuery([]), "");
});

test("usablePresets keeps the good ones and warns about the rest", () => {
  const good: Preset = { label: "good", scope: "career", picks: ["sergio-llull", "walter-tavares"] };
  const bad: Preset = { label: "bad", scope: "season", picks: ["sergio-llull:2009"] };
  const { ok, warnings } = usablePresets([good, bad], seasonsOf);
  assert.deepEqual(ok, [good]);
  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /"bad" skipped: sergio-llull: no 2009 season/);
});
