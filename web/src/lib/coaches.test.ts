import { test } from "node:test";
import assert from "node:assert/strict";
import { normaliseName, searchCoaches, seasonRange, signed, winPct } from "./coaches.ts";

test("names normalise without accents, case or extra spaces", () => {
  assert.equal(normaliseName("Željko  Obradović"), "zeljko obradovic");
  assert.equal(normaliseName("  ŠARUNAS Jasikevičius "), "sarunas jasikevicius");
});

test("search matches accent-insensitive, case-insensitive parts of any word", () => {
  const coaches = [
    { name: "Željko Obradović", href: "/o/", seasons: [2010], clubs: ["PAN"] },
    { name: "Šarūnas Jasikevičius", href: "/j/", seasons: [2020], clubs: ["FBT"] },
    { name: "Pablo Laso", href: "/l/", seasons: [2015], clubs: ["MAD"] },
  ];
  assert.deepEqual(searchCoaches(coaches, "zeljko").map((c) => c.href), ["/o/"]);
  assert.deepEqual(searchCoaches(coaches, "OBRA").map((c) => c.href), ["/o/"]);
  assert.deepEqual(searchCoaches(coaches, "sarunas jasi").map((c) => c.href), ["/j/"]);
  assert.deepEqual(searchCoaches(coaches, "las").map((c) => c.href), ["/l/"]);
  assert.deepEqual(searchCoaches(coaches, "jasi laso"), []);
  assert.deepEqual(searchCoaches(coaches, "   "), []);
});

test("win percentage with one decimal, dash without games", () => {
  assert.equal(winPct({ games: 279, wins: 167 }), "59.9%");
  assert.equal(winPct({ games: 0, wins: 0 }), "-");
});

test("signed figures always print their sign", () => {
  assert.equal(signed(17.36), "+17.4");
  assert.equal(signed(-3), "-3.0");
  assert.equal(signed(0), "0.0");
  assert.equal(signed(-0.04), "0.0");
});

test("season range runs from the first to the last season", () => {
  assert.equal(seasonRange([2026, 2015, 2019]), "2015-16 to 2026-27");
  assert.equal(seasonRange([2021]), "2021-22");
  assert.equal(seasonRange([]), "-");
});
