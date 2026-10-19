// Percentiles and ranks of rows within a pool, one metric (key) at a time. Pure: the only imports
// are types, so Node runs this file directly (`node --test src/lib/`). Which way is "better" is
// the caller's to say (`betterOf` in ./better.ts, for the site's metrics).
//
// Conventions
// - A row whose value is null, undefined, NaN or infinite is left out of that key's pool and gets
//   null for that key. A row outside `opts.group` gets null for every key.
// - `pct` runs from 0 (worst in the pool) to 100 (best), and is oriented so that 100 is best for
//   the key, whatever its direction. Tied values share the mean of their positions, so a tie sits
//   between the two spans it covers. A lone value in its pool is 100 (best and worst at once).
//   The positions are spread over the whole pool: pct = (strictly worse + ½·(ties − 1)) / (n − 1) · 100.
// - `rank` is competition ranking, 1 = best: tied values share a rank and the next rank skips
//   (values 4, 2, 2, 1 rank 1, 2, 2, 4).
// - `of` is the pool size for that key (rows in the group with a usable value).
// - Output has one entry per input row, in input order, and each entry has every requested key in
//   the order given. Row ids should be unique; a repeated id overwrites the earlier entry.
// - O(n log n) per key: one sort, then a binary search per row.

/** The direction of a metric: which end of its scale is good. */
type Better = "higher" | "lower";

export interface PoolRow {
  id: string;
  /** Optional pool label, such as a position. Used only with `opts.group`. */
  group?: string | null;
  values: Record<string, number | null | undefined>;
}

export interface Placement {
  /** 0 (worst in the pool) to 100 (best), oriented so 100 is best for the key. */
  pct: number;
  /** 1 is best; tied values share a rank and the next rank skips. */
  rank: number;
  /** Pool size for this key. */
  of: number;
}

export type Placements = Map<string, Record<string, Placement | null>>;

interface RankOptions {
  /** Restrict the pool to rows whose group equals this (`null` means rows with no group). Left
   * undefined, the pool is every row. */
  group?: string | null;
}

const usable = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** Index of the first element not below `x` (count of elements strictly less than `x`). */
function lowerBound(sorted: number[], x: number): number {
  let lo = 0;
  let hi = sorted.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] < x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Index of the first element above `x` (count of elements less than or equal to `x`). */
function upperBound(sorted: number[], x: number): number {
  let lo = 0;
  let hi = sorted.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] <= x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Percentile and rank of every row on every key, within its pool. `better(key)` says which end
 * of the key's scale is good. For a key with no better side, the caller passes "higher" and ignores
 * the result. */
export function rankPool(
  rows: PoolRow[],
  keys: string[],
  better: (key: string) => Better,
  opts: RankOptions = {},
): Placements {
  const pool = rows.filter((row) => opts.group === undefined || (row.group ?? null) === opts.group);
  const out: Placements = new Map();
  for (const row of rows) {
    out.set(row.id, Object.fromEntries(keys.map((key) => [key, null])));
  }

  for (const key of keys) {
    const dir = better(key);
    const scored: { id: string; v: number }[] = [];
    for (const row of pool) {
      const v = row.values[key];
      if (usable(v)) scored.push({ id: row.id, v });
    }
    const sorted = scored.map((s) => s.v).sort((a, b) => a - b);
    const n = sorted.length;

    for (const { id, v } of scored) {
      const below = lowerBound(sorted, v);
      const tied = upperBound(sorted, v) - below;
      const above = n - below - tied;
      const worse = dir === "higher" ? below : above; // rows this value beats
      const better_ = dir === "higher" ? above : below; // rows strictly ahead of it
      const pct = n === 1 ? 100 : ((worse + 0.5 * (tied - 1)) / (n - 1)) * 100;
      const slot = out.get(id);
      if (slot) slot[key] = { pct, rank: 1 + better_, of: n };
    }
  }
  return out;
}
