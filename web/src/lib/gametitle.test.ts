// Unit tests for game titles and the pre-game line: a played game shows its score, an upcoming
// one reads "vs", and a missing pre-game row gives no chance rather than a made-up one.
// Run with `node --test src/lib/gametitle.test.ts` from web/.

import { test } from "node:test";
import assert from "node:assert/strict";
import { gameTitle, percent, preGameHomeChance, type PreGameRow } from "./gametitle.ts";

test("a played game reads as score, then the date", () => {
  assert.equal(
    gameTitle({ home: "Real Madrid", away: "Virtus Bologna", date: "2026-10-16", homeScore: 86, awayScore: 78 }),
    "Real Madrid 86–78 Virtus Bologna: EuroLeague, 16 Oct 2026",
  );
});

test("an upcoming game reads as home vs away, then the date", () => {
  assert.equal(
    gameTitle({ home: "Olympiacos Piraeus", away: "Baskonia", date: "2026-11-02" }),
    "Olympiacos Piraeus vs Baskonia: EuroLeague, 2 Nov 2026",
  );
});

test("a score on only one side is not a played game", () => {
  assert.equal(
    gameTitle({ home: "A", away: "B", date: "2026-11-02", homeScore: 80 }),
    "A vs B: EuroLeague, 2 Nov 2026",
  );
});

test("the pre-game chance is the headline model's home-side probability", () => {
  const rows: PreGameRow[] = [
    { game_id: "E2026_59", models: { elo: { p_home: 0.6517 }, m1: { p_home: 0.7231 } } },
  ];
  assert.equal(preGameHomeChance(rows, "elo", "E2026_59"), 0.6517);
  assert.equal(preGameHomeChance(rows, "m1", "E2026_59"), 0.7231);
});

test("no logged row, or no row for the headline model, gives no chance", () => {
  const rows: PreGameRow[] = [{ game_id: "E2026_59", models: { m1: { p_home: 0.7 } } }];
  assert.equal(preGameHomeChance(rows, "elo", "E2026_59"), null);
  assert.equal(preGameHomeChance(rows, "elo", "E2026_1"), null);
});

test("a probability reads as a whole percentage", () => {
  assert.equal(percent(0.6517), "65%");
  assert.equal(percent(0.5), "50%");
});
