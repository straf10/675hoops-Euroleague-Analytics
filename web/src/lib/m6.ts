// M6 on the site (weeks 16-18): the player card's projection, impact, shot-making and "plays like"
// blocks. The data is what `eurohoops publish` writes below src/data/api
// (the read-only API's responses, one file per route); every file may be absent.

import codes from "./m6_codes.json";

// ---- Data -------------------------------------------------------------------------------------

interface Band {
  mean: number;
  lo80: number;
  hi80: number;
}

export interface ProjectionRow {
  person_id: string;
  competition: string;
  team: string;
  name: string;
  debut_season: number;
  stats: Record<string, Band>;
  /** Decayed possessions behind the projection. */
  exposure: number;
  n_seasons: number;
  flags: string[];
}

export interface ProjectionReport {
  model: string;
  variant: string;
  half_life: number;
  gated: boolean;
  gate_passed: boolean;
  /** The projected season's first year: 2026 is 2026-27. */
  season: number;
  checkpoint: number;
  stats: string[];
  projections: ProjectionRow[];
}

export interface ImpactSeason {
  season: number;
  o: number;
  d: number;
  total: number;
  sd_total: number;
  ci90_o?: [number, number];
  ci90_d?: [number, number];
  ci90_total: [number, number];
  minutes: number;
  games: number;
  seen: boolean;
}

export interface RapmPlayer {
  person_id: string;
  name: string;
  /** The source team code of his last team that season (displayCode shows it). */
  team: string;
  /** Points per 100 possessions: offense, defense, and their sum. */
  o: number;
  d: number;
  total: number;
  ci90_o: [number, number];
  ci90_d: [number, number];
  ci90_total: [number, number];
  minutes: number;
  games: number;
  /** 1 is the best total among the players at the minimum minutes; null below them. */
  rank: number | null;
}

export interface RapmBoard {
  model: string;
  variant: string;
  units: string;
  /** The posterior interval's level: 0.9 is a 90% interval. */
  interval: number;
  /** The season's first year (2025 is 2025-26). */
  season: number;
  minimum_minutes: number;
  players: RapmPlayer[];
}

export const rapmBoard = (): Promise<RapmBoard | null> => load<RapmBoard>("rapm.json");

export interface ShotMakingSeason {
  season: number;
  split: string;
  fga: number;
  shot_making: number;
  ci90: [number, number];
}

export interface PlayerIndex {
  person_id: string;
  name: string;
  impact: { model: string; units: string; seasons: ImpactSeason[] } | null;
  shot_making: { model: string; units: string; seasons: ShotMakingSeason[] } | null;
}

interface SimilarRow {
  rank: number;
  person_id: string;
  competition: string;
  season: number;
  name: string;
  score: number;
  query_season?: number;
}

interface SimilarReport {
  model: string;
  season: number;
  person_id: string;
  features: Record<string, string[]>;
  pool_seasons: number[];
  similar: SimilarRow[];
}

// Lazy, like lib/stats.ts: a page only parses the files it reads, and no export means no files.
const files = {
  ...import.meta.glob<unknown>("../data/api/players/*/*.json", { import: "default" }),
  ...import.meta.glob<unknown>("../data/api/rapm.json", { import: "default" }),
};
const cache = new Map<string, Promise<unknown>>();

async function load<T>(relative: string): Promise<T | null> {
  const key = `../data/api/${relative}`;
  const loader = files[key] as (() => Promise<unknown>) | undefined;
  if (!loader) return null;
  if (!cache.has(key)) cache.set(key, loader());
  return (await cache.get(key)) as T;
}

/** A EuroLeague stats player's file key: source id X is person `P:X`, file `P_X`. */
const personKey = (id: string): string => `P_${id}`;

interface PlayerM6 {
  projection: ProjectionReport | null;
  index: PlayerIndex | null;
  similar: SimilarReport | null;
}

export async function playerM6(id: string): Promise<PlayerM6> {
  const dir = `players/${personKey(id)}`;
  const [projection, index, similar] = await Promise.all([
    load<ProjectionReport>(`${dir}/projection.json`),
    load<PlayerIndex>(`${dir}/index.json`),
    load<SimilarReport>(`${dir}/similar.json`),
  ]);
  return { projection, index, similar };
}

// ---- Words and numbers ------------------------------------------------------------------------

/** 2026 -> "2026-27". */
export const seasonLabel = (s: number): string => `${s}-${String((s + 1) % 100).padStart(2, "0")}`;

export const COMPETITIONS: Record<string, string> = { euroleague: "EuroLeague" };

/** A source team code as the site shows it (publish.py's DISPLAY_CODES; tests keep the copy in step). */
const displayCode = (competition: string, code: string): string =>
  (codes as Record<string, Record<string, string>>)[competition]?.[code] ?? code;

export const thousands = (x: number): string => Math.round(x).toLocaleString("en-GB");

/** Counts per 100 possessions and shooting percentages: a stat's label, unit and kind. */
interface StatInfo {
  key: string;
  label: string;
  unit: string;
  pct?: boolean;
}

export const PROJECTED: StatInfo[] = [
  { key: "pts", label: "Points", unit: "per 100 possessions" },
  { key: "oreb", label: "Offensive rebounds", unit: "per 100 possessions" },
  { key: "dreb", label: "Defensive rebounds", unit: "per 100 possessions" },
  { key: "ast", label: "Assists", unit: "per 100 possessions" },
  { key: "tov", label: "Turnovers", unit: "per 100 possessions" },
  { key: "stl", label: "Steals", unit: "per 100 possessions" },
  { key: "blk", label: "Blocks", unit: "per 100 possessions" },
  { key: "fg3a", label: "3-point attempts", unit: "per 100 possessions" },
  { key: "fta", label: "Free-throw attempts", unit: "per 100 possessions" },
  { key: "ts", label: "True shooting", unit: "% of shot value", pct: true },
  { key: "fg3", label: "3-point", unit: "% made", pct: true },
  { key: "ft", label: "Free-throw", unit: "% made", pct: true },
];

export const fixed = (x: number, digits = 1): string => (Math.abs(x) < 0.5 * 10 ** -digits ? 0 : x).toFixed(digits).replace(/^-/, "−");
export const percent = (x: number): string => `${fixed(100 * x)}%`;
