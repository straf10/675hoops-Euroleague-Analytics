// Leaders: pools of player lines (a season or whole careers), the qualifying floors, and the
// overview's boards (about fifteen small rankings, NBA-style). Pure functions with no browser-only
// imports, so Node can test them (see leaders.test.ts). Run at build time for the first paint and in
// the browser when the season or the scope changes.

import { betterOf } from "./better.ts";
import { BY_KEY, format, rated, type Measure } from "./measures.ts";

type Scope = "season" | "career" | "best";
type Mode = "game" | "total";
export type Totals = Record<string, number>;

/** One line as the JSON endpoints ship it. ``season`` is 0 on a career line. */
export type Wire = [slug: string, name: string, team: string, dorsal: string, season: number, first: number, last: number, totals: number[]];

export interface Pool {
  fields: string[];
  /** season -> the most games any player played in it (the season floor's reference) */
  most: Record<string, number>;
  rows: Wire[];
}

export interface Entry {
  key: string;
  slug: string;
  name: string;
  team: string;
  dorsal: string;
  season: number;
  first: number;
  last: number;
  t: Totals;
}

interface View {
  scope: Scope;
  season: number;
  stat: string;
  mode: Mode;
  club: string; // "" = the whole league
}

// all-time hidden until pre-2022 seasons return (docs/SITE_FEEDBACK.md): set true to restore "Best seasons".
export const SHOW_ALL_TIME = false;
export const SCOPES: { key: Scope; label: string }[] = [
  { key: "season", label: "Season" },
  { key: "career", label: "Career" },
  ...(SHOW_ALL_TIME ? [{ key: "best" as Scope, label: "Best seasons" }] : []),
];
export const CAREER_GAMES = 60;
const SEASON_MINUTES = 15;
/** The Players page's floors (its defaults): a quarter of the most games anyone played that season,
 *  and ten minutes a game. A board ranks only players the Players page lists by default. */
const PLAYERS_GAMES_SHARE = 4;
const PLAYERS_MINUTES = 10;
/** The first season the overview offers (2022-23); older seasons stay out of the select. */
export const FIRST_OVERVIEW_SEASON = 2022;

export const seasonLabel = (s: number) => `${s}-${String((s + 1) % 100).padStart(2, "0")}`;

export function entries(pool: Pool): Entry[] {
  return pool.rows.map(([slug, name, team, dorsal, season, first, last, values]) => {
    const t: Totals = {};
    pool.fields.forEach((f, i) => (t[f] = values[i]));
    return { key: `${slug}:${season}:${team}`, slug, name, team, dorsal, season, first, last, t };
  });
}

/** Per-season club lines -> one line per player over all of them: club and number worn most. */
export function careers(lines: Entry[]): Entry[] {
  const by = new Map<string, Entry[]>();
  for (const e of lines) by.set(e.slug, [...(by.get(e.slug) ?? []), e]);
  return [...by.values()].map((own) => {
    const t: Totals = {};
    for (const e of own) for (const [k, v] of Object.entries(e.t)) t[k] = (t[k] ?? 0) + v;
    // The club and number are his latest, not the club he played most games for.
    const latest = [...own].sort((x, y) => x.season - y.season).at(-1)!;
    return {
      key: `${latest.slug}:0`,
      slug: latest.slug,
      name: latest.name,
      team: latest.team,
      dorsal: latest.dorsal,
      season: 0,
      first: Math.min(...own.map((e) => e.first)),
      last: Math.max(...own.map((e) => e.last)),
      t,
    };
  });
}

const measure = (key: string) => BY_KEY[key] ?? BY_KEY.pts;

export function valueOf(key: string, t: Totals, mode: Mode): number | null {
  const m = measure(key);
  const raw = m.value(t);
  if (raw === null || m.kind !== "count" || mode === "total") return raw;
  return t.gp ? raw / t.gp : null;
}

function text(key: string, v: number | null, mode: Mode): string {
  const m = measure(key);
  if (v === null || !Number.isFinite(v)) return "–";
  const digits = m.kind === "count" && mode === "total" ? 0 : m.digits;
  const body = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (v < 0 && Number(Math.abs(v).toFixed(digits)) !== 0) return `−${body}`;
  return m.signed && v > 0 ? `+${body}` : body;
}

const seasonFloor = (most: Record<string, number>, season: number) => Math.ceil((most[season] ?? 0) / 2);

/** Whether a line is left unranked on the view's stat (too few games, minutes or attempts). */
export function failsFloor(e: Entry, view: View, most: Record<string, number>): boolean {
  const m = measure(view.stat);
  if (m.qualifies && !m.qualifies(e.t)) return true;
  if (view.mode === "total" && m.kind === "count") return false;
  if (e.season === 0) return e.t.gp < CAREER_GAMES;
  return e.t.gp < seasonFloor(most, e.season) || e.t.sec / e.t.gp < SEASON_MINUTES * 60;
}

interface Ranked {
  e: Entry;
  value: number | null;
  text: string;
  rank: number; // 0 when not ranked
  floor: boolean;
}

function rank(list: Entry[], view: View, most: Record<string, number>): Ranked[] {
  const rows = list.map((e) => {
    const value = valueOf(view.stat, e.t, view.mode);
    return { e, value, text: text(view.stat, value, view.mode), rank: 0, floor: value === null || failsFloor(e, view, most) };
  });
  rows.sort((a, b) => {
    const qa = !a.floor, qb = !b.floor;
    if (qa !== qb) return qa ? -1 : 1;
    const d = (b.value ?? -Infinity) - (a.value ?? -Infinity);
    return d || b.e.t.sec - a.e.t.sec || a.e.name.localeCompare(b.e.name);
  });
  let n = 0;
  for (const r of rows) if (!r.floor) r.rank = ++n;
  return rows;
}

// ---- The overview boards -------------------------------------------------------------------

export interface BoardSpec {
  /** The measure key in measures.ts. */
  key: string;
  title: string;
  /** A season or career total rather than a per-game figure. */
  total?: boolean;
}

/** The overview's boards, in reading order (two per row on a wide screen, one on a phone). */
export const BOARDS: BoardSpec[] = [
  { key: "pts", title: "Points per game" },
  { key: "reb", title: "Rebounds per game" },
  { key: "ast", title: "Assists per game" },
  { key: "stl", title: "Steals per game" },
  { key: "blk", title: "Blocks per game" },
  { key: "pir", title: "PIR per game" },
  { key: "pts", title: "Total points", total: true },
  { key: "min", title: "Minutes per game" },
  { key: "ts", title: "True shooting %" },
  { key: "efg", title: "Effective FG%" },
  { key: "fg_pct", title: "Field-goal %" },
  { key: "fg3_pct", title: "Three-point %" },
  { key: "ft_pct", title: "Free-throw %" },
  { key: "usg", title: "Usage %" },
  { key: "net", title: "Net rating" },
  { key: "ast_pct", title: "Assist %" },
  { key: "ws", title: "Win shares", total: true },
];

/** Whether a line ranks on a measure: the measure's own attempts or minutes rule, then the floors. */
export function qualifies(e: Entry, m: Measure, most: Record<string, number>, career: boolean): boolean {
  if (m.qualifies && !m.qualifies(e.t)) return false;
  if (career) return e.t.gp >= CAREER_GAMES;
  if (!e.t.gp) return false;
  return e.t.gp >= Math.ceil((most[e.season] ?? 0) / PLAYERS_GAMES_SHARE) && e.t.sec / e.t.gp / 60 >= PLAYERS_MINUTES;
}

export interface BoardRank {
  e: Entry;
  value: number;
  text: string;
}

export interface Board {
  spec: BoardSpec;
  leader: BoardRank | null;
  /** Ranks 2 to 5. */
  next: BoardRank[];
  /** How many players rank on this board. */
  qualified: number;
}

/** The overview: every board for one pool (a season, or the career pool). */
export function boards(list: Entry[], most: Record<string, number>, career: boolean): Board[] {
  return BOARDS.map((spec) => {
    const m = measure(spec.key);
    const rows = list.flatMap((e) => {
      if (!qualifies(e, m, most, career)) return [];
      const value = spec.total ? m.value(e.t) : rated(m, e.t, "game");
      return value === null || !Number.isFinite(value) ? [] : [{ e, value }];
    });
    // Better-is-lower measures sort ascending; the rest, the highest first.
    const sign = betterOf(spec.key) === "lower" ? 1 : -1;
    rows.sort((a, b) => sign * (a.value - b.value) || b.e.t.sec - a.e.t.sec || a.e.name.localeCompare(b.e.name));
    const digits = spec.total ? 0 : m.digits;
    const ranked: BoardRank[] = rows.map((r) => ({ e: r.e, value: r.value, text: format({ ...m, digits }, r.value) }));
    return { spec, leader: ranked[0] ?? null, next: ranked.slice(1, 5), qualified: ranked.length };
  });
}

/** The Players page with this board's measure preselected, or null where Players has no such list
 *  (career boards, and total points: Players ranks per game, not totals). */
export function fullListHref(base: string, spec: BoardSpec, season: number, career: boolean): string | null {
  if (career || spec.total) return null;
  return `${base.replace(/\/$/, "")}/players/?metric=${spec.key}&season=${season}`;
}
