import { test } from "node:test";
import assert from "node:assert/strict";
import {
  COACH_METRICS,
  MIN_SAMPLE,
  coachHeadHtml,
  coachRows,
  coachRowsHtml,
  coachViewFromQuery,
  coachViewToQuery,
  formatMeasure,
  normaliseName,
  rate,
  scopeRows,
  searchCoaches,
  seasonRange,
  share,
  signed,
  sortCoaches,
  winPct,
  type CoachIndex,
  type CoachRow,
  type CoachStyle,
} from "./coaches.ts";

const style = (over: {
  ppp?: number | null;
  possessions?: number;
  clutchWins?: number;
  clutchLosses?: number;
  players?: number | null;
  rotationGames?: number;
  challengeGames?: number;
  perGame?: number | null;
  late?: number | null;
}): CoachStyle => ({
  ato: { possessions: over.possessions ?? 100, points: 0, ppp: over.ppp === undefined ? 1 : over.ppp, league_ppp: 1.05 },
  clutch: {
    games: (over.clutchWins ?? 0) + (over.clutchLosses ?? 0),
    team_games: 40,
    wins: over.clutchWins ?? 0,
    losses: over.clutchLosses ?? 0,
    league_share: 0.5,
  },
  rotation: {
    games: over.rotationGames ?? 50,
    players_per_game: over.players === undefined ? 10 : over.players,
    top7_share: 0.8,
    league_players_per_game: 10.5,
    league_top7_share: 0.8,
  },
  challenges:
    over.challengeGames === undefined
      ? null
      : {
          from_season: 2021,
          games: over.challengeGames,
          per_game: over.perGame ?? 0.4,
          late_share: over.late ?? 0.5,
          league_per_game: 0.36,
          league_late_share: 0.45,
        },
});

const row = (over: Partial<CoachRow> & { name: string }): CoachRow => ({
  slug: over.name.toLowerCase().replace(/\W+/g, "-"),
  href: `/coaches/${over.name.toLowerCase().replace(/\W+/g, "-")}/`,
  games: 0,
  wins: 0,
  losses: 0,
  seasons: 1,
  now: null,
  playoffs: { seasons: 0, final_four: 0, titles: 0 },
  style: null,
  ...over,
});

test("sorting puts a missing or thin figure last whichever way the sort runs", () => {
  const rows = [
    row({ name: "Empty" }), // no games: no win %
    row({ name: "Thin", games: 10, wins: 9, losses: 1 }), // 90%, but under 20 games: not ranked
    row({ name: "Best", games: 40, wins: 30, losses: 10 }), // 75%
    row({ name: "Worst", games: 40, wins: 10, losses: 30 }), // 25%
  ];
  // The missing ones keep the order they came in, after every ranked figure.
  assert.deepEqual(sortCoaches(rows, "win_pct", "desc").map((r) => r.name), ["Best", "Worst", "Empty", "Thin"]);
  assert.deepEqual(sortCoaches(rows, "win_pct", "asc").map((r) => r.name), ["Worst", "Best", "Empty", "Thin"]);
});

test("ties keep the order the rows came in, and games sorts most first", () => {
  const rows = [
    row({ name: "B", games: 30, wins: 15, losses: 15 }),
    row({ name: "A", games: 30, wins: 15, losses: 15 }),
    row({ name: "C", games: 50, wins: 10, losses: 40 }),
  ];
  assert.deepEqual(sortCoaches(rows, "win_pct", "desc").map((r) => r.name), ["B", "A", "C"]);
  assert.deepEqual(sortCoaches(rows, "games", "desc").map((r) => r.name), ["C", "B", "A"]);
});

test("after-timeout points per possession needs 50 possessions to be ranked", () => {
  const rows = [
    row({ name: "Few", style: style({ ppp: 1.6, possessions: 49 }) }),
    row({ name: "Enough low", style: style({ ppp: 0.9, possessions: MIN_SAMPLE.possessions }) }),
    row({ name: "Enough high", style: style({ ppp: 1.2, possessions: 120 }) }),
    row({ name: "Null", style: style({ ppp: null, possessions: 200 }) }),
  ];
  assert.deepEqual(sortCoaches(rows, "ato", "desc").map((r) => r.name), ["Enough high", "Enough low", "Few", "Null"]);
  assert.deepEqual(sortCoaches(rows, "ato", "asc").map((r) => r.name), ["Enough low", "Enough high", "Few", "Null"]);
});

test("clutch win % needs 10 clutch games; the clutch count sorts on its own", () => {
  const rows = [
    row({ name: "Nine", style: style({ clutchWins: 9, clutchLosses: 0 }) }),
    row({ name: "Ten", style: style({ clutchWins: 5, clutchLosses: 5 }) }),
    row({ name: "Twelve", style: style({ clutchWins: 4, clutchLosses: 8 }) }),
  ];
  assert.deepEqual(sortCoaches(rows, "clutch_pct", "desc").map((r) => r.name), ["Ten", "Twelve", "Nine"]);
  assert.deepEqual(sortCoaches(rows, "clutch_games", "desc").map((r) => r.name), ["Twelve", "Ten", "Nine"]);
});

test("challenges start in 2021-22: a coach without a record sorts last and shows a dash", () => {
  const rows = [
    row({ name: "None", style: style({}) }),
    row({ name: "Some", style: style({ challengeGames: 30, perGame: 0.2, late: 0.7 }) }),
  ];
  assert.deepEqual(sortCoaches(rows, "challenges", "desc").map((r) => r.name), ["Some", "None"]);
  const metric = COACH_METRICS.find((m) => m.key === "challenges")!;
  assert.equal(formatMeasure(metric.read(rows[0]), metric.kind), "-");
  assert.equal(formatMeasure(metric.read(rows[1]), metric.kind), "0.20");
});

test("the index rows take the scope, the club now, and each coach's style", () => {
  const index = {
    h2h_min_games: 4,
    coverage: [],
    current_season: 2026,
    current_through: "2026-10-16",
    current: [{ team: "FBT", slug: "a-coach" }],
    coaches: [
      { slug: "a-coach", name: "A Coach", games: 30, wins: 20, losses: 10, expected_wins: 15, wins_above_expectation: 5, seasons_played: [2025, 2026], clubs: ["FBT"], playoffs: { seasons: 2, final_four: 1, titles: 0 } },
      { slug: "b-coach", name: "B Coach", games: 10, wins: 4, losses: 6, expected_wins: 5, wins_above_expectation: -1, seasons_played: [2019], clubs: ["BAR"], playoffs: { seasons: 0, final_four: 0, titles: 0 } },
    ],
  } as unknown as CoachIndex;
  const rows = coachRows(index, { "a-coach": style({}), "b-coach": null }, "/base/");
  assert.equal(rows[0].href, "/base/coaches/a-coach/");
  assert.equal(rows[0].now, "FBT");
  assert.equal(rows[1].now, null);
  assert.equal(rows[1].style, null);
  assert.deepEqual(scopeRows(rows, "current").map((r) => r.slug), ["a-coach"]);
  assert.deepEqual(scopeRows(rows, "all").map((r) => r.slug), ["a-coach", "b-coach"]);
});

test("the view reads and writes the query string, with the page's scope as the default", () => {
  assert.deepEqual(coachViewFromQuery("", "current"), { scope: "current", metric: "games", dir: "desc" });
  assert.deepEqual(coachViewFromQuery("?scope=all&metric=ato&sort=asc", "current"), { scope: "all", metric: "ato", dir: "asc" });
  assert.deepEqual(coachViewFromQuery("?metric=nope&sort=up", "all"), { scope: "all", metric: "games", dir: "desc" });
  assert.equal(coachViewToQuery({ scope: "current", metric: "games", dir: "desc" }, "current"), "");
  assert.equal(coachViewToQuery({ scope: "all", metric: "win_pct", dir: "asc" }, "current"), "?scope=all&metric=win_pct&sort=asc");
  const view = { scope: "all" as const, metric: "titles", dir: "desc" as const };
  assert.deepEqual(coachViewFromQuery(coachViewToQuery(view, "current"), "current"), view);
});

test("the head has one sortable button per metric, the chosen one marked, and each has a tip", () => {
  const html = coachHeadHtml({ scope: "all", metric: "win_pct", dir: "asc" });
  for (const m of COACH_METRICS) assert.ok(html.includes(`data-sort="${m.key}"`), m.key);
  assert.ok(html.includes('aria-sort="ascending"'));
  assert.equal((html.match(/class="info-tip"/g) ?? []).length, COACH_METRICS.length);
});

test("the body escapes names, greys a thin rate, and prints a dash for a missing one", () => {
  const rows = [row({ name: "Ann <b>Smith</b>", games: 5, wins: 3, losses: 2, now: "BAR" })];
  const html = coachRowsHtml(rows, "win_pct");
  assert.ok(html.includes("Ann &lt;b&gt;Smith&lt;/b&gt;"));
  assert.ok(html.includes('class="num strong thin"'));
  assert.ok(html.includes('<td class="now">BAR</td>'));
  assert.ok(html.includes(">-</td>"));
});

test("formatting: integers, win %, share and rates, dash without a value", () => {
  const win = COACH_METRICS.find((m) => m.key === "win_pct")!;
  assert.equal(formatMeasure({ value: 0.6129, thin: false }, win.kind), "61.3%");
  assert.equal(formatMeasure({ value: null, thin: false }, win.kind), "-");
  assert.equal(formatMeasure({ value: 3.4, thin: false }, "int"), "3");
});

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

test("per-game rates and shares print with their precision, dash without a value", () => {
  assert.equal(rate(1.0483), "1.05");
  assert.equal(rate(10.275, 1), "10.3");
  assert.equal(rate(null), "-");
  assert.equal(share(0.5395), "54%");
  assert.equal(share(0.4286), "43%");
  assert.equal(share(null), "-");
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
