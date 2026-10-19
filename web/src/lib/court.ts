// Half-court drawing and the three shot-chart layers (FG% against the league, frequency, single
// attempts). Pure strings, shared by the build and the in-page updates of the player, team and
// Shots pages. Court metres, basket at the origin; drawn with the baseline on top.

import { esc } from "./format";
import { dataTip, tip } from "./tip";

/** [q, r, attempts, makes, league FG% in the cell x10 (-1: no league shots there)] */
export type HexCell = [q: number, r: number, att: number, made: number, league: number];

const SQRT3 = Math.sqrt(3);
const BASELINE = 1.575;
export const DEPTH = 10; // metres from the basket shown (the original 9.3 plus a little more height)
const MIDCOURT = 14 - BASELINE; // metres from the basket to the halfway line
/** Court metres from the basket to the layer's y (the baseline sits at BASELINE below the basket). */
export const toY = (y: number) => y + BASELINE;

function courtLines(depth: number, closed: boolean): string {
  const arcY = Math.sqrt(6.75 ** 2 - 6.6 ** 2); // where the corner lines meet the arc
  const ft = 5.8 - BASELINE;
  return [
    closed
      ? `<path class="line" d="M-7.5 0H7.5V${toY(depth)}H-7.5Z"/><path class="line" d="M-1.8 ${toY(depth)}A1.8 1.8 0 0 1 1.8 ${toY(depth)}"/>`
      : `<path class="line" d="M-7.5 ${toY(depth)}V0H7.5V${toY(depth)}"/>`,
    `<path class="line" d="M-2.45 0V${toY(ft)}H2.45V0"/>`,
    `<path class="line" d="M-1.8 ${toY(ft)}A1.8 1.8 0 0 0 1.8 ${toY(ft)}"/>`,
    `<path class="line" d="M-6.6 0V${toY(arcY)}A6.75 6.75 0 0 0 6.6 ${toY(arcY)}V0"/>`,
    `<path class="line" d="M-1.25 ${toY(0)}A1.25 1.25 0 0 0 1.25 ${toY(0)}"/>`,
  ].join("");
}

// Backboard and rim sit above the marks, so the basket stays legible under the busiest cells.
const BASKET = `<path class="line" d="M-0.9 ${toY(-0.375)}H0.9"/><circle class="rim" cx="0" cy="${toY(0)}" r="0.225"/>`;

/** The court is drawn this much narrower than it is long (the sides are squeezed, the depth kept),
 * so the floor fills more of the chart. Every chart uses it. */
const SQUEEZE = 0.84;

/** A coordinate with at most two decimals and no trailing zeros or leading zero: "-7.5", ".5", "1.58".
 * Path data is most of a chart's bytes, and centimetre precision is all a court needs. */
export const num = (v: number): string => String(+v.toFixed(2)).replace(/^(-?)0\./, "$1.");

/** The court with a mark layer clipped to the floor. `closed` draws it to the halfway line. */
export const court = (layer: string, label: string, closed = false) => {
  const depth = closed ? MIDCOURT : DEPTH;
  const h = toY(depth).toFixed(3);
  const marks = layer ? `<svg x="-7.5" y="0" width="15" height="${h}" viewBox="-7.5 0 15 ${h}">${layer}</svg>` : "";
  const width = (15.4 * SQUEEZE).toFixed(3);
  const left = (-7.7 * SQUEEZE).toFixed(3);
  return (
    `<svg class="court" viewBox="${left} -0.2 ${width} ${(toY(depth) + 0.4).toFixed(2)}" role="img" aria-label="${esc(label)}">` +
    `<g transform="scale(${SQUEEZE} 1)"><rect class="floor" x="-7.5" y="0" width="15" height="${h}"/>${courtLines(depth, closed)}${marks}${BASKET}</g></svg>`
  );
};

// The six corners of a pointy-top hex, from 30 degrees above the right-hand side, clockwise.
const CORNERS = [0, 1, 2, 3, 4, 5].map((i) => {
  const a = ((60 * i - 30) * Math.PI) / 180;
  return [Math.cos(a), Math.sin(a)];
});

/** A pointy-top hex in short absolute form: the same six vertices, rounded to 0.001 m as before,
 * but without trailing zeros, with V for the vertical sides and runs of implicit linetos
 * (a chart holds hundreds of these). Absolute, so the browser draws exactly the same points. */
function hexPath(cx: number, cy: number, r: number): string {
  let d = "";
  let px = NaN; // the previous corner's x
  let afterV = false; // a pair after V needs an explicit L; after M or L it runs on
  for (const [cos, sin] of CORNERS) {
    const x = +(cx + r * cos).toFixed(3);
    const y = +(cy + r * sin).toFixed(3);
    const vertical = x === px;
    d += !d ? `M ${x} ${y}` : vertical ? `V${y}` : `${afterV ? "L" : " "}${x} ${y}`;
    px = x;
    afterV = vertical;
  }
  return `${d}Z`;
}


/** Five steps of "FG% here against the league here", shrunk toward the league on small samples. */
function tone(att: number, made: number, leaguePermille: number): number {
  if (leaguePermille < 0) return 0;
  const league = leaguePermille / 1000;
  const k = 8; // prior weight in attempts
  const diff = 100 * ((made + k * league) / (att + k) - league);
  if (diff <= -7) return -2;
  if (diff <= -2.5) return -1;
  if (diff < 2.5) return 0;
  return diff < 7 ? 1 : 2;
}


const defaultTip = ([, , att, made, lg]: HexCell) => {
  const league = lg < 0 ? "no league shots here" : `league ${(lg / 10).toFixed(1)}%`;
  return tip`<b>${made} of ${att}</b> (${((100 * made) / att).toFixed(0)}%)<br>${league}`;
};


