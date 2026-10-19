// Helpers for the game page's win-probability line (seasons/{season}/wp.json, stats/wp.py): the
// geometry of the static SVG, the nearest point under a pointer, and the words of the swing list
// and the control table. Probabilities are basis points (10000 = 100%), elapsed is game seconds.

import { clockText } from "./game.ts";

/** One line point: [elapsed, home score, away score, home win probability in basis points]. */
export type WpPoint = [elapsed: number, home: number, away: number, wp: number];

/** One swing: [elapsed, period, clock (s left in the period), home scored (1/0), code, home, away
 * after the play, the home win probability change in basis points]. */
export type WpSwing = [
  elapsed: number,
  period: number,
  clock: number,
  homeScored: number,
  code: string,
  home: number,
  away: number,
  delta: number,
];

export interface WpGame {
  /** The pre-game home win probability at tip-off, basis points. */
  pre: number;
  /** Overtime periods played. */
  ot: number;
  line: WpPoint[];
  swings: WpSwing[];
  /** Five control parts per team, in CONTROL_ORDER. */
  control: { home: number[]; away: number[] };
}

export const REG_SECONDS = 2400;
export const OT_SECONDS = 300;
export const BP = 10000;

/** The control parts in the order wp_control.py writes them. */
export const CONTROL_ORDER = ["dominance", "control", "drama", "comeback", "crunch"] as const;

/** The game's time axis end, in seconds: 2400 plus five minutes per overtime period. */
export function gameEnd(ot: number): number {
  return REG_SECONDS + ot * OT_SECONDS;
}

/** Period and seconds left in it at a game time (regulation 10 min, overtime 5 min). A time on a
 * period boundary reads as the start of the next period, as the clock does. */
export function periodAt(elapsed: number): { period: number; left: number } {
  if (elapsed < REG_SECONDS) {
    const period = Math.floor(elapsed / 600) + 1;
    return { period, left: 600 - (elapsed - (period - 1) * 600) };
  }
  const k = Math.floor((elapsed - REG_SECONDS) / OT_SECONDS);
  return { period: 5 + k, left: OT_SECONDS - (elapsed - REG_SECONDS - k * OT_SECONDS) };
}

/** "Q2 04:31" or "OT1 02:10" for a game time. */
export function gameClock(elapsed: number): string {
  const { period, left } = periodAt(elapsed);
  return clockText(period, Math.round(left));
}

export interface Geometry {
  width: number;
  height: number;
  left: number;
  right: number;
  top: number;
  bottom: number;
  end: number;
}

/** The plot's frame in SVG units. The viewBox is narrow so the 13-unit text stays legible at 390 px. */
export function geometry(ot: number): Geometry {
  return { width: 480, height: 230, left: 44, right: 10, top: 10, bottom: 26, end: gameEnd(ot) };
}

/** Game time to x. */
export function xAt(g: Geometry, elapsed: number): number {
  return g.left + (elapsed / g.end) * (g.width - g.left - g.right);
}

/** Home win probability (basis points) to y: home on top, so 100% is at the top edge. */
export function yAt(g: Geometry, wp: number): number {
  return g.top + (1 - wp / BP) * (g.height - g.top - g.bottom);
}

/** The line as an SVG path: straight segments through the points in game order. */
export function linePath(g: Geometry, points: readonly WpPoint[]): string {
  return points
    .map((p, i) => `${i === 0 ? "M" : "L"}${xAt(g, p[0]).toFixed(1)},${yAt(g, p[3]).toFixed(1)}`)
    .join("");
}

/** Index of the point nearest a game time. Where several points share a second, the last one
 * (the state after every play of that second) wins. */
export function nearestIndex(points: readonly WpPoint[], elapsed: number): number {
  let lo = 0;
  let hi = points.length - 1;
  if (hi < 0) return -1;
  if (elapsed <= points[0][0]) return 0;
  if (elapsed >= points[hi][0]) return hi;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (points[mid][0] <= elapsed) lo = mid;
    else hi = mid - 1;
  }
  // lo is the last point at or before elapsed; the next one wins only when strictly nearer.
  const next = lo + 1 < points.length ? lo + 1 : lo;
  return elapsed - points[lo][0] > points[next][0] - elapsed ? next : lo;
}

/** Percent with no decimals, for a basis-point probability. */
export function percent(bp: number): string {
  return `${Math.round(bp / 100)}%`;
}

/** Signed percentage points, one decimal: a basis-point change of 807 reads "+8.1 pp". */
export function points(bp: number): string {
  const pp = (Math.abs(bp) / 100).toFixed(1);
  return bp > 0 ? `+${pp} pp` : bp < 0 ? `−${pp} pp` : "0.0 pp";
}

/** The words of a play code from the play-by-play (wp_pbp.py SCORING_CODES). */
export function playLabel(code: string): string {
  switch (code) {
    case "3FGM":
      return "Three-point make";
    case "2FGM":
    case "LAYUPMD":
    case "DUNK":
      return "Two-point make";
    case "FTM":
      return "Free throw";
    default:
      return "Scoring play";
  }
}

/** The scoring team's gain from a swing: the home change for a home score, its opposite for away. */
export function swingGain(swing: WpSwing): number {
  return swing[3] === 1 ? swing[7] : -swing[7];
}

/** A control part as shown: dominance signed to two decimals, the rest as the protocol gives them.
 * Control and comeback are shares, shown as percentages. */
export function controlValue(part: (typeof CONTROL_ORDER)[number], value: number): string {
  switch (part) {
    case "dominance":
      return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(2)}`;
    case "control":
    case "comeback":
      return percent(value * BP);
    default:
      return value.toFixed(2);
  }
}

/** The one-line reading of a game's line for screen readers. */
export function lineSummary(home: string, away: string, game: WpGame): string {
  const first = game.line[0];
  const last = game.line[game.line.length - 1];
  const result = last[3] === BP ? `${home} won` : `${away} won`;
  return `${home} win chance starts at ${percent(first[3])} at tip-off. ${result}; the line ends at the result.`;
}
