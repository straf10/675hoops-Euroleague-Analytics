import { test } from "node:test";
import assert from "node:assert/strict";
import {
  POLYGON_AXES,
  POLYGON_KEYS,
  TEAM_GROUPS,
  TEAM_MAX,
  figure,
  leaderOf,
  placeAll,
  shotShares,
  teamBodyHtml,
  teamColumns,
  teamDescription,
  teamHeadHtml,
  teamOptions,
  teamSeries,
  teamsFromQuery,
  teamsToQuery,
  withShots,
  type TeamSeasonRows,
} from "./compare_teams.ts";
import type { IndexRow } from "./ranking.ts";

const row = (code: string, name: string, f: Record<string, number>): IndexRow => ({ code, name, w: 0, l: 0, f });

// Four clubs with every polygon measure set, so each club's place is easy to read off.
const base = { ortg: 110, drtg: 100, efg: 55, tov: 14, oreb: 30, oefg: 50, otov: 12, dreb: 70, net: 10, pace: 70, ftr: 25, oftr: 20 };
const rows: IndexRow[] = [
  row("AAA", "Alpha", { ...base }),
  row("BBB", "Beta", { ...base, ortg: 120, drtg: 95, net: 25, efg: 60, tov: 10, oefg: 45, otov: 15, dreb: 75 }),
  row("CCC", "Gamma", { ...base, ortg: 100, drtg: 105, net: -5, efg: 50, tov: 18, oefg: 55, otov: 8, dreb: 65 }),
  row("DDD", "Delta", { ...base, ortg: 105, drtg: 100, net: 5, efg: 52, tov: 14, oefg: 50, otov: 12, dreb: 68 }),
];
const seasons: TeamSeasonRows[] = [
  { season: 2025, label: "2025-26", rows },
  { season: 2024, label: "2024-25", rows: rows.slice(0, 2) },
];

test("shotShares: shares of all six bands, rim+short, mid+long2, three+deep3", () => {
  const s = shotShares({
    rim: [50, 30],
    short: [10, 5],
    mid: [20, 8],
    long2: [10, 3],
    three: [40, 15],
    deep3: [10, 2],
  });
  // Rim and short 60, mid and long two 30, threes 50, of 140 attempts.
  assert.ok(Math.abs(s.rim_share - (100 * 60) / 140) < 1e-9);
  assert.ok(Math.abs(s.mid_share - (100 * 30) / 140) < 1e-9);
  assert.ok(Math.abs(s.three_share - (100 * 50) / 140) < 1e-9);
  assert.ok(Math.abs(s.rim_share + s.mid_share + s.three_share - 100) < 1e-9);
});

test("shotShares: no bands gives NaN, which the ranking skips", () => {
  const s = shotShares({});
  assert.ok(Number.isNaN(s.rim_share));
  assert.ok(Number.isNaN(s.three_share));
});

test("withShots adds the shares to each club and leaves its figures alone", () => {
  const out = withShots([rows[0]], { AAA: { rim: [10, 5], three: [10, 3] } });
  assert.equal(out[0].f.ortg, 110);
  assert.equal(out[0].f.rim_share, 50);
  assert.equal(out[0].f.three_share, 50);
  assert.ok(Number.isNaN(withShots([rows[1]], {})[0].f.rim_share));
});

test("placeAll ranks by betterOf: a lower turnover rate and a lower defensive rating place higher", () => {
  const p = placeAll(rows, ["tov", "drtg", "ortg"]);
  // tov: BBB (10) is best, CCC (18) worst.
  assert.equal(p.get("BBB")!.tov!.pct, 100);
  assert.equal(p.get("CCC")!.tov!.pct, 0);
  assert.equal(p.get("BBB")!.tov!.rank, 1);
  // drtg: BBB (95) is best.
  assert.equal(p.get("BBB")!.drtg!.rank, 1);
  // ortg: higher is better, so BBB (120) leads and CCC (100) trails.
  assert.equal(p.get("BBB")!.ortg!.rank, 1);
  assert.equal(p.get("CCC")!.ortg!.rank, 4);
});

test("placeAll: a missing figure is not placed", () => {
  const withGap = [...rows, row("EEE", "Epsilon", { ...base, efg: NaN })];
  const p = placeAll(withGap, ["efg"]);
  assert.equal(p.get("EEE")!.efg, null);
  assert.equal(p.get("BBB")!.efg!.of, 4);
});

test("teamColumns ranks each column within its own season and drops unknown picks", () => {
  const cols = teamColumns(
    [
      { code: "BBB", season: 2025 },
      { code: "BBB", season: 2024 },
      { code: "ZZZ", season: 2025 },
    ],
    seasons,
  );
  assert.equal(cols.length, 2);
  assert.equal(cols[0].pool, 4);
  assert.equal(cols[1].pool, 2);
  assert.equal(cols[1].placements.get("BBB")!.ortg!.of, 2);
});

test("leaderOf: best value among the columns, lower-is-better inverted, ties lead nobody", () => {
  const cols = teamColumns(
    [
      { code: "BBB", season: 2025 },
      { code: "CCC", season: 2025 },
    ],
    seasons,
  );
  assert.equal(leaderOf(cols, "tov"), 0); // BBB 10 beats CCC 18
  assert.equal(leaderOf(cols, "ortg"), 0); // BBB 120 beats CCC 100
  const tie = teamColumns(
    [
      { code: "AAA", season: 2025 },
      { code: "AAA", season: 2024 },
    ],
    seasons,
  );
  assert.equal(leaderOf(tie, "ortg"), -1);
  assert.equal(leaderOf(cols.slice(0, 1), "ortg"), -1);
});

test("figure: one decimal, net signed, shares with a percent sign, a dash for no value", () => {
  assert.equal(figure("ortg", 110.44), "110.4");
  assert.equal(figure("net", 4.24), "+4.2");
  assert.equal(figure("net", -3), "−3.0");
  assert.equal(figure("rim_share", 41.26), "41.3%");
  assert.equal(figure("ortg", NaN), "–");
  assert.equal(figure("ortg", undefined), "–");
});

test("POLYGON_AXES: eight axes, each with the metric's name and about text", () => {
  assert.equal(POLYGON_AXES.length, POLYGON_KEYS.length);
  assert.equal(POLYGON_AXES.length, 8);
  assert.equal(POLYGON_AXES[3].key, "tov");
  assert.ok(POLYGON_AXES.every((a) => a.head && a.name && a.about));
});

test("teamSeries: one shape per column, percentiles on every axis, slots 1 to 5", () => {
  const cols = teamColumns(
    [
      { code: "BBB", season: 2025 },
      { code: "CCC", season: 2025 },
    ],
    seasons,
  );
  const series = teamSeries(cols);
  assert.equal(series.length, 2);
  assert.deepEqual(series.map((s) => s.slot), [1, 2]);
  assert.equal(series[0].profile.axes.length, POLYGON_KEYS.length);
  // BBB is best on turnovers (tov, lower is better), so 100 on that axis.
  const tov = series[0].profile.axes.find((a) => a.key === "tov")!;
  assert.equal(tov.pct, 100);
  assert.match(teamDescription(cols), /Beta 2025-26/);
  // The key shows the short display code and season; the full name stays the title.
  assert.deepEqual(series.map((s) => s.label), ["BBB 2025-26", "CCC 2025-26"]);
  assert.deepEqual(series.map((s) => s.name), ["Beta 2025-26", "Gamma 2025-26"]);
});

test("teamSeries: a club outside the season's data gets a note and no shape", () => {
  const cols = teamColumns([{ code: "BBB", season: 2025 }], seasons);
  cols[0].code = "NOPE";
  const s = teamSeries(cols);
  assert.equal(s[0].profile.note, "Not in this season's data.");
  assert.ok(s[0].profile.axes.every((a) => a.pct === null));
});

test("teamHeadHtml and teamBodyHtml: codes, leader dot on the lead, groups in order", () => {
  const cols = teamColumns(
    [
      { code: "BBB", season: 2025 },
      { code: "CCC", season: 2025 },
    ],
    seasons,
  );
  const head = teamHeadHtml(cols, "<svg></svg>");
  assert.match(head, /class="tcode">BBB</);
  assert.match(head, /data-drop="1"/);
  const body = teamBodyHtml(cols);
  assert.equal((body.match(/<tbody>/g) ?? []).length, 4);
  assert.ok(body.indexOf("Ratings") < body.indexOf("Offense"));
  const measures = TEAM_GROUPS.flatMap((g) => g.keys);
  assert.equal((body.match(/lead-dot/g) ?? []).length, measures.filter((k) => leaderOf(cols, k) >= 0).length);
  assert.match(body, /Net/);
});

test("teamOptions: one entry per club-season, labelled with its season", () => {
  const opts = teamOptions(seasons);
  assert.equal(opts.length, rows.length + 2);
  assert.equal(opts[0].text, "Alpha (2025-26)");
  assert.deepEqual(opts[0].pick, { code: "AAA", season: 2025 });
});

test("teamsToQuery writes the mode and the picks, and teamsFromQuery reads them back", () => {
  const picks = [
    { code: "BBB", season: 2025 },
    { code: "AAA", season: 2024 },
  ];
  const q = teamsToQuery(picks);
  assert.equal(q, "?mode=teams&t=BBB-2025,AAA-2024");
  const known = (code: string, season: number) => seasons.some((s) => s.season === season && s.rows.some((r) => r.code === code));
  assert.deepEqual(teamsFromQuery(q, known), { mode: "teams", picks });
});

test("teamsFromQuery: players by default, unknown and repeated picks dropped, codes upper-cased, capped", () => {
  const known = (code: string, season: number) => season === 2025 && code !== "ZZZ";
  assert.deepEqual(teamsFromQuery("", known), { mode: "players", picks: [] });
  assert.deepEqual(teamsFromQuery("?p=some-player", known).mode, "players");
  const parsed = teamsFromQuery("?mode=teams&t=bbb-2025,BBB-2025,ZZZ-2025,junk,AAA-2025,DDD-2025,EEE-2025,FFF-2025,GGG-2025", known);
  assert.equal(parsed.mode, "teams");
  // Six valid picks: the list stops at TEAM_MAX (five), in link order.
  assert.deepEqual(
    parsed.picks.map((p) => `${p.code}-${p.season}`),
    ["BBB-2025", "AAA-2025", "DDD-2025", "EEE-2025", "FFF-2025"],
  );
  assert.equal(parsed.picks.length, TEAM_MAX);
});
