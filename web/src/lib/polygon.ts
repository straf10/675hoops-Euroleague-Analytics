// The percentile polygon on Compare: each player's place among the qualified players of his season
// (or of the career pool), axis by axis, drawn as a closed shape on rings at 25, 50, 75 and 100.
// Pure (no browser imports), so Node runs it for the tests. Metric formulas come from measures.ts,
// the direction of each metric from betterOf (better.ts), and the ranking from rankPool (percentile.ts).

import { betterOf } from "./better.ts";
import { BY_KEY, rated, TOV_PCT, type Measure } from "./measures.ts";
import { rankPool, type PoolRow } from "./percentile.ts";

export const MIN_AXES = 3;
export const MAX_AXES = 8;
const RINGS = [25, 50, 75, 100];
/** The season pool's game floor, as in the player page's league board: a quarter of the most games anyone played, and at least this many. */
const MIN_FLOOR_GAMES = 5;
/** Minutes a game for a season line to be pooled (the Players page default). */
const FLOOR_MINUTES = 10;

export interface Axis {
  key: string;
  head: string;
  name: string;
  about: string;
}

const measureOf = (key: string): Measure | undefined => (key === TOV_PCT.key ? TOV_PCT : BY_KEY[key]);

/** Every axis the picker offers, in the order it lists them. */
export const AXIS_KEYS = [
  "pts",
  "ts",
  "usg",
  "ast_pct",
  "reb_pct",
  "tov_pct",
  "net",
  "reb",
  "ast",
  "stl",
  "blk",
  "pir",
  "efg",
  "fg2_pct",
  "fg3_pct",
  "ft_pct",
  "ast_tov",
];

function axisOf(key: string): Axis {
  const m = measureOf(key);
  if (!m) throw new Error(`polygon: no measure for axis ${key}`);
  return { key, head: m.head, name: m.name, about: m.about };
}

export const AXES: Axis[] = AXIS_KEYS.map(axisOf);

/** The seven default axes: the All-round preset. */
export const DEFAULT_AXES = ["pts", "ts", "usg", "ast_pct", "reb_pct", "tov_pct", "net"];

interface Preset {
  key: string;
  label: string;
  axes: string[];
}

/** Presets: each one sets the axis list. Usage has no better side, so a high usage reads as 100. */
export const PRESETS: Preset[] = [
  { key: "all-round", label: "All-round", axes: DEFAULT_AXES },
  { key: "scoring", label: "Scoring", axes: ["pts", "ts", "efg", "fg2_pct", "fg3_pct", "ft_pct", "usg"] },
  { key: "creation", label: "Creation", axes: ["pts", "ast", "ast_pct", "ast_tov", "tov_pct", "usg"] },
  { key: "interior", label: "Interior", axes: ["reb", "reb_pct", "blk", "fg2_pct", "net"] },
  { key: "efficiency", label: "Efficiency", axes: ["ts", "efg", "ft_pct", "tov_pct", "ast_tov", "net"] },
];

/** Adds or removes one axis, keeping the picker's order. A change that would leave fewer than
 *  MIN_AXES or more than MAX_AXES returns the list unchanged. */
export function toggleAxis(current: string[], key: string): string[] {
  if (current.includes(key)) return current.length > MIN_AXES ? current.filter((k) => k !== key) : current;
  if (current.length >= MAX_AXES) return current;
  return AXIS_KEYS.filter((k) => k === key || current.includes(k));
}

interface Point {
  x: number;
  y: number;
}

const round = (v: number) => Math.round(v * 100) / 100;

/** Vertex of axis i (of n) at `pct` (0 to 100) on a circle of `radius` centred on (cx, cy). Axis 0
 *  points straight up; the rest follow clockwise, evenly spaced. */
export function vertex(i: number, n: number, pct: number, cx: number, cy: number, radius: number): Point {
  const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
  const r = (radius * pct) / 100;
  return { x: round(cx + r * Math.cos(a)), y: round(cy + r * Math.sin(a)) };
}

/** The `n` vertices of a ring at `pct`, as an SVG points string. */
export function ringPoints(n: number, pct: number, cx: number, cy: number, radius: number): string {
  return Array.from({ length: n }, (_, i) => vertex(i, n, pct, cx, cy, radius))
    .map((p) => `${p.x},${p.y}`)
    .join(" ");
}

/** The shape's vertices for a player's percentiles. A missing axis (null) sits at the centre, so
 *  the shape shows the gap rather than hiding it; the text fallback names the axis. */
export function shapePoints(pct: (number | null)[], cx: number, cy: number, radius: number): string {
  const n = pct.length;
  return pct
    .map((p, i) => vertex(i, n, p ?? 0, cx, cy, radius))
    .map((p) => `${p.x},${p.y}`)
    .join(" ");
}

/** A metric's value for the pool or the player, per game for counts, or null when he does not qualify. */
function axisValue(key: string, t: Record<string, number>): number | null {
  const m = measureOf(key);
  if (!m) return null;
  if (m.qualifies && !m.qualifies(t)) return null;
  return rated(m, t, "game");
}

/** Totals by field name from a row's values, as the Players page builds them. */
function totalsOf(fields: string[], values: number[]): Record<string, number> {
  return Object.fromEntries(fields.map((f, i) => [f, values[i]]));
}

/** One pool line: a player's id, slug, name, listed position ("G" | "F" | "C") and totals by season. */
export interface RawPlayer {
  id: string;
  slug: string;
  name: string;
  pos?: string | null;
  totals: number[];
}

export interface AxisPlace {
  key: string;
  /** 0 (worst in the pool) to 100 (best); null when the player is not counted on this axis. */
  pct: number | null;
  /** 1 is best. */
  rank: number | null;
  /** Players counted on this axis in the pool. */
  of: number;
}

export interface Profile {
  slug: string;
  /** Why there is no shape, or null. */
  note: string | null;
  /** Players in the pool the profile is ranked against. */
  pool: number;
  axes: AxisPlace[];
}

interface PoolOptions {
  /** Career pool: whole careers with at least `careerGames` games (CAREER_GAMES in leaders.ts). */
  career: boolean;
  careerGames: number;
  /** Rank only against players with the same listed position. */
  position: boolean;
}

/** The lines that make up the pool. Season: a games floor and a minutes floor. Career: a games floor. */
function poolOf(players: RawPlayer[], fields: string[], career: boolean, careerGames: number): { p: RawPlayer; t: Record<string, number> }[] {
  const lines = players.map((p) => ({ p, t: totalsOf(fields, p.totals) }));
  if (career) return lines.filter((l) => (l.t.gp ?? 0) >= careerGames);
  const most = Math.max(0, ...lines.map((l) => l.t.gp ?? 0));
  const floorGames = Math.max(MIN_FLOOR_GAMES, Math.ceil(most / 4));
  return lines.filter((l) => l.t.gp >= floorGames && l.t.sec / l.t.gp / 60 >= FLOOR_MINUTES);
}

/** A player's percentile on each axis within the pool (see PoolOptions). */
export function profile(players: RawPlayer[], fields: string[], slug: string, axes: string[], opts: PoolOptions): Profile {
  const empty = (note: string, pool = 0): Profile => ({ slug, note, pool, axes: axes.map((key) => ({ key, pct: null, rank: null, of: 0 })) });
  const subject = players.find((p) => p.slug === slug);
  if (!subject) return empty("Not in this season's data.");
  const pool = poolOf(players, fields, opts.career, opts.careerGames);
  if (!pool.some((l) => l.p.id === subject.id)) return empty(opts.career ? `Under ${opts.careerGames} career games.` : "Under the season's games and minutes floors.");
  if (opts.position && !subject.pos) return empty("No listed position.");

  const rows: PoolRow[] = pool.map((l) => ({
    id: l.p.id,
    group: l.p.pos ?? null,
    values: Object.fromEntries(axes.map((key) => [key, axisValue(key, l.t)])),
  }));
  const placed = rankPool(rows, axes, (key) => (betterOf(key) === "lower" ? "lower" : "higher"), opts.position ? { group: subject.pos ?? null } : {});
  const mine = placed.get(subject.id);
  const counted = opts.position ? rows.filter((r) => r.group === (subject.pos ?? null)).length : rows.length;
  return {
    slug,
    note: null,
    pool: counted,
    axes: axes.map((key) => {
      const p = mine?.[key] ?? null;
      return { key, pct: p ? p.pct : null, rank: p ? p.rank : null, of: p ? p.of : 0 };
    }),
  };
}

/** One sentence per player for the text fallback: "PTS 81 (rank 9 of 214); TOV% not counted". */
export function describeProfile(name: string, prof: Profile, axes: Axis[]): string {
  if (prof.note) return `${name}: ${prof.note}`;
  const parts = axes.map((a, i) => {
    const p = prof.axes[i];
    return p.pct === null ? `${a.head} not counted` : `${a.head} ${Math.round(p.pct)} (rank ${p.rank} of ${p.of})`;
  });
  return `${name}, against ${prof.pool} players: ${parts.join("; ")}.`;
}

export interface SeriesShape {
  name: string;
  /** 1 to 5: the series token (--series-1 to --series-5). */
  slot: number;
  profile: Profile;
}

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** The whole SVG: rings, spokes, axis labels, one shape per series. Accessible name from `title`,
 *  the text fallback in `desc`. Colours come from the --series-N and --rule tokens. */
export function profileSvg(axes: Axis[], series: SeriesShape[], title: string, desc: string, id = "profile"): string {
  const size = 320;
  const c = size / 2;
  const R = 104;
  const n = axes.length;
  const rings = RINGS.map(
    (r) => `<polygon points="${ringPoints(n, r, c, c, R)}" fill="none" style="stroke:var(--rule-strong);stroke-width:1" />`,
  ).join("");
  const spokes = axes
    .map((_, i) => {
      const p = vertex(i, n, 100, c, c, R);
      return `<line x1="${c}" y1="${c}" x2="${p.x}" y2="${p.y}" style="stroke:var(--rule);stroke-width:1" />`;
    })
    .join("");
  const ringLabels = RINGS.map((r) => {
    const p = vertex(0, n, r, c, c, R);
    return `<text x="${p.x + 3}" y="${p.y}" class="ring-label">${r}</text>`;
  }).join("");
  const labels = axes
    .map((a, i) => {
      const p = vertex(i, n, 100, c, c, R + 16);
      const a0 = -Math.PI / 2 + (2 * Math.PI * i) / n;
      const cos = Math.cos(a0);
      const sin = Math.sin(a0);
      const anchor = cos > 0.2 ? "start" : cos < -0.2 ? "end" : "middle";
      const dy = sin > 0.5 ? "0.9em" : sin < -0.5 ? "-0.2em" : "0.35em";
      return `<text x="${p.x}" y="${p.y}" text-anchor="${anchor}" dy="${dy}" class="axis-label"><title>${esc(a.name)}: ${esc(a.about)}</title>${esc(a.head)}</text>`;
    })
    .join("");
  const shapes = series
    .filter((s) => s.profile.axes.some((a) => a.pct !== null))
    .map((s) => {
      const pct = s.profile.axes.map((a) => a.pct);
      return `<polygon class="shape" points="${shapePoints(pct, c, c, R)}" style="fill:var(--series-${s.slot});fill-opacity:0.12;stroke:var(--series-${s.slot});stroke-width:2"><title>${esc(s.name)}</title></polygon>`;
    })
    .join("");
  return (
    `<svg viewBox="0 0 ${size} ${size}" role="img" aria-labelledby="${id}-title ${id}-desc" class="profile-svg" xmlns="http://www.w3.org/2000/svg">` +
    `<title id="${id}-title">${esc(title)}</title><desc id="${id}-desc">${esc(desc)}</desc>` +
    `<g>${rings}${spokes}</g><g class="ring-labels" aria-hidden="true">${ringLabels}</g>` +
    `<g>${shapes}</g><g class="axis-labels">${labels}</g></svg>`
  );
}

/** The pool file a pick is ranked against: the career pool in Career scope, else its season's file.
 *  Null when the site has no pool for that season (2021-22 has player totals but no pool file), so
 *  the page never requests a file that does not exist. */
export function poolUrl(season: number, career: boolean, root: string, poolSeasons: readonly number[]): string | null {
  if (career) return `${root}/data/career-players.json`;
  return poolSeasons.includes(season) ? `${root}/data/players/${season}.json` : null;
}
