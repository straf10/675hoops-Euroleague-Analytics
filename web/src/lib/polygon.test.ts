import { test } from "node:test";
import assert from "node:assert/strict";
import {
  AXES,
  AXIS_KEYS,
  DEFAULT_AXES,
  MAX_AXES,
  MIN_AXES,
  PRESETS,
  profile,
  profileSvg,
  ringPoints,
  shapePoints,
  toggleAxis,
  vertex,
  type RawPlayer,
} from "./polygon.ts";

const FIELDS = [
  "gp", "sec", "pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "ast", "stl", "tov", "blk",
  "pir", "pm", "poss", "game_sec", "tm_fga", "tm_fgm", "tm_fta", "tm_tov", "tm_poss", "tm_oreb", "tm_dreb",
  "opp_oreb", "opp_dreb",
];

/** A season line for a player who plays 35 minutes a game; `o` overrides fields by name. */
function line(id: string, gp: number, o: Record<string, number> = {}): RawPlayer {
  const base: Record<string, number> = {
    gp, sec: gp * 2100, pts: 15 * gp, fg2m: 4 * gp, fg2a: 8 * gp, fg3m: 2 * gp, fg3a: 5 * gp, ftm: 3 * gp, fta: 4 * gp,
    oreb: 1 * gp, dreb: 4 * gp, ast: 3 * gp, stl: gp, tov: 2 * gp, blk: 0, pir: 12 * gp, pm: 0, poss: 60 * gp,
    game_sec: gp * 2400, tm_fga: 60 * gp, tm_fgm: 25 * gp, tm_fta: 15 * gp, tm_tov: 12 * gp, tm_poss: 70 * gp,
    tm_oreb: 10 * gp, tm_dreb: 28 * gp, opp_oreb: 9 * gp, opp_dreb: 27 * gp,
    ...o,
  };
  return { id: `P:${id}`, slug: id, name: id.toUpperCase(), pos: "G", totals: FIELDS.map((f) => base[f] ?? 0) };
}

const season = { career: false, careerGames: 60, position: false };

test("vertex: axis 0 points up, the rest go clockwise and are evenly spaced", () => {
  assert.deepEqual(vertex(0, 4, 100, 50, 50, 40), { x: 50, y: 10 });
  assert.deepEqual(vertex(1, 4, 100, 50, 50, 40), { x: 90, y: 50 });
  assert.deepEqual(vertex(2, 4, 100, 50, 50, 40), { x: 50, y: 90 });
  assert.deepEqual(vertex(3, 4, 100, 50, 50, 40), { x: 10, y: 50 });
});

test("vertex: pct scales the radius, 0 is the centre", () => {
  assert.deepEqual(vertex(0, 7, 0, 50, 50, 40), { x: 50, y: 50 });
  assert.deepEqual(vertex(0, 7, 50, 50, 50, 40), { x: 50, y: 30 });
});

test("ringPoints: every vertex of a ring sits at its radius", () => {
  const pts = ringPoints(7, 75, 0, 0, 100).split(" ").map((s) => s.split(",").map(Number));
  assert.equal(pts.length, 7);
  for (const [x, y] of pts) assert.ok(Math.abs(Math.hypot(x, y) - 75) < 0.05);
});

test("shapePoints: a missing axis sits at the centre", () => {
  const pts = shapePoints([100, null, 100], 50, 50, 40).split(" ");
  assert.equal(pts[1], "50,50");
});

test("TOV% is inverted: the fewest turnovers in the pool is 100, the most is 0", () => {
  const players = [line("a", 20, { tov: 10 }), line("b", 20, { tov: 30 }), line("c", 20, { tov: 60 }), line("d", 20, { tov: 20 })];
  const pick = (slug: string) => profile(players, FIELDS, slug, ["tov_pct"], season).axes[0].pct;
  assert.equal(pick("a"), 100);
  assert.equal(pick("c"), 0);
  assert.ok((pick("d") ?? 0) > (pick("b") ?? 0));
});

test("a count axis reads higher as better, per game", () => {
  const players = [line("a", 20, { pts: 300 }), line("b", 20, { pts: 500 }), line("c", 20, { pts: 400 })];
  assert.equal(profile(players, FIELDS, "b", ["pts"], season).axes[0].pct, 100);
  assert.equal(profile(players, FIELDS, "a", ["pts"], season).axes[0].pct, 0);
});

test("season pool: players under the games floor are not ranked", () => {
  const players = [line("a", 30), line("b", 30), line("c", 30), line("cameo", 4)];
  const cameo = profile(players, FIELDS, "cameo", ["pts"], season);
  assert.match(cameo.note ?? "", /floor/);
  assert.equal(profile(players, FIELDS, "a", ["pts"], season).pool, 3);
});

test("career pool: the games floor is the career minimum", () => {
  const players = [line("long", 59), line("ok", 60), line("x", 80)];
  const opts = { career: true, careerGames: 60, position: false };
  assert.match(profile(players, FIELDS, "long", ["pts"], opts).note ?? "", /60 career games/);
  assert.equal(profile(players, FIELDS, "ok", ["pts"], opts).pool, 2);
});

test("position pool ranks only against the same listed position", () => {
  const guard = (id: string, pts: number) => ({ ...line(id, 20, { pts }), pos: "G" });
  const centre = (id: string, pts: number) => ({ ...line(id, 20, { pts }), pos: "C" });
  const players = [guard("g1", 300), guard("g2", 500), centre("c1", 900), centre("c2", 100)];
  const p = profile(players, FIELDS, "g1", ["pts"], { ...season, position: true });
  assert.equal(p.pool, 2);
  assert.equal(p.axes[0].pct, 0);
  assert.equal(p.axes[0].of, 2);
});

test("axes with no value (not qualified) are null, and the note names the rest", () => {
  // No shots, free throws or turnovers: TOV% has no base, so the value is null (not 0).
  const players = [line("a", 20, { fg2a: 0, fg3a: 0, fta: 0, tov: 0 }), line("b", 20, { tov: 5 })];
  const p = profile(players, FIELDS, "a", ["tov_pct", "pts"], season);
  assert.equal(p.axes[0].pct, null);
  assert.notEqual(p.axes[1].pct, null);
});

test("picker: the presets have 3 to 8 known, distinct axes", () => {
  for (const preset of PRESETS) {
    assert.ok(preset.axes.length >= MIN_AXES && preset.axes.length <= MAX_AXES, preset.label);
    assert.equal(new Set(preset.axes).size, preset.axes.length, preset.label);
    for (const k of preset.axes) assert.ok(AXIS_KEYS.includes(k), `${preset.label}: ${k}`);
  }
  assert.equal(AXES.length, AXIS_KEYS.length);
});

test("presets: All-round is the seven default axes, in the order they are listed", () => {
  assert.deepEqual(PRESETS[0].axes, DEFAULT_AXES);
  assert.deepEqual(DEFAULT_AXES, ["pts", "ts", "usg", "ast_pct", "reb_pct", "tov_pct", "net"]);
  assert.deepEqual(
    PRESETS.map((p) => p.label),
    ["All-round", "Scoring", "Creation", "Interior", "Efficiency"],
  );
});

test("toggleAxis: keeps the picker's order and stops at the bounds", () => {
  assert.deepEqual(toggleAxis(["pts", "ts", "net"], "reb"), ["pts", "ts", "net", "reb"]);
  assert.deepEqual(toggleAxis(["pts", "ts", "net"], "ts"), ["pts", "ts", "net"]);
  assert.deepEqual(toggleAxis(["pts", "ts", "net", "reb"], "ts"), ["pts", "net", "reb"]);
  assert.deepEqual(toggleAxis(["pts", "ts", "net"], "net"), ["pts", "ts", "net"]);
  const eight = AXIS_KEYS.slice(0, 8);
  assert.deepEqual(toggleAxis(eight, AXIS_KEYS[8]), eight);
});

test("profileSvg: an accessible name, one shape per series, four rings", () => {
  const axes = DEFAULT_AXES.map((k) => AXES.find((a) => a.key === k)!);
  const players = [line("a", 20, { pts: 300 }), line("b", 20, { pts: 500 }), line("c", 20, { pts: 400 })];
  const prof = profile(players, FIELDS, "b", DEFAULT_AXES, season);
  const svg = profileSvg(axes, [{ name: "B", slot: 1, profile: prof }], "Percentile profile", "B: text");
  assert.match(svg, /role="img"/);
  assert.match(svg, /aria-labelledby="profile-title profile-desc"/);
  assert.match(svg, /<title id="profile-title">Percentile profile<\/title>/);
  assert.match(svg, /<desc id="profile-desc">B: text<\/desc>/);
  assert.equal((svg.match(/class="shape"/g) ?? []).length, 1);
  assert.match(svg, /fill-opacity:0\.12;stroke:var\(--series-1\);stroke-width:2/);
  assert.equal((svg.match(/fill="none"/g) ?? []).length, 4);
});

test("profileSvg: a series with no values draws no shape", () => {
  const axes = [AXES[0], AXES[1], AXES[2]];
  const empty = { slug: "x", note: "Not in this season's data.", pool: 0, axes: axes.map((a) => ({ key: a.key, pct: null, rank: null, of: 0 })) };
  const svg = profileSvg(axes, [{ name: "X", slot: 2, profile: empty }], "t", "d");
  assert.equal((svg.match(/class="shape"/g) ?? []).length, 0);
});
