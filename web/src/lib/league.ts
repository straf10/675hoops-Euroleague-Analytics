// "Against the league" on the player page: his per-game figures in six key metrics against the
// players who play real minutes that season, and his rank in the league and among his position.
// Pure; built from seasons/{season}/players.json at build time. The ranking itself is in ./league_rank.ts.

import { betterOf, type BetterIs } from "./better";
import { BY_KEY, rated, type Measure } from "./players";
import { rankLeague, type LeagueLine, type PositionPool } from "./league_rank";
import type { PlayerRow, SeasonPlayers } from "./stats";

/** The six metrics, in order. Usage is a style measure (no better side, see `betterOf`). */
export const KEY_METRICS: string[] = ["pts", "reb", "ast", "ts", "usg", "pir"];

/** Minutes a game to be counted, and a quarter of the most games anyone played (the dashboard's rule). */
export const FLOOR_MINUTES = 10;
/** Whatever the quarter-of-the-most rule gives, a line needs at least this many games. */
export const MIN_FLOOR_GAMES = 5;

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
  /** Mean of the league pool. */
  league: number;
  /** His rank in the league pool (1 is best), null when not counted. */
  rank: number | null;
  /** Players counted in the league pool. */
  of: number;
  /** His position's mean and rank (lib/league_rank.ts); null without a listed position. */
  position: PositionPool | null;
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

/** The value of a metric for a player's season totals, or null when he does not qualify for it. */
function valueOf(key: string, t: Record<string, number>): number | null {
  const m = BY_KEY[key];
  return (m.qualifies?.(t) ?? true) ? rated(m, t, "game") : null;
}

/** null when he is not in the pool (too few games or minutes) or no metric counts him. */
export function leagueBoard(data: SeasonPlayers, id: string): LeagueBoard | null {
  const lines = data.players.map((row: PlayerRow) => ({ row, t: totalsOf(data.fields, row.totals.season) }));
  const most = Math.max(0, ...lines.map((l) => l.t.gp));
  const floorGames = Math.max(MIN_FLOOR_GAMES, Math.ceil(most / 4));
  const pool = lines.filter((l) => l.t.gp >= floorGames && l.t.sec / l.t.gp / 60 >= FLOOR_MINUTES);
  if (!pool.some((l) => l.row.id === id)) return null;

  const ranks = rankLeague(
    pool.map((l): LeagueLine => ({
      id: l.row.id,
      pos: l.row.pos ?? null,
      values: Object.fromEntries(KEY_METRICS.map((key) => [key, valueOf(key, l.t)])),
    })),
    id,
    KEY_METRICS,
    (key) => (betterOf(key) === "lower" ? "lower" : "higher"),
  );

  const boards: MetricBoard[] = [];
  for (const key of KEY_METRICS) {
    const r = ranks[key];
    if (!r) continue;
    const m = BY_KEY[key];
    const values = pool.map((l) => valueOf(key, l.t)).filter((v): v is number => v !== null);
    const [lo, hi] = niceBounds(m, values);
    boards.push({
      key,
      head: m.head,
      name: m.name,
      about: m.about,
      digits: m.digits,
      pct: m.kind === "pct",
      better: betterOf(key),
      mine: r.mine,
      league: r.league.average,
      rank: r.league.rank,
      of: r.league.of,
      position: r.position,
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
