// Player-page shot charts built on the shared court (lib/court.ts): one mark per attempt (a filled
// circle for a make, a cross for a miss) and the hexes shaded by how often he shot from each cell.

import { court, DEPTH, hexChart, type HexCell } from "./court";
import { tip } from "./tip";

const BASELINE = 1.575; // metres from the basket to the baseline, as lib/court.ts

/** `dots` is flat [x, y, made] in court centimetres. Misses are drawn first, so makes stay on top. */
export function markChart(dots: number[], label: string): string {
  const made: string[] = [];
  const miss: string[] = [];
  const r = 0.14;
  const d = 0.11;
  for (let i = 0; i < dots.length; i += 3) {
    const x = dots[i] / 100;
    const y = dots[i + 1] / 100;
    if (y > DEPTH || Math.abs(x) > 7.5) continue;
    const cy = y + BASELINE;
    if (dots[i + 2]) made.push(`M${(x - r).toFixed(2)} ${cy.toFixed(2)}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`);
    else miss.push(`M${(x - d).toFixed(2)} ${(cy - d).toFixed(2)}l${2 * d} ${2 * d}m${-2 * d} 0l${2 * d} ${-2 * d}`);
  }
  return court(`<path class="xmiss" d="${miss.join("")}"/><path class="made" d="${made.join("")}"/>`, label);
}

/** Five steps of one orange ramp by how busy the cell is against the busiest. */
export const freqStep = (att: number, most: number): string => {
  const r = att / most;
  return r >= 0.6 ? "f5" : r >= 0.3 ? "f4" : r >= 0.15 ? "f3" : r >= 0.06 ? "f2" : "f1";
};

export function freqChart(hex: HexCell[], radius: number, label: string): string {
  const most = Math.max(1, ...hex.map((c) => c[2]));
  const total = hex.reduce((a, c) => a + c[2], 0);
  return hexChart(hex, radius, {
    label,
    color: (c) => freqStep(c[2], most),
    tip: (c) => tip`<b>${c[2]} attempt${c[2] === 1 ? "" : "s"}</b>, ${((100 * c[2]) / total).toFixed(1)}% of his shots<br>${c[3]} made`,
  });
}

export const countLine = (dots: number[]): string => {
  let made = 0;
  for (let i = 2; i < dots.length; i += 3) made += dots[i];
  return `${dots.length / 3} located attempts, ${made} made`;
};

export const dotLabel = (season: string, dots: number[]): string => `${season} shot chart: ${countLine(dots)}`;
