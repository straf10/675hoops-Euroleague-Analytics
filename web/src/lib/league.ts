// "Against the league" on the player page: his per-game figures in six key metrics against the
// players who play real minutes that season, and the season's top ten in each. Pure; built from
// seasons/{season}/players.json at build time.

import type { BetterIs } from "./delta";
import { BY_KEY, rated, type Measure } from "./players";
import type { PlayerRow, SeasonPlayers } from "./stats";

/** The six metrics, in order. Usage is a style measure: its arrow stays ink. */
export const KEY_METRICS: { key: string; better: BetterIs }[] = [
  { key: "pts", better: "higher" },
  { key: "reb", better: "higher" },
  { key: "ast", better: "higher" },
  { key: "ts", better: "higher" },
  { key: "usg", better: "neither" },
  { key: "pir", better: "higher" },
];

/** Minutes a game to be counted, and a quarter of the most games anyone played (the dashboard's rule). */
export const FLOOR_MINUTES = 10;

export interface BoardRow {
  rank: number;
  slug: string;
  name: string;
  team: string;
  value: number;
}

export interface MetricBoard {
  key: string;
  head: string;
  name: string;
  about: string;
  digits: number;
  pct: boolean;
  better: BetterIs;
  /** His value; null when he is not counted in this metric. */
  mine: number | null;
  league: number;
  rank: number | null;
  of: number;
  top: BoardRow[];
  /** Him as an extra row (with his own rank) when he is outside the top ten. */
  extra: BoardRow | null;
  /** Rail scale. */
  lo: number;
  hi: number;
}

export interface LeagueBoard {
  floorGames: number;
  floorMinutes: number;
  boards: MetricBoard[];
}

const totalsOf = (fields: string[], values: number[]) => Object.fromEntries(fields.map((f, i) => [f, values[i]]));

function niceBounds(measure: Measure, values: number[]): [number, number] {
  const hi = Math.max(...values);
  const lo = Math.min(...values);
  if (measure.kind !== "pct") return [0, Math.ceil(hi)];
  return [Math.floor(lo / 5) * 5, Math.ceil(hi / 5) * 5];
}

/** null when he is not in the pool (too few games or minutes) or no metric counts him. */
export function leagueBoard(data: SeasonPlayers, id: string, topN = 10): LeagueBoard | null {
  const lines = data.players.map((row: PlayerRow) => ({ row, t: totalsOf(data.fields, row.totals.season) }));
  const most = Math.max(0, ...lines.map((l) => l.t.gp));
  const floorGames = Math.ceil(most / 4);
  const pool = lines.filter((l) => l.t.gp >= Math.max(1, floorGames) && l.t.sec / l.t.gp / 60 >= FLOOR_MINUTES);
  if (!pool.some((l) => l.row.id === id)) return null;

  const boards: MetricBoard[] = [];
  for (const { key, better } of KEY_METRICS) {
    const m = BY_KEY[key];
    const ranked = pool
      .filter((l) => m.qualifies?.(l.t) ?? true)
      .map((l) => ({ l, value: rated(m, l.t, "game") }))
      .filter((r): r is { l: (typeof pool)[number]; value: number } => r.value !== null)
      .sort((a, b) => b.value - a.value || a.l.row.name.localeCompare(b.l.row.name));
    if (!ranked.length) continue;
    const row = (r: (typeof ranked)[number], at: number): BoardRow => ({
      rank: at + 1,
      slug: r.l.row.slug,
      name: r.l.row.name,
      team: r.l.row.teams[r.l.row.teams.length - 1] ?? "",
      value: r.value,
    });
    const at = ranked.findIndex((r) => r.l.row.id === id);
    const values = ranked.map((r) => r.value);
    const [lo, hi] = niceBounds(m, values);
    boards.push({
      key,
      head: m.head,
      name: m.name,
      about: m.about,
      digits: m.digits,
      pct: m.kind === "pct",
      better,
      mine: at >= 0 ? ranked[at].value : null,
      league: values.reduce((a, b) => a + b, 0) / values.length,
      rank: at >= 0 ? at + 1 : null,
      of: ranked.length,
      top: ranked.slice(0, topN).map(row),
      extra: at >= topN ? row(ranked[at], at) : null,
      lo,
      hi: hi > lo ? hi : lo + 1,
    });
  }
  return boards.some((b) => b.mine !== null) ? { floorGames, floorMinutes: FLOOR_MINUTES, boards } : null;
}

export const ordinal = (n: number): string => {
  const r = n % 100;
  if (r >= 11 && r <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10 > 3 ? 0 : n % 10]}`;
};
