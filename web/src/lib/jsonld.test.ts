// Unit tests for the schema.org builders: a SportsEvent always has a name, a startDate and a
// location, and no nested event without them (Search Console read the old superEvent as one).
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { sportsEvent, sportsTeam, type GameInput, type JsonLdObject } from "./jsonld.ts";

const game = (over: Partial<GameInput> = {}): GameInput => ({
  name: "Crvena Zvezda at Baskonia",
  url: "https://675hoops.com/games/E2023_115/",
  description: "Baskonia 87, Crvena Zvezda 85, 2023-24 EuroLeague.",
  image: "https://675hoops.com/og.png",
  startDate: "2023-12-08T19:30:00Z",
  eventStatus: "completed",
  home: { name: "Baskonia", url: "https://675hoops.com/teams/kba/" },
  away: { name: "Crvena Zvezda", url: "https://675hoops.com/teams/cz/" },
  location: { name: "BUESA ARENA", address: "Ctra. Zurbano s/n, 01013 Vitoria" },
  ...over,
});

/** Every SportsEvent in a JSON-LD value, at any depth. */
function events(value: unknown, out: JsonLdObject[] = []): JsonLdObject[] {
  if (Array.isArray(value)) value.forEach((v) => events(v, out));
  else if (value && typeof value === "object") {
    const o = value as JsonLdObject;
    if (o["@type"] === "SportsEvent") out.push(o);
    Object.values(o).forEach((v) => events(v, out));
  }
  return out;
}

test("a game is one SportsEvent with name, startDate and location", () => {
  const [ev] = events([sportsEvent(game())]);
  assert.equal(ev["@context"], "https://schema.org");
  assert.equal(ev.name, "Crvena Zvezda at Baskonia");
  assert.equal(ev.startDate, "2023-12-08T19:30:00Z");
  assert.deepEqual(ev.location, {
    "@type": "Place",
    name: "BUESA ARENA",
    address: { "@type": "PostalAddress", streetAddress: "Ctra. Zurbano s/n, 01013 Vitoria" },
  });
});

test("no superEvent: nothing nested is a SportsEvent without a date and place", () => {
  const out = sportsEvent(game());
  assert.equal("superEvent" in out, false);
  for (const ev of events(out).slice(1)) {
    assert.ok(ev.startDate && ev.location, "nested SportsEvent lacks startDate or location");
  }
});

test("status, attendance mode and organizer are set; no offers and no endDate", () => {
  const done = sportsEvent(game());
  assert.equal(done.eventStatus, "https://schema.org/EventCompleted");
  assert.equal(done.eventAttendanceMode, "https://schema.org/OfflineEventAttendanceMode");
  assert.deepEqual(done.organizer, {
    "@type": "SportsOrganization",
    name: "EuroLeague",
    url: "https://www.euroleaguebasketball.net",
  });
  assert.equal("offers" in done, false);
  assert.equal("endDate" in done, false);
  const next = sportsEvent(game({ eventStatus: "scheduled" }));
  assert.equal(next.eventStatus, "https://schema.org/EventScheduled");
});

test("description, image and url come from the caller", () => {
  const ev = sportsEvent(game());
  assert.equal(ev.description, "Baskonia 87, Crvena Zvezda 85, 2023-24 EuroLeague.");
  assert.equal(ev.image, "https://675hoops.com/og.png");
  assert.equal(ev.url, "https://675hoops.com/games/E2023_115/");
});

test("a venue without an address is a Place with a name only, never an invented address", () => {
  const ev = sportsEvent(game({ location: { name: "UBER ARENA" } }));
  assert.deepEqual(ev.location, { "@type": "Place", name: "UBER ARENA" });
});

test("a date-only startDate passes through unchanged when the time is not set", () => {
  const ev = sportsEvent(game({ startDate: "2026-10-24" }));
  assert.equal(ev.startDate, "2026-10-24");
});

test("team references stay bare: name and url only", () => {
  const team = sportsTeam({ name: "Baskonia", url: "https://675hoops.com/teams/kba/" });
  assert.deepEqual(Object.keys(team).sort(), ["@context", "@type", "memberOf", "name", "sport", "url"]);
});
