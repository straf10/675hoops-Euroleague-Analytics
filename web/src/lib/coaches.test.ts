import { test } from "node:test";
import assert from "node:assert/strict";
import {
  COACH_METRICS,
  CORE_KEYS,
  SEASON_MIN_SAMPLE,
  SECTIONS,
  coachCaption,
  coachHeadHtml,
  coachRowsHtml,
  coachViewFromQuery,
  coachViewToQuery,
  columnKeys,
  formatMeasure,
  metricOf,
  namedSeasons,
  normaliseName,
  placementOf,
  placementShown,
  rate,
  searchCoaches,
  seasonLabel,
  seasonOf,
  seasonRange,
  seasonRows,
  share,
  signed,
  sortCoaches,
  switchSection,
  switchSeason,
  winPct,
  type CoachRow,
  type CoachSeasonRow,
  type CoachStyle,
  type CoachView,
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
  clutch?: number;
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
          league_per_game: 0.36,
          clutch: over.clutch ?? 0,
          clutch_per_clutch_game: 0.1,
          league_clutch_per_clutch_game: 0.12,
        },
});

const row = (over: Partial<CoachSeasonRow> & { name: string }): CoachSeasonRow => ({
  slug: over.name.toLowerCase().replace(/\W+/g, "-"),
  season: 2026,
  clubs: ["FBT"],
  games: 0,
  wins: 0,
  losses: 0,
  expected_wins: 0,
  wins_above_expectation: 0,
  playoffs: { seasons: 0, final_four: 0, titles: 0 },
  style: null,
  ...over,
});

const view = (over: Partial<CoachView>): CoachView => ({
  season: 2026,
  section: "expected",
  metric: "games",
  dir: "desc",
  ...over,
});

const metric = (key: string) => metricOf(key)!;

test("the sections name every non-core column exactly once", () => {
  const own = SECTIONS.flatMap((s) => s.keys);
  assert.equal(new Set(own).size, own.length);
  const all = COACH_METRICS.map((m) => m.key).filter((k) => !CORE_KEYS.includes(k));
  assert.deepEqual([...own].sort(), [...all].sort());
  assert.deepEqual(columnKeys("expected"), [...CORE_KEYS, "expected_wins", "wins_above_expectation", "placement"]);
  assert.deepEqual(columnKeys("advanced"), [
    ...CORE_KEYS,
    "ato",
    "clutch_pct",
    "clutch_games",
    "challenges",
    "clutch_challenges",
  ]);
  assert.deepEqual(
    SECTIONS.map((s) => s.label),
    ["Expected", "Advanced", "Rotation"],
  );
});

test("season minimums: win % from 5 games, after timeout from 25 possessions, clutch from 5 games", () => {
  assert.equal(SEASON_MIN_SAMPLE.games, 5);
  assert.equal(SEASON_MIN_SAMPLE.possessions, 25);
  assert.equal(SEASON_MIN_SAMPLE.clutch, 5);
  const winRow = (games: number) => row({ name: "W", games, wins: 1 });
  assert.equal(metric("win_pct").read(winRow(4)).thin, true);
  assert.equal(metric("win_pct").read(winRow(5)).thin, false);
  const atoRow = (possessions: number) => row({ name: "A", style: style({ ppp: 1, possessions }) });
  assert.equal(metric("ato").read(atoRow(24)).thin, true);
  assert.equal(metric("ato").read(atoRow(25)).thin, false);
  const clutchRow = (games: number) => row({ name: "C", style: style({ clutchWins: games, clutchLosses: 0 }) });
  assert.equal(metric("clutch_pct").read(clutchRow(4)).thin, true);
  assert.equal(metric("clutch_pct").read(clutchRow(5)).thin, false);
});

test("rotation and challenges per game need 5 games in the season", () => {
  const rot = (games: number) => row({ name: "R", style: style({ rotationGames: games }) });
  assert.equal(metric("players").read(rot(4)).thin, true);
  assert.equal(metric("top7").read(rot(5)).thin, false);
  const ch = (games: number) => row({ name: "H", style: style({ challengeGames: games, clutch: 3 }) });
  assert.equal(metric("challenges").read(ch(4)).thin, true);
  assert.equal(metric("challenges").read(ch(5)).thin, false);
});

test("clutch challenges are a count of the season's clutch-window challenges, a dash without a record", () => {
  const ch = row({ name: "H", style: style({ challengeGames: 5, clutch: 3 }) });
  assert.deepEqual(metric("clutch_challenges").read(ch), { value: 3, thin: false });
  assert.equal(formatMeasure(metric("clutch_challenges").read(ch), "int"), "3");
  const none = row({ name: "N", style: style({}) });
  assert.equal(formatMeasure(metric("clutch_challenges").read(none), "int"), "-");
});

test("a thin figure goes last whichever way the sort runs", () => {
  const rows = [
    row({ name: "Empty" }),
    row({ name: "Thin", games: 4, wins: 4 }),
    row({ name: "Best", games: 30, wins: 20, losses: 10 }),
    row({ name: "Worst", games: 30, wins: 10, losses: 20 }),
  ];
  assert.deepEqual(sortCoaches(rows, "win_pct", "desc").map((r) => r.name), ["Best", "Worst", "Empty", "Thin"]);
  assert.deepEqual(sortCoaches(rows, "win_pct", "asc").map((r) => r.name), ["Worst", "Best", "Empty", "Thin"]);
});

test("ties keep the order the rows came in", () => {
  const rows = [
    row({ name: "B", games: 30, wins: 15, losses: 15 }),
    row({ name: "A", games: 30, wins: 15, losses: 15 }),
    row({ name: "C", games: 50, wins: 10, losses: 40 }),
  ];
  assert.deepEqual(sortCoaches(rows, "win_pct", "desc").map((r) => r.name), ["B", "A", "C"]);
  assert.deepEqual(sortCoaches(rows, "games", "desc").map((r) => r.name), ["C", "B", "A"]);
});

test("the placement is the furthest stage, and sorts champion first", () => {
  const none = { seasons: 0, final_four: 0, titles: 0 };
  assert.equal(placementOf(none), "regular");
  assert.equal(placementOf({ ...none, play_ins: 1 }), "play_in");
  assert.equal(placementOf({ seasons: 1, final_four: 0, titles: 0, play_ins: 1 }), "playoffs");
  assert.equal(placementOf({ seasons: 1, final_four: 0, titles: 0 }), "playoffs");
  assert.equal(placementOf({ seasons: 1, final_four: 1, titles: 0 }), "final_four");
  assert.equal(placementOf({ seasons: 1, final_four: 1, titles: 0, runner_ups: 1 }), "runner_up");
  assert.equal(placementOf({ seasons: 1, final_four: 1, titles: 1 }), "champion");
  const rows = [
    row({ name: "Regular" }),
    row({ name: "Play-in", playoffs: { ...none, play_ins: 1 } }),
    row({ name: "Champion", playoffs: { seasons: 1, final_four: 1, titles: 1 } }),
    row({ name: "Runner-up", playoffs: { seasons: 1, final_four: 1, titles: 0, runner_ups: 1 } }),
    row({ name: "Playoffs", playoffs: { seasons: 1, final_four: 0, titles: 0 } }),
    row({ name: "Final Four", playoffs: { seasons: 1, final_four: 1, titles: 0 } }),
  ];
  const order = ["Champion", "Runner-up", "Final Four", "Playoffs", "Play-in", "Regular"];
  assert.deepEqual(sortCoaches(rows, "placement", "desc").map((r) => r.name), order);
  assert.deepEqual(
    sortCoaches(rows, "placement", "desc").map((r) => formatMeasure(metric("placement").read(r), "placement")),
    ["Champion", "Runner-up", "Final Four", "Playoffs", "Play-in", "Regular season"],
  );
});

test("placement is not shown for the season in progress", () => {
  assert.equal(placementShown(2026, 2026), false);
  assert.equal(placementShown(2025, 2026), true);
  assert.ok(!columnKeys("expected", false).includes("placement"));
  assert.ok(columnKeys("expected", true).includes("placement"));
  const hidden = coachHeadHtml(view({ section: "expected" }), false);
  assert.ok(!hidden.includes('data-sort="placement"'));
  assert.ok(coachHeadHtml(view({ section: "expected" }), true).includes('data-sort="placement"'));
  // A placement sort from a completed season does not carry into the season in progress.
  assert.deepEqual(
    coachViewFromQuery("?season=2026&section=expected&metric=placement", [2026, 2025], 2026),
    view({ metric: "games" }),
  );
  assert.deepEqual(
    coachViewFromQuery("?season=2025&section=expected&metric=placement", [2026, 2025], 2026),
    view({ season: 2025, metric: "placement" }),
  );
  assert.deepEqual(
    switchSeason(view({ section: "expected", metric: "placement", dir: "asc" }), 2026, 2026),
    view({ section: "expected", metric: "expected_wins", dir: "desc" }),
  );
  assert.deepEqual(
    switchSeason(view({ section: "expected", metric: "placement", dir: "asc" }), 2025, 2026),
    view({ season: 2025, section: "expected", metric: "placement", dir: "asc" }),
  );
});

test("challenges show a dash in a season without a record", () => {
  const rows = [
    row({ name: "None", style: style({}) }),
    row({ name: "Some", style: style({ challengeGames: 30, perGame: 0.2, clutch: 7 }) }),
  ];
  assert.deepEqual(sortCoaches(rows, "challenges", "desc").map((r) => r.name), ["Some", "None"]);
  assert.equal(formatMeasure(metric("challenges").read(rows[0]), "dec2"), "-");
  assert.equal(formatMeasure(metric("challenges").read(rows[1]), "dec2"), "0.20");
});

test("the season's rows are that season's coaches, with links", () => {
  const rows: CoachSeasonRow[] = [
    row({ name: "A Coach", season: 2026, clubs: ["FBT", "PAO"] }),
    row({ name: "B Coach", season: 2025, clubs: ["BAR"] }),
  ];
  const shown = seasonRows(rows, 2026, "/base/");
  assert.deepEqual(shown.map((r) => r.slug), ["a-coach"]);
  assert.equal(shown[0].href, "/base/coaches/a-coach/");
});

test("a season's file holds only that season's rows, in file order, and leaves the input alone", () => {
  const rows: CoachSeasonRow[] = [
    row({ name: "Old One", season: 2025 }),
    row({ name: "New Two", season: 2026 }),
    row({ name: "New One", season: 2026 }),
  ];
  const before = JSON.stringify(rows);
  assert.deepEqual(seasonOf(rows, 2026).map((r) => r.name), ["New Two", "New One"]);
  assert.deepEqual(seasonOf(rows, 2025).map((r) => r.name), ["Old One"]);
  assert.deepEqual(seasonOf(rows, 2019), []);
  assert.equal(JSON.stringify(rows), before);
});

test("a fetched season sorts and switches section like the embedded one", () => {
  const rows: CoachSeasonRow[] = [
    row({ name: "Low", season: 2020, games: 10, wins: 2, losses: 8 }),
    row({ name: "High", season: 2020, games: 10, wins: 8, losses: 2 }),
  ];
  const fetched = seasonOf(rows, 2020);
  const view = switchSection({ season: 2020, section: "expected", metric: "games", dir: "desc" }, "advanced");
  assert.equal(view.section, "advanced");
  assert.deepEqual(sortCoaches(seasonRows(fetched, 2020, "/b/"), "win_pct", "desc").map((r) => r.name), ["High", "Low"]);
});

test("the season options are the seasons the box scores name coaches for, newest first", () => {
  const coverage = [
    { season: 2014, games: 100, with_coach: 0 },
    { season: 2015, games: 100, with_coach: 40 }, // a single named side: under half, not listed
    { season: 2016, games: 100, with_coach: 90 },
    { season: 2026, games: 60, with_coach: 60 },
  ];
  assert.deepEqual(namedSeasons(coverage), [2026, 2016]);
});

test("the view reads and writes the query string, with the page's season as the default", () => {
  const seasons = [2026, 2025];
  assert.deepEqual(coachViewFromQuery("", seasons, 2026), view({}));
  assert.deepEqual(coachViewFromQuery("?season=2025&section=advanced&metric=ato&sort=asc", seasons, 2026), {
    season: 2025,
    section: "advanced",
    metric: "ato",
    dir: "asc",
  });
  // An unknown season, section or a column of another section falls back to the defaults.
  assert.deepEqual(coachViewFromQuery("?season=1999&section=nope&metric=ato&sort=up", seasons, 2026), view({ metric: "games" }));
  assert.deepEqual(coachViewFromQuery("?section=expected&metric=ato", seasons, 2026), view({ metric: "games" }));
  assert.equal(coachViewToQuery(view({}), 2026), "");
  const other = view({ season: 2025, section: "rotation", metric: "top7", dir: "asc" });
  assert.equal(coachViewToQuery(other, 2026), "?season=2025&section=rotation&metric=top7&sort=asc");
  assert.deepEqual(coachViewFromQuery(coachViewToQuery(other, 2026), seasons, 2026), other);
});

test("switching section keeps the sort column when the new section shows it, else resets it", () => {
  const start = view({ metric: "games", dir: "asc" });
  assert.deepEqual(switchSection(start, "expected").metric, "games");
  assert.equal(switchSection(start, "expected").dir, "asc");
  const moved = switchSection(view({ section: "expected", metric: "wins_above_expectation", dir: "asc" }), "advanced");
  assert.deepEqual(moved, view({ section: "advanced", metric: "ato", dir: "desc" }));
});

test("the head has a sortable button for each shown column, the chosen one marked, and a tip each", () => {
  const html = coachHeadHtml(view({ section: "advanced", metric: "win_pct", dir: "asc" }));
  const shown = columnKeys("advanced");
  for (const key of shown) assert.ok(html.includes(`data-sort="${key}"`), key);
  assert.equal((html.match(/data-sort=/g) ?? []).length, shown.length);
  assert.ok(!html.includes('data-sort="placement"'));
  assert.ok(html.includes('aria-sort="ascending"'));
  assert.equal((html.match(/class="info-tip"/g) ?? []).length, shown.length);
});

test("the body escapes names, shows the clubs, greys a thin rate and prints a dash for a missing one", () => {
  const rows: CoachRow[] = [
    { ...row({ name: "Ann <b>Smith</b>", games: 4, wins: 3, losses: 1, clubs: ["FBT", "PAO"] }), href: "/x/" },
  ];
  const html = coachRowsHtml(rows, view({ metric: "win_pct" }));
  assert.ok(html.includes("Ann &lt;b&gt;Smith&lt;/b&gt;"));
  assert.ok(html.includes('class="num strong thin"'));
  assert.ok(html.includes('<td class="club">FBT, PAO</td>'));
  const rotation = coachRowsHtml(rows, view({ section: "rotation" }));
  assert.ok(rotation.includes(">-</td>"));
});

test("the caption names the season's section and metric", () => {
  assert.equal(coachCaption(view({ metric: "win_pct" }), "2026-27 EuroLeague coaches"), "2026-27 EuroLeague coaches, by win %");
});

test("formatting: integers, win %, shares, rates, signed figures, dash without a value", () => {
  const win = metric("win_pct");
  assert.equal(formatMeasure({ value: 0.6129, thin: false }, win.kind), "61.3%");
  assert.equal(formatMeasure({ value: null, thin: false }, win.kind), "-");
  assert.equal(formatMeasure({ value: 3.4, thin: false }, "int"), "3");
  assert.equal(formatMeasure({ value: 2.5, thin: false }, metric("wins_above_expectation").kind), "+2.5");
  assert.equal(formatMeasure({ value: 4, thin: false }, metric("clutch_challenges").kind), "4");
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

test("season labels and ranges", () => {
  assert.equal(seasonLabel(2026), "2026-27");
  assert.equal(seasonRange([2026, 2015, 2019]), "2015-16 to 2026-27");
  assert.equal(seasonRange([2021]), "2021-22");
  assert.equal(seasonRange([]), "-");
});
