// Shot heatmaps on the half court: a grid of 0.5 m squares, each shaded from the hex cells around it
// (a Gaussian smoothing, so the map reads as one surface rather than the hexes). Two maps, shown
// one at a time: frequency (how many shots from each spot, in the team's colour, more is stronger)
// and shot making (points per attempt above the league's expectation: teal above, red-orange below).

import { court, DEPTH, num, toY, type HexCell } from "./court";
import { colours, luminance } from "./jersey";

export const SQUARE = 0.5; // metres
const SIGMA = 0.45; // smoothing width, metres
const REACH = 3 * SIGMA; // cells further than this add nothing
const PRIOR = 3; // attempts of shrinkage: a thin spot fades toward zero
export const FULL = 0.5; // points per attempt over expectation at full colour
const THREE_FROM = 6.75; // metres: a make beyond this is worth three
const HALF = 7.5; // half the court's width, metres
const FADE = 0.03; // squares below this share of the peak are left blank

interface Spot {
  x: number;
  y: number;
  att: number;
  made: number;
  league: number; // the league's FG per mille in that cell, or -1 with no league shots there
}

/** One square of the floor: its box in court metres (x across, y from the basket), and the
 * smoothed frequency and quality at its centre. */
export interface Square {
  x: number;
  y: number;
  w: number;
  h: number;
  /** Smoothed attempts (the kernel's sum over nearby cells). */
  freq: number;
  /** Points per attempt above the league's expectation, shrunk toward zero on thin samples. */
  quality: number;
}

/** The hex cells as points: centre in metres from the basket, with the cell's counts. */
function spots(hex: HexCell[], radius: number): Spot[] {
  return hex.map(([q, r, att, made, league]) => ({
    x: radius * Math.sqrt(3) * (q + r / 2),
    y: radius * 1.5 * r,
    att,
    made,
    league,
  }));
}

/** Every square of the floor, row by row from the basket (the last row stops at the depth shown). */
function floor(): { x: number; y: number; w: number; h: number }[] {
  const out: { x: number; y: number; w: number; h: number }[] = [];
  for (let x = -HALF; x < HALF - 1e-9; x += SQUARE) {
    for (let y = 0; y < DEPTH - 1e-9; y += SQUARE) {
      out.push({ x, y, w: SQUARE, h: Math.min(SQUARE, DEPTH - y) });
    }
  }
  return out;
}

/** Smooth the cells onto the floor's squares. Points beyond the reach of a square do not count. */
export function bin(hex: HexCell[], radius: number): Square[] {
  const pts = spots(hex, radius);
  return floor().map(({ x, y, w, h }) => {
    const cx = x + w / 2;
    const cy = y + h / 2;
    let freq = 0;
    let gain = 0; // points above expectation, kernel-weighted
    let weight = 0; // attempts with a league figure, kernel-weighted
    for (const p of pts) {
      const d2 = (p.x - cx) ** 2 + (p.y - cy) ** 2;
      if (d2 > REACH * REACH) continue;
      const k = Math.exp(-d2 / (2 * SIGMA * SIGMA));
      freq += k * p.att;
      if (p.league < 0) continue;
      // A make is worth 3 beyond the arc, 2 inside it; expectation is the league's FG% there.
      const value = Math.hypot(p.x, p.y) > THREE_FROM ? 3 : 2;
      gain += k * value * (p.made - (p.league / 1000) * p.att);
      weight += k * p.att;
    }
    return { x, y, w, h, freq, quality: gain / (weight + PRIOR) };
  });
}

/** Whether a square's centre (court metres) is lit; with no predicate every square is. */
export type Lit = (x: number, y: number) => boolean;

/** A square outside the lit zones is faded to a fifth of its opacity, so the picked zones still read in place. */
const dimming = (s: Square, lit?: Lit): number => (!lit || lit(s.x + s.w / 2, s.y + s.h / 2) ? 1 : 0.2);

/** Squares of one class and one opacity step become a single path: about a fifth of the bytes of one
 * rect per square, which is most of a shot map. Opacity is rounded to steps of 0.05, too fine to see.
 * Each square sits in layer coordinates (y carries the baseline offset, as lib/court.ts). */
function squares(items: { s: Square; cls: string; opacity: number }[]): string {
  const groups = new Map<string, { cls: string; opacity: number; d: string[] }>();
  for (const { s, cls, opacity } of items) {
    const step = Math.round(opacity * 20) / 20;
    const key = `${cls}|${step}`;
    const g = groups.get(key) ?? { cls, opacity: step, d: [] };
    const y = toY(s.y);
    g.d.push(`M${num(s.x)} ${num(y)}h${num(s.w)}v${num(s.h)}h${num(-s.w)}z`);
    groups.set(key, g);
  }
  return [...groups.values()]
    .map((g) => `<path class="${g.cls}" fill-opacity="${num(g.opacity)}" d="${g.d.join("")}"/>`)
    .join("");
}

/** The busiest square's smoothed attempts, rounded: the frequency key's "up to x per area". */
export function peakShots(hex: HexCell[], radius: number): number {
  return Math.round(Math.max(0, ...bin(hex, radius).map((s) => s.freq)));
}

/** Frequency: one hue, stronger where he shot more. Shaded against the busiest square. */
export function freqHeat(hex: HexCell[], radius: number, label: string, lit?: Lit): string {
  const sq = bin(hex, radius);
  const top = Math.max(0, ...sq.map((s) => s.freq));
  const items = top
    ? sq
        .filter((s) => s.freq / top >= FADE)
        .map((s) => ({ s, cls: "hf", opacity: Math.min(0.92, (s.freq / top) ** 0.6) * dimming(s, lit) }))
    : [];
  return court(`<g class="heat">${squares(items)}</g>`, label);
}

/** Black and grey: no hue and too dark (black) or too neutral (grey) to carry a make. White is not one. */
const neutralDark = (hex: string) => achromatic(hex) && luminance(hex) < 0.7;

/** A dark colour that is still a hue (navy, dark blue): dark, but with a clear colour. */
const darkHue = (hex: string) => !achromatic(hex) && luminance(hex) < 0.05;

/** Dark enough that a make or miss in it would vanish on the court: black, grey or navy. */
const dark = (hex: string) => luminance(hex) < 0.05 || neutralDark(hex);

/** The colour mixed toward white by `t` (0 to 1): a dark hue lightened enough to read on the paper. */
function lighten(hex: string, t: number): string {
  const n = parseInt(hex.slice(1), 16);
  const mix = (c: number) => Math.round(c + (255 - c) * t);
  const [r, g, b] = [mix((n >> 16) & 255), mix((n >> 8) & 255), mix(n & 255)];
  return `#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

/** The colours of a club's shots. Makes take the main colour. Black and grey mains give way to the
 * secondary; a navy or dark-blue main is lightened so it reads. Misses take the secondary, or a neutral
 * ring when the secondary is dark or when the makes already use it, so the two always read apart. The
 * frequency squares use the make colour. A club with dark colours in both falls back to the page's ink,
 * which flips with the theme. */
export function shotPair(code: string | undefined): { make: string; miss: string } {
  const [primary, secondary] = colours(code ?? "");
  const givesWay = neutralDark(primary);
  const fallback = "var(--ink-2)";
  const make = givesWay
    ? dark(secondary)
      ? fallback
      : secondary
    : darkHue(primary)
      ? lighten(primary, 0.3)
      : primary;
  const miss = givesWay || dark(secondary) ? fallback : secondary;
  return { make: ink(make), miss: ink(miss) };
}

/** A near-white or near-black colour would vanish on one of the two themes: it becomes the page's ink,
 * which is dark on light and light on dark. */
const ink = (c: string) =>
  c.startsWith("var(") ? c : luminance(c) >= 0.7 || luminance(c) < 0.05 ? "var(--ink-2)" : c;

/** The team's colour for the frequency squares and the player page's accents: the make colour. */
export function teamColour(code: string | undefined): string {
  return shotPair(code).make;
}

/** Near-grey colours (black, white, grey): little spread between the red, green and blue channels. */
function achromatic(hex: string): boolean {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return Math.max(r, g, b) - Math.min(r, g, b) < 40;
}

/** Shot making: teal where the spot scores more than the league's shots from it, red-orange where less. */
export function qualityHeat(hex: HexCell[], radius: number, label: string, lit?: Lit): string {
  const items = bin(hex, radius)
    .filter((s) => Math.abs(s.quality) / FULL >= FADE)
    .map((s) => {
      const strength = Math.min(1, Math.abs(s.quality) / FULL);
      return { s, cls: s.quality > 0 ? "hq pos" : "hq neg", opacity: Math.min(0.92, strength ** 0.8) * dimming(s, lit) };
    });
  return court(`<g class="heat">${squares(items)}</g>`, label);
}
