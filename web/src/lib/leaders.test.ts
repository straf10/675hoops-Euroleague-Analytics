// Unit tests for the Leaders overview: the boards, their qualifying floors, the leader and the next
// four, and the link to the Players page. Run with `node --test src/lib/` from web/ (Node 24+ strips
// the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { BOARDS, boards, fullListHref, qualifies, type Entry, type Totals } from "./leaders.ts";
import { BY_KEY } from "./measures.ts";

// A regular season: 20 games at 30 minutes, 30 points a game unless overridden, qualified on every
// measure's own rule (attempts, free throws, possessions, minutes).
const BASE: Totals = {
  gp: 20,
  sec: 36000,
  pts: 400,
  fg2m: 20,
  fg2a: 40,
  fg3m: 8,
  fg3a: 20,
  ftm: 16,
  fta: 20,
  oreb: 20,
  dreb: 80,
  ast: 100,
  stl: 20,
  blk: 10,
  tov: 50,
  pir: 300,
  pm: 50,
  poss: 1400,
  game_sec: 48000,
  tm_fga: 1200,
  tm_fgm: 500,
  tm_fta: 300,
  tm_tov: 250,
  tm_oreb: 200,
  tm_dreb: 600,
  opp_oreb: 200,
  opp_dreb: 600,
};

const player = (name: string, team: string, over: Partial<Totals> = {}, season = 2024): Entry => ({
  key: `${name}:${season}:${team}`,
  slug: name.toLowerCase(),
  name,
  team,
  dorsal: "7",
  season,
  first: season,
  last: season,
  t: { ...BASE, ...over },
});

test("there are seventeen boards, the total points one among them", () => {
  assert.equal(BOARDS.length, 17);
  assert.ok(BOARDS.some((b) => b.total && b.key === "pts"));
});

test("the leader is the highest per-game figure, then ranks 2 to 5 as text", () => {
  const list = [
    player("Ann", "PAM", { pts: 600 }),
    player("Ben", "OLY", { pts: 500 }),
    player("Cy", "BAR", { pts: 440 }),
    player("Di", "ULK", { pts: 400 }),
    player("Ed", "PAO", { pts: 380 }),
    player("Fay", "ASV", { pts: 360 }),
  ];
  const b = boards(list, { 2024: 20 }, false)[0]; // the first board is points per game
  assert.equal(b.leader?.e.name, "Ann");
  assert.equal(b.leader?.text, "30.0");
  assert.deepEqual(
    b.next.map((r) => r.e.name),
    ["Ben", "Cy", "Di", "Ed"],
  );
  assert.equal(b.qualified, 6);
});

test("the Players floors: a quarter of the most games, and ten minutes a game", () => {
  const most = { 2024: 40 };
  const few = player("Gus", "BAR", { gp: 9, pts: 900 });
  const shortMinutes = player("Hal", "BAR", { sec: 20 * 500 });
  assert.equal(qualifies(few, BY_KEY.pts, most, false), false);
  assert.equal(qualifies(shortMinutes, BY_KEY.pts, most, false), false);
  assert.equal(qualifies(player("Ivo", "BAR"), BY_KEY.pts, most, false), true);
});

test("a measure's own rule still applies: true shooting needs three shots a game", () => {
  const cold = player("Jo", "BAR", { fg2a: 10, fg3a: 5, fg2m: 4, fg3m: 2 });
  assert.equal(qualifies(cold, BY_KEY.ts, { 2024: 20 }, false), false);
  assert.equal(qualifies(cold, BY_KEY.pts, { 2024: 20 }, false), true);
});

test("a career needs 60 games, and its boards read the career line", () => {
  assert.equal(qualifies(player("Kit", "BAR", { gp: 59 }, 0), BY_KEY.pts, {}, true), false);
  assert.equal(qualifies(player("Kit", "BAR", { gp: 60 }, 0), BY_KEY.pts, {}, true), true);
});

test("total points sums the season, not the per-game figure", () => {
  const b = boards([player("Lu", "ULK", { pts: 600 })], { 2024: 20 }, false).find((x) => x.spec.total)!;
  assert.equal(b.leader?.value, 600);
  assert.equal(b.leader?.text, "600");
});

test("minutes, net rating and assist percentage use the shared formulas", () => {
  const list = [player("Mo", "ULK")];
  const find = (key: string) => boards(list, { 2024: 20 }, false).find((x) => x.spec.key === key && !x.spec.total)!;
  assert.equal(find("min").leader?.text, "30.0");
  assert.equal(find("net").leader?.text, "+3.6"); // 100 × 50 / 1400
  assert.ok(find("ast_pct").leader !== null);
});

test("a board with no qualifier has no leader and says so", () => {
  const b = boards([], {}, false)[0];
  assert.equal(b.leader, null);
  assert.deepEqual(b.next, []);
  assert.equal(b.qualified, 0);
});

test("the full-list link opens the Players page with the measure and season", () => {
  assert.equal(fullListHref("/", BOARDS[0], 2024, false), "/players/?metric=pts&season=2024");
  assert.equal(fullListHref("/site/", BOARDS[7], 2023, false), "/site/players/?metric=min&season=2023");
});

test("no link for career boards, or for total points (Players ranks per game)", () => {
  assert.equal(fullListHref("/", BOARDS[0], 0, true), null);
  assert.equal(fullListHref("/", BOARDS[6], 2024, false), null);
});
