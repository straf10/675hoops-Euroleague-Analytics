// Unit tests for the Compare accolades: season lookup, stat titles and career counts and rates.
// Run with `node --test "src/lib/**/*.test.ts"` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { careerAchievements, formatRate, seasonAchievement, seasonTitles, type AchEntry, type StatTitle } from "./achievement.ts";

const e = (season: number, club: string, reached: AchEntry[2], champion: 0 | 1 = 0): AchEntry => [season, club, reached, champion];

test("a season shows the furthest stage of the club he played for", () => {
  const entries = [e(2021, "EFS", "W", 1)];
  assert.deepEqual(seasonAchievement(entries, 2021), { reached: "W", club: "EFS", clubs: 1, champion: true });
  assert.equal(seasonAchievement(entries, 2020), null);
});

test("a mid-season move keeps the furthest stage over both clubs", () => {
  const entries = [e(2019, "PAO", "RS"), e(2019, "BAR", "PO")];
  const s = seasonAchievement(entries, 2019);
  assert.equal(s?.reached, "PO");
  assert.equal(s?.club, "BAR");
  assert.equal(s?.clubs, 2);
  assert.equal(s?.champion, false);
});

test("career counts go by season, so a split season is counted once", () => {
  const entries = [e(2019, "PAO", "RS"), e(2019, "BAR", "FF"), e(2020, "BAR", "RS")];
  const c = careerAchievements(entries);
  assert.equal(c.seasons, 2);
  assert.equal(c.clubs, 2);
  assert.equal(c.finalFours, 1);
  assert.equal(c.playoffs, 1);
  assert.equal(c.finalFourRate, 0.5);
  assert.equal(c.playoffRate, 0.5);
});

test("titles count the seasons his club won, and the Final Four counts toward playoffs", () => {
  const entries = [
    e(2021, "EFS", "W", 1),
    e(2022, "EFS", "F", 0),
    e(2023, "EFS", "FF", 0),
    e(2024, "EFS", "PO", 0),
    e(2025, "EFS", "RS", 0),
  ];
  const c = careerAchievements(entries);
  assert.equal(c.seasons, 5);
  assert.equal(c.titles, 1);
  assert.equal(c.finals, 2);
  assert.equal(c.finalFours, 3);
  assert.equal(c.playoffs, 4);
  assert.equal(c.playoffRate, 0.8);
  assert.equal(c.finalFourRate, 0.6);
});

test("a player of the champion gets the title even without a Final Four game", () => {
  // The club's stage is W for every club-mate he played for (achievements.py)
  const c = careerAchievements([e(2022, "EFS", "W", 1)]);
  assert.equal(c.titles, 1);
  assert.equal(c.finals, 1);
  assert.equal(c.finalFours, 1);
});

test("a final counts once per season, when either club of a split season reached it", () => {
  const c = careerAchievements([e(2023, "PAO", "F", 0), e(2023, "BAR", "PO", 0)]);
  assert.equal(c.finals, 1);
  assert.equal(c.clubs, 2);
});

test("no entries give no rates", () => {
  const c = careerAchievements([]);
  assert.deepEqual(c, {
    seasons: 0,
    clubs: 0,
    titles: 0,
    finals: 0,
    finalFours: 0,
    finalFourRate: null,
    playoffs: 0,
    playoffRate: null,
    statTitles: 0,
  });
  assert.equal(formatRate(c.playoffRate), "–");
});

test("stat titles are counted per title and listed by season", () => {
  const titles: StatTitle[] = [
    [2021, "pts"],
    [2021, "pir"],
    [2023, "blk"],
  ];
  const c = careerAchievements([e(2021, "EFS", "W", 1), e(2023, "EFS", "PO", 0)], titles);
  assert.equal(c.statTitles, 3);
  assert.deepEqual(seasonTitles(titles, 2021), ["Points", "PIR"]);
  assert.deepEqual(seasonTitles(titles, 2022), []);
});

test("rates print as whole percentages", () => {
  assert.equal(formatRate(1 / 3), "33%");
  assert.equal(formatRate(0.5), "50%");
  assert.equal(formatRate(1), "100%");
});
