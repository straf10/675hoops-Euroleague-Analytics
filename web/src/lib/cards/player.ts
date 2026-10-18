// Player card (1080 x 1350) for a player in the live season. Every section is drawn from data the
// player page shows: the projection with its 80% interval (lib/m6.ts), the attempts of his shot
// season (`dots`, court centimetres), and the shot twins. A section with no data is left out.
// Layout follows the approved demo (player-card.html).

import { fixed, percent } from "../m6";
import {
  AXIS,
  BLUE,
  INK,
  INK_SOFT,
  MUTED,
  ORANGE,
  RULE,
  RULE_STRONG,
  SURFACE,
  canvas,
  circle,
  fitSize,
  footer,
  line,
  logo,
  text,
} from "./draw";

/** One projected rate: its central estimate and 80% interval. */
export interface CardRate {
  label: string;
  /** Shown beside the label, e.g. "per 100 possessions". */
  unit: string;
  pct: boolean;
  mean: number;
  lo80: number;
  hi80: number;
}

export interface CardTwin {
  name: string;
  /** "Partizan · 2017-18" style. */
  club: string;
  /** Similarity in [0, 1]. */
  score: number;
}

export interface PlayerCardInput {
  name: string;
  /** The clubs of his live season, as the page names them, and his position when listed. */
  club: string;
  position: string | null;
  /** The live season, e.g. "2026-27". */
  season: string;
  projection: { season: string; rates: CardRate[] } | null;
  shots: { season: string; dots: number[] } | null;
  twins: { query: string; list: CardTwin[] } | null;
}

const W = 1080;
const H = 1350;
const X0 = 72;
const X1 = 1008;
const RX = 540;

// Court geometry: the site's court (lib/court.ts), at 28 px to the metre, the baseline at the top
// and the basket 1.575 m below it. Depth is cut at 10 m from the basket, as the shot charts do.
const S = 28;
const BASELINE = 1.575;
const DEPTH = 10;
const CX = X0 + (15 * S) / 2;
const CY0 = 812;
const COURT_H = (DEPTH + BASELINE) * S;
const by = CY0 + BASELINE * S;

function court(): string {
  const ftY = CY0 + 5.8 * S;
  const arcY = Math.sqrt(6.75 ** 2 - 6.6 ** 2);
  const r3 = 6.75 * S;
  const dx = 6.6 * S;
  const yArc = by + arcY * S;
  return [
    `<rect x="${X0}" y="${CY0}" width="${15 * S}" height="${COURT_H}" fill="${SURFACE}"/>`,
    `<path d="M${CX - 2.45 * S},${CY0} V${ftY} H${CX + 2.45 * S} V${CY0}" fill="none" stroke="${AXIS}" stroke-width="1.2"/>`,
    `<path d="M${CX - 1.8 * S},${ftY} A${1.8 * S},${1.8 * S} 0 0 0 ${CX + 1.8 * S},${ftY}" fill="none" stroke="${AXIS}" stroke-width="1.2"/>`,
    `<path d="M${CX - 1.25 * S},${by} A${1.25 * S},${1.25 * S} 0 0 0 ${CX + 1.25 * S},${by}" fill="none" stroke="${AXIS}" stroke-width="1.2"/>`,
    `<path d="M${CX - dx},${CY0} V${yArc} A${r3},${r3} 0 0 0 ${CX + dx},${yArc} V${CY0}" fill="none" stroke="${AXIS}" stroke-width="1.5"/>`,
    `<rect x="${X0}" y="${CY0}" width="${15 * S}" height="${COURT_H}" fill="none" stroke="${AXIS}" stroke-width="1.5"/>`,
    line(CX - 0.9 * S, CY0 + 1.2 * S, CX + 0.9 * S, CY0 + 1.2 * S, INK, 3),
    `<circle cx="${CX}" cy="${by}" r="${0.225 * S}" fill="none" stroke="${INK}" stroke-width="2.2"/>`,
  ].join("");
}

/** Attempts (flat [x, y, made, three] stride 4) as the player page draws them: a filled orange dot
 * for a make, a blue cross for a miss.
 * Misses go first so the makes sit on top. */
function marks(dots: number[]): string {
  const misses: string[] = [];
  const makes: string[] = [];
  const d = 0.16 * S;
  const r = 0.2 * S;
  for (let i = 0; i < dots.length; i += 4) {
    const x = dots[i] / 100;
    const y = dots[i + 1] / 100;
    if (y > DEPTH || Math.abs(x) > 7.5) continue;
    const px = CX + x * S;
    const py = CY0 + (y + BASELINE) * S;
    if (dots[i + 2]) makes.push(circle(px, py, r, ORANGE));
    else
      misses.push(
        `<path d="M${(px - d).toFixed(1)},${(py - d).toFixed(1)} l${2 * d},${2 * d} m${-2 * d},0 l${2 * d},${-2 * d}" fill="none" stroke="${BLUE}" stroke-width="2" stroke-linecap="round"/>`,
      );
  }
  return misses.join("") + makes.join("");
}

/** Projected rates: a bar for the 80% interval, a dot at the projection. */
function rateRow(top: number, rate: CardRate, fmt: (x: number) => string): string {
  const pad = (rate.hi80 - rate.lo80) * 0.1 || 1;
  const lo = rate.lo80 - pad;
  const hi = rate.hi80 + pad;
  const sx = (v: number) => X0 + ((v - lo) / (hi - lo)) * (700 - X0);
  const ty = top + 62;
  const label = rate.unit ? `${rate.label}, ${rate.unit}` : rate.label;
  return [
    text(X0, top + 34, label, { size: 24, weight: 500 }),
    line(X0, ty, 700, ty, RULE_STRONG, 2),
    `<line x1="${sx(rate.lo80).toFixed(1)}" y1="${ty}" x2="${sx(rate.hi80).toFixed(1)}" y2="${ty}" stroke="${ORANGE}" stroke-width="10" stroke-linecap="round" stroke-opacity="0.35"/>`,
    circle(sx(rate.mean), ty, 9, ORANGE),
    text(740, top + 60, fmt(rate.mean), { size: 40, weight: 600, track: -0.02 }),
    text(740, top + 88, `80% interval ${fmt(rate.lo80)} to ${fmt(rate.hi80)}`, { size: 20, fill: INK_SOFT }),
  ].join("");
}

const rateText = (r: CardRate) => (x: number) => (r.pct ? percent(x) : fixed(x));

export function playerSvg(p: PlayerCardInput): string {
  const b: string[] = [];
  b.push(logo(X0, 34));
  b.push(text(X1, 66, `${p.season} season`, { size: 22, fill: MUTED, anchor: "end" }));
  const nameSize = fitSize(p.name, 96, X1 - X0, -0.03);
  b.push(text(X0, 196, p.name, { size: nameSize, weight: 620, track: -0.03 }));
  const facts = p.position ? `${p.club}  ·  ${p.position}` : p.club;
  b.push(text(X0, 246, facts, { size: 28, fill: INK_SOFT }));
  b.push(line(X0, 280, X1, 280, RULE_STRONG, 1.5));

  if (p.projection && p.projection.rates.length) {
    b.push(text(X0, 336, `${p.projection.season} projection, 80% interval`, { size: 30, weight: 600 }));
    b.push(text(X0, 364, "The dot is the projection; the bar is its 80% interval.", { size: 20, fill: MUTED }));
    p.projection.rates.slice(0, 3).forEach((r, i) => b.push(rateRow(400 + i * 110, r, rateText(r))));
  }

  if (p.shots) {
    const made = countMade(p.shots.dots);
    const attempts = p.shots.dots.length / 4;
    b.push(text(X0, 760, `Shot chart, ${p.shots.season}`, { size: 30, weight: 600 }));
    b.push(text(X0, 788, "Filled: made. Cross: missed. Half court, basket at top.", { size: 20, fill: MUTED }));
    b.push(court());
    b.push(marks(p.shots.dots));
    if (p.twins) b.push(twinBlock(p.twins, attempts, made));
    else b.push(text(RX, CY0 + 40, `${attempts} located attempts, ${made} made, FG ${pct1(made, attempts)}`, { size: 22, fill: INK_SOFT }));
  } else if (p.twins) {
    b.push(twinBlock(p.twins, 0, 0));
  }

  b.push(footer(X0, X1, 1326));
  return canvas(W, H, b.join(""));
}

function countMade(dots: number[]): number {
  let made = 0;
  for (let i = 2; i < dots.length; i += 4) made += dots[i];
  return made;
}

const pct1 = (made: number, att: number) => (att ? `${((100 * made) / att).toFixed(1)}%` : "–");

function twinBlock(twins: { query: string; list: CardTwin[] }, attempts: number, made: number): string {
  const b: string[] = [];
  b.push(line(RX, CY0, X1, CY0, RULE_STRONG, 1.5));
  b.push(text(RX, CY0 + 38, "Shot twins", { size: 30, weight: 600 }));
  b.push(text(RX, CY0 + 66, `Closest player-seasons to his ${twins.query} season`, { size: 20, fill: MUTED }));
  twins.list.slice(0, 5).forEach((t, i) => {
    const top = CY0 + 90 + i * 60;
    b.push(text(RX, top + 28, t.name, { size: 26, weight: 600 }));
    b.push(text(RX, top + 52, t.club, { size: 20, fill: INK_SOFT }));
    b.push(text(X1, top + 28, `${Math.round(100 * t.score)}%`, { size: 38, weight: 600, anchor: "end" }));
    b.push(text(X1, top + 52, "similar", { size: 20, fill: MUTED, anchor: "end" }));
    if (i < Math.min(twins.list.length, 5) - 1) b.push(line(RX, top + 66, X1, top + 66, RULE, 1));
  });
  if (attempts) {
    b.push(text(RX, CY0 + 90 + 5 * 60 + 40, `${attempts} located attempts, ${made} made, FG ${pct1(made, attempts)}`, { size: 22, fill: INK_SOFT }));
  }
  return b.join("");
}
