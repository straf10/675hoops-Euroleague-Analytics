// The rank and average of one player among the league pool and his position's pool, for each key.
// Pure (imports only ./percentile.ts and ./position.ts, so Node runs it for the tests, as
// percentile.ts). lib/league.ts turns these into the Against-the-league boards.

import { rankPool, type PoolRow } from "./percentile.ts";
import { position, type Position } from "./position.ts";

/** One pool line: a player's value per key (null when he is not counted there) and his listed position. */
export interface LeagueLine {
  id: string;
  /** "G" | "F" | "C" from the listing, or null when he has none that season. */
  pos: string | null;
  values: Record<string, number | null | undefined>;
}

export interface PositionPool {
  /** Lower-case plural: "guards", "forwards" or "centres". */
  name: string;
  /** Mean of the position's counted values in this key. */
  average: number;
  /** His rank among the position (1 is best), null when he is not counted in this key. */
  rank: number | null;
  /** Players of the position counted in this key. */
  of: number;
}

export interface KeyRanks {
  /** His value; null when he is not counted in this key. */
  mine: number | null;
  league: {
    /** Mean of every counted player in this key. */
    average: number;
    /** His rank in the league pool (1 is best), null when he is not counted in this key. */
    rank: number | null;
    /** Players counted in this key. */
    of: number;
  };
  /** Null when he has no listed position or none of his position is counted in this key. */
  position: PositionPool | null;
}

const PLURAL: Record<Position, string> = { Guard: "guards", Forward: "forwards", Centre: "centres" };

const usable = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

/** The ranks of `id` in each key the pool counts, keyed by key. Keys nobody counts are left out. */
export function rankLeague(
  lines: LeagueLine[],
  id: string,
  keys: string[],
  better: (key: string) => "higher" | "lower",
): Record<string, KeyRanks> {
  const out: Record<string, KeyRanks> = {};
  const mine = lines.find((l) => l.id === id);
  if (!mine) return out;
  const rows: PoolRow[] = lines.map((l) => ({ id: l.id, group: l.pos, values: l.values }));
  const league = rankPool(rows, keys, better);
  const pos = position(mine.pos);
  const byPos = pos ? rankPool(rows, keys, better, { group: mine.pos }) : null;

  for (const key of keys) {
    const values = lines.map((l) => l.values[key]).filter(usable);
    if (!values.length) continue;
    const own = mine.values[key];
    const among = pos ? lines.filter((l) => l.pos === mine.pos).map((l) => l.values[key]).filter(usable) : [];
    const placed = byPos?.get(id)?.[key] ?? null;
    out[key] = {
      mine: usable(own) ? own : null,
      league: { average: mean(values), rank: league.get(id)?.[key]?.rank ?? null, of: values.length },
      position: pos && among.length ? { name: PLURAL[pos], average: mean(among), rank: placed?.rank ?? null, of: among.length } : null,
    };
  }
  return out;
}
