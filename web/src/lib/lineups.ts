// Best duos and five-man units of a club, from seasons/{season}/units.json (stats/units.py).
// Pure: the rows, the sort and the range. Markup is in lineups_html.ts.

/** A pair row: [id, id, minutes, possessions, points for, points against, net, ci]. */
/** A unit row: [id x5, minutes, possessions, points for, points against, net, ci]. */
export type LineupRow = (string | number)[];

export interface UnitsClub {
  pairs: LineupRow[];
  units: LineupRow[];
}

export interface UnitsFile {
  season: number;
  minimums: { pair: number; unit: number };
  /** Points per possession behind each ci (a rough noise figure). */
  sd: number;
  clubs: Record<string, UnitsClub>;
}

/** One duo or unit, read from its row. `ci` is the rough 95% half-width of `net`. */
export interface Line {
  ids: string[];
  minutes: number;
  poss: number;
  pf: number;
  pa: number;
  net: number;
  ci: number;
}

export type LineupSort = "minutes" | "net";

export const PAIR_SIZE = 2;
export const UNIT_SIZE = 5;

/** The rows of a file as lines: `size` player ids, then the six numbers. */
export function lines(rows: LineupRow[], size: number): Line[] {
  return rows.map((r) => ({
    ids: r.slice(0, size).map(String),
    minutes: Number(r[size]),
    poss: Number(r[size + 1]),
    pf: Number(r[size + 2]),
    pa: Number(r[size + 3]),
    net: Number(r[size + 4]),
    ci: Number(r[size + 5]),
  }));
}

/** The 95% range of a net rating, as low and high (net minus and plus ci). */
export function range(line: Line): { low: number; high: number } {
  return { low: line.net - line.ci, high: line.net + line.ci };
}

/** Sorts by net rating or by minutes, largest first; the other key breaks a tie, then the ids. */
export function sortLines(list: Line[], by: LineupSort): Line[] {
  const other: LineupSort = by === "net" ? "minutes" : "net";
  return [...list].sort(
    (a, b) =>
      b[by] - a[by] || b[other] - a[other] || a.ids.join(",").localeCompare(b.ids.join(","))
  );
}

/** Season -> the club's rows in that season, from the published files. */
export interface ClubSeason {
  sd: number;
  minimums: { pair: number; unit: number };
  pairs: LineupRow[];
  units: LineupRow[];
}
export type ClubUnits = Record<string, ClubSeason>;
