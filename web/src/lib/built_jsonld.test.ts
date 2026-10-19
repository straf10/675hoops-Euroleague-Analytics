// Checks the structured data of one built page of each type (game, player, team, coach, home,
// downloads): every JSON-LD block parses, and each carries the fields its schema.org type needs.
// Reads the build in ../site, so it skips when the site has not been built (npx astro build).
// Run with `node --test src/lib/built_jsonld.test.ts` from web/.

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const SITE = resolve("../site");
const built = existsSync(join(SITE, "index.html"));

/** The parsed JSON-LD blocks of a built page, in document order. */
function blocks(page: string): Record<string, unknown>[] {
  const html = readFileSync(join(SITE, page), "utf8");
  const out: Record<string, unknown>[] = [];
  for (const m of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
    out.push(JSON.parse(m[1]) as Record<string, unknown>);
  }
  return out;
}

/** The first block of a schema.org type; fails the test when the page has none. */
function ofType(page: string, type: string): Record<string, unknown> {
  const hit = blocks(page).find((b) => b["@type"] === type);
  assert.ok(hit, `${page} has no ${type} block`);
  return hit;
}

/** The first subdirectory of a folder of the build: a real page to test against. */
function firstPage(folder: string): string {
  const dirs = readdirSync(join(SITE, folder), { withFileTypes: true }).filter((d) => d.isDirectory());
  assert.ok(dirs.length > 0, `no pages under ${folder}`);
  return `${folder}/${dirs[0].name}/index.html`;
}

const skip = built ? false : "no build in ../site (run npx astro build)";

test("every block on a built page is valid JSON with a schema.org context", { skip }, () => {
  for (const page of ["index.html", firstPage("games"), firstPage("players"), "downloads/index.html"]) {
    for (const b of blocks(page)) {
      assert.equal(b["@context"], "https://schema.org", `${page}: @context`);
      assert.equal(typeof b["@type"], "string", `${page}: @type`);
    }
  }
});

test("a game page has a SportsEvent with a name, a start, a place and both teams", { skip }, () => {
  const ev = ofType(firstPage("games"), "SportsEvent");
  assert.equal(typeof ev.name, "string");
  assert.equal(typeof ev.startDate, "string");
  assert.equal((ev.location as Record<string, unknown>)["@type"], "Place");
  assert.equal((ev.homeTeam as Record<string, unknown>)["@type"], "SportsTeam");
  assert.equal((ev.awayTeam as Record<string, unknown>)["@type"], "SportsTeam");
  assert.match(String(ev.eventStatus), /^https:\/\/schema\.org\/Event(Completed|Scheduled)$/);
});

test("a player page has a Person with a name and URL", { skip }, () => {
  const person = ofType(firstPage("players"), "Person");
  assert.equal(typeof person.name, "string");
  assert.match(String(person.url), /^https:\/\/675hoops\.com\/players\//);
});

test("a team page has a SportsTeam with a name, URL, sport and league", { skip }, () => {
  const team = ofType(firstPage("teams"), "SportsTeam");
  assert.equal(typeof team.name, "string");
  assert.match(String(team.url), /^https:\/\/675hoops\.com\/teams\//);
  assert.equal(team.sport, "Basketball");
  assert.equal((team.memberOf as Record<string, unknown>)["@type"], "SportsOrganization");
});

test("a coach page has a Person who is a head coach, with worksFor only when a club is current", { skip }, () => {
  const coach = ofType(firstPage("coaches"), "Person");
  assert.equal(coach.jobTitle, "Head coach");
  assert.equal("affiliation" in coach, false);
  if ("worksFor" in coach) {
    assert.equal((coach.worksFor as Record<string, unknown>)["@type"], "SportsTeam");
  }
});

test("the home page has a WebSite with a name and URL", { skip }, () => {
  const site = ofType("index.html", "WebSite");
  assert.equal(site.name, "6.75 Analytics");
  assert.equal(site.url, "https://675hoops.com/");
});

test("the downloads page has a Dataset with files to download", { skip }, () => {
  const ds = ofType("downloads/index.html", "Dataset");
  assert.equal(typeof ds.name, "string");
  const files = ds.distribution as Record<string, unknown>[];
  assert.ok(files.length > 0, "no DataDownload entries");
  for (const f of files) {
    assert.equal(f["@type"], "DataDownload");
    // The files are served from the repository's raw URLs, so only the scheme is fixed here.
    assert.match(String(f.contentUrl), /^https:\/\//);
  }
});

test("a breadcrumb trail is numbered from 1 with a link for each step", { skip }, () => {
  const trail = ofType(firstPage("players"), "BreadcrumbList").itemListElement as Record<string, unknown>[];
  assert.ok(trail.length >= 2, "a player page is at least two steps deep");
  trail.forEach((step, i) => {
    assert.equal(step.position, i + 1);
    assert.equal(step["@type"], "ListItem");
    assert.match(String(step.item), /^https:\/\/675hoops\.com\//);
  });
});
