// Pure helpers for the game page: one team's box score from the player game logs, the clock labels
// and the phase names. Logs and runs come from stats/seasons/{y}/games.json and runs.json.

export type Pair = [made: number, att: number];

/** The box score's columns, as totals (one player's line, or a team's sum of lines). */
export interface BoxStats {
  sec: number;
  pts: number;
  reb: number;
  ast: number;
  stl: number;
  blk: number;
  tov: number;
  pf: number;
  pm: number;
  fg: Pair;
  tp: Pair;
  ft: Pair;
}

export interface BoxLine extends BoxStats {
  id: string;
  name: string;
  slug: string;
  starter: boolean;
}

/** One player's game-log line, keyed by his id (games.json keeps the logs by player). */
export interface LogEntry {
  id: string;
  line: (string | number)[];
}

export interface PersonRef {
  name: string;
  slug: string;
}

const EMPTY: BoxStats = {
  sec: 0,
  pts: 0,
  reb: 0,
  ast: 0,
  stl: 0,
  blk: 0,
  tov: 0,
  pf: 0,
  pm: 0,
  fg: [0, 0],
  tp: [0, 0],
  ft: [0, 0],
};

/** A log line's box columns, read by the names in the season's log_fields. */
export function lineStats(fields: string[], line: (string | number)[]): BoxStats {
  const num = (name: string) => Number(line[fields.indexOf(name)] ?? 0);
  return {
    sec: num("sec"),
    pts: num("pts"),
    reb: num("oreb") + num("dreb"),
    ast: num("ast"),
    stl: num("stl"),
    blk: num("blk"),
    tov: num("tov"),
    pf: num("pf"),
    pm: num("pm"),
    fg: [num("fg2m") + num("fg3m"), num("fg2a") + num("fg3a")],
    tp: [num("fg3m"), num("fg3a")],
    ft: [num("ftm"), num("fta")],
  };
}

function sum(a: BoxStats, b: BoxStats): BoxStats {
  return {
    sec: a.sec + b.sec,
    pts: a.pts + b.pts,
    reb: a.reb + b.reb,
    ast: a.ast + b.ast,
    stl: a.stl + b.stl,
    blk: a.blk + b.blk,
    tov: a.tov + b.tov,
    pf: a.pf + b.pf,
    pm: a.pm + b.pm,
    fg: [a.fg[0] + b.fg[0], a.fg[1] + b.fg[1]],
    tp: [a.tp[0] + b.tp[0], a.tp[1] + b.tp[1]],
    ft: [a.ft[0] + b.ft[0], a.ft[1] + b.ft[1]],
  };
}

/**
 * One team's box score in one game. The team's totals are the sum of every line of that team; the
 * player list leaves out anyone with no minutes, starters first, then by minutes.
 */
export function gameBox(
  fields: string[],
  entries: LogEntry[],
  team: string,
  people: Record<string, PersonRef>,
): { players: BoxLine[]; totals: BoxStats } {
  const teamAt = fields.indexOf("team");
  const startAt = fields.indexOf("starter");
  const mine = entries.filter((e) => String(e.line[teamAt]) === team);
  const totals = mine.reduce((acc, e) => sum(acc, lineStats(fields, e.line)), EMPTY);
  const players = mine
    .map((e) => ({ e, stats: lineStats(fields, e.line) }))
    .filter(({ stats }) => stats.sec > 0)
    .map(({ e, stats }) => {
      const who = people[e.id];
      return {
        ...stats,
        id: e.id,
        name: who?.name ?? e.id,
        slug: who?.slug ?? "",
        starter: Number(e.line[startAt]) === 1,
      };
    })
    .sort((a, b) => Number(b.starter) - Number(a.starter) || b.sec - a.sec || a.name.localeCompare(b.name));
  return { players, totals };
}

/** Period number -> "Q1".."Q4", then "OT1", "OT2", ... */
export function periodName(period: number): string {
  return period <= 4 ? `Q${period}` : `OT${period - 4}`;
}

/** A run's clock: the period and the time left in it, "Q2 04:31" (--:-- when the row had no clock). */
export function clockText(period: number, left: number | null): string {
  if (left === null) return `${periodName(period)} --:--`;
  const m = Math.floor(left / 60);
  const s = left % 60;
  return `${periodName(period)} ${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** The phase code of games.json as a page label. */
export function phaseLabel(phase: string, round: number): string {
  switch (phase) {
    case "RS":
      return `Regular season, round ${round}`;
    case "PI":
      return "Play-in";
    case "PO":
      return "Playoffs";
    case "TS":
      return "Top 16";
    case "FF":
      return "Final Four";
    default:
      return phase;
  }
}
