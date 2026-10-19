// Tests for the sitemap's <lastmod> dates: each page carries the date its data last changed, and
// a static page carries none. Run with `node --test scripts/sitemap-lastmod.test.mjs` from web/.

import { test } from "node:test";
import assert from "node:assert/strict";
import { dateIndex, lastmodFor } from "./sitemap-lastmod.mjs";

const data = {
  seasons: [
    {
      season: 2025,
      games: {
        E2025_1: ["2025-10-03", 1, "RS", "DUB", "BAR", 80, 75],
        E2025_2: ["2025-10-10", 2, "RS", "BAR", "DUB", 90, 88],
      },
      log_fields: ["game_id", "team", "pts"],
      logs: { P1: [["E2025_1", "DUB", 10]], P2: [["E2025_2", "BAR", 4]] },
    },
    {
      season: 2026,
      games: { E2026_9: ["2026-10-17", 6, "RS", "BAR", "MAD", 70, 66] },
      log_fields: ["game_id", "team", "pts"],
      logs: { P1: [["E2026_9", "DUB", 2]] },
    },
  ],
  players: [
    { id: "P1", slug: "first-player" },
    { id: "P2", slug: "second-player" },
  ],
  coaches: [{ slug: "a-coach", seasons: [{ season: 2025, team: "DUB" }] }],
};
const index = dateIndex(data);
const origin = "https://675hoops.com";

test("a game page carries the game's own date", () => {
  assert.equal(lastmodFor(`${origin}/games/E2025_2/`, index), "2025-10-10");
});

test("a player page carries the date of the player's latest game, across seasons", () => {
  assert.equal(lastmodFor(`${origin}/players/first-player/`, index), "2026-10-17");
  assert.equal(lastmodFor(`${origin}/players/second-player/`, index), "2025-10-10");
});

test("a team page carries the club's latest game date, matched on the lower-case code", () => {
  assert.equal(lastmodFor(`${origin}/teams/bar/`, index), "2026-10-17");
  assert.equal(lastmodFor(`${origin}/teams/dub/`, index), "2025-10-10");
});

test("a coach page carries the club's latest game in the coach's last season there", () => {
  assert.equal(lastmodFor(`${origin}/coaches/a-coach/`, index), "2025-10-10");
});

test("a static page, the home page and an unknown id carry no lastmod", () => {
  assert.equal(lastmodFor(`${origin}/methodology/`, index), undefined);
  assert.equal(lastmodFor(`${origin}/`, index), undefined);
  assert.equal(lastmodFor(`${origin}/games/E9999_1/`, index), undefined);
});

test("dates differ between pages: a sitemap with one build date for all is not what this gives", () => {
  const dates = new Set(
    [
      `${origin}/games/E2025_1/`,
      `${origin}/games/E2026_9/`,
      `${origin}/players/second-player/`,
    ].map((u) => lastmodFor(u, index)),
  );
  assert.ok(dates.size > 1);
});
