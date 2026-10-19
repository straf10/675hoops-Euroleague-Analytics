// Unit tests for Compare's Teams-mode picks: the club picker's rules (one club per season, the
// same club allowed in another season) and the default pair. Run with
// `node --test "src/lib/**/*.test.ts"` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { addClub, clubChoices, defaultTeamPicks, latestSeason, TEAM_MAX, type TeamSeasonRows } from "./compare_teams.ts";
import type { IndexRow } from "./ranking.ts";

const row = (code: string, name: string, net: number): IndexRow => ({ code, name, w: 0, l: 0, f: { net } });
const seasons: TeamSeasonRows[] = [
  {
    season: 2024,
    label: "2024-25",
    rows: [row("AAA", "Alpha", 12), row("BBB", "Beta", 3), row("CCC", "Gamma", -4)],
  },
  {
    season: 2025,
    label: "2025-26",
    rows: [row("AAA", "Alpha", 1), row("BBB", "Beta", 9), row("DDD", "Delta", 9), row("CCC", "Gamma", 2)],
  },
];

test("the latest season is the one with the largest start year", () => {
  assert.equal(latestSeason(seasons)?.season, 2025);
  assert.equal(latestSeason([]), undefined);
});

test("the club picker lists one season's clubs by name, disabling a club already picked for that season", () => {
  const picks = [{ code: "BBB", season: 2025 }];
  const choices = clubChoices(seasons, 2025, picks);
  assert.deepEqual(
    choices.map((c) => [c.name, c.picked]),
    [
      ["Alpha", false],
      ["Beta", true],
      ["Delta", false],
      ["Gamma", false],
    ],
  );
});

test("the same club stays available in another season", () => {
  const picks = [{ code: "BBB", season: 2025 }];
  const other = clubChoices(seasons, 2024, picks).find((c) => c.code === "BBB");
  assert.equal(other?.picked, false);
});

test("addClub refuses the same club for the same season, but allows it for another season", () => {
  const picks = [{ code: "AAA", season: 2025 }];
  assert.equal(addClub(picks, { code: "AAA", season: 2025 }), picks, "same club, same season: refused");
  assert.deepEqual(addClub(picks, { code: "AAA", season: 2024 }), [
    { code: "AAA", season: 2025 },
    { code: "AAA", season: 2024 },
  ]);
});

test("addClub stops at the list's cap", () => {
  const full = Array.from({ length: TEAM_MAX }, (_, i) => ({ code: `C${i}`, season: 2025 }));
  assert.equal(addClub(full, { code: "ZZZ", season: 2025 }), full);
});

test("the default pair is the two strongest clubs (net rating) of the latest season", () => {
  // 2025-26: Beta and Delta tie on net 9; Beta first by name. Alpha and Gamma are not in the pair.
  assert.deepEqual(defaultTeamPicks(seasons), [
    { code: "BBB", season: 2025 },
    { code: "DDD", season: 2025 },
  ]);
  assert.deepEqual(defaultTeamPicks([]), []);
});
