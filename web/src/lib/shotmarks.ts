// Player-page shot charts built on the shared court (lib/court.ts): one mark per attempt (a filled
// circle for a make, a cross for a miss). The heatmaps (lib/heat.ts) sit beside it on the page.

import { court, DEPTH } from "./court";

const BASELINE = 1.575; // metres from the basket to the baseline, as lib/court.ts

/** Which attempts to show: all, two-pointers only, or threes only. */
export type ShotFilter = "all" | "2" | "3";

/** Whether attempt `i` (a stride-4 index into `dots`) passes the filter. */
const keep = (dots: number[], i: number, filter: ShotFilter): boolean =>
  filter === "all" || dots[i + 3] === (filter === "3" ? 1 : 0);

/**
 * `dots` is flat [x, y, made, three] in court centimetres. Misses are drawn first, so makes stay
 * on top. `filter` keeps only two-pointers ("2") or threes ("3"); "all" (the default) keeps all.
 */
export function markChart(dots: number[], label: string, filter: ShotFilter = "all"): string {
  const made: string[] = [];
  const miss: string[] = [];
  const r = 0.14;
  const d = 0.11;
  for (let i = 0; i < dots.length; i += 4) {
    if (!keep(dots, i, filter)) continue;
    const x = dots[i] / 100;
    const y = dots[i + 1] / 100;
    if (y > DEPTH || Math.abs(x) > 7.5) continue;
    const cy = y + BASELINE;
    if (dots[i + 2]) made.push(`M${(x - r).toFixed(2)} ${cy.toFixed(2)}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`);
    else miss.push(`M${(x - d).toFixed(2)} ${(cy - d).toFixed(2)}l${2 * d} ${2 * d}m${-2 * d} 0l${2 * d} ${-2 * d}`);
  }
  return court(`<path class="xmiss" d="${miss.join("")}"/><path class="made" d="${made.join("")}"/>`, label);
}

/** "N located attempts, M made" over the attempts that pass `filter` ("all" by default). */
export const countLine = (dots: number[], filter: ShotFilter = "all"): string => {
  let attempts = 0;
  let made = 0;
  for (let i = 0; i < dots.length; i += 4) {
    if (!keep(dots, i, filter)) continue;
    attempts++;
    made += dots[i + 2];
  }
  return `${attempts} located attempts, ${made} made`;
};

export const dotLabel = (season: string, dots: number[]): string => `${season} shot chart: ${countLine(dots)}`;
