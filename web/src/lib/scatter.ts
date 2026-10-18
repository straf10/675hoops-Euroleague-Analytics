// The Teams index charts: offence against defence (ORtg, DRtg) and pace against net rating, one
// mark per club. Pure (format helpers only), so the build and the in-page season switch draw the
// same SVG. Values are per 100 possessions, pace per 40 minutes, as the table shows them.
import { esc, signed } from "./format";
import { colours } from "./jersey";
import { CLUB_MARK } from "./mark";
import { dataTip, tip } from "./tip";

export interface ScatterClub {
  code: string;
  name: string;
  ortg: number;
  drtg: number;
  net: number;
  pace: number;
}

/** One season's clubs and the league line (the league's own factors, from the same totals). */
export interface ClubPlot {
  league: { ortg: number; drtg: number; pace: number };
  clubs: ScatterClub[];
}

const W = 380;
const H = 360;
const PAD = { left: 60, right: 22, top: 14, bottom: 50 };
const IW = W - PAD.left - PAD.right;
const IH = H - PAD.top - PAD.bottom;
const STEPS = [1, 2, 2.5, 5, 10];
/** A club's disc radius, in chart units (about 9 px on a phone). */
const R = 6.5;

interface Scale {
  lo: number;
  hi: number;
  ticks: number[];
}

/** A linear scale that covers the values, out to whole tick steps (1, 2, 2.5, 5 or 10 times a power of ten). */
function scale(values: number[]): Scale {
  const lo0 = Math.min(...values);
  const hi0 = Math.max(...values);
  const raw = (hi0 - lo0 || 1) / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = (STEPS.find((m) => m * mag >= raw) ?? 10) * mag;
  const lo = Math.floor(lo0 / step) * step;
  const hi = (Math.floor(hi0 / step) + 1) * step;
  const count = Math.round((hi - lo) / step);
  const ticks = Array.from({ length: count + 1 }, (_, i) => +(lo + i * step).toFixed(6));
  return { lo, hi, ticks };
}

const one = (v: number) => v.toFixed(1);
const whole = (v: number) => String(v);
const net = (v: number) => (v === 0 ? "0" : signed(v, 0));

interface Frame {
  id: string;
  title: string;
  desc: string;
  xs: Scale;
  ys: Scale;
  /** whether a higher value on the y axis sits higher on the page (false: the defensive axis, lower is up) */
  highUp: boolean;
  /** short corner notes inside the plot saying which way is better: x sits bottom right, y top left */
  notes?: { x?: string; y?: string };
  xTitle: string;
  yTitle: string;
  xFmt: (v: number) => string;
  yFmt: (v: number) => string;
  body: (x: (v: number) => number, y: (v: number) => number) => string;
}

/** The chart's frame: plot, gridlines, ticks, axis titles, and the accessible name and description. */
function svgFrame(f: Frame): string {
  const x = (v: number) => PAD.left + ((v - f.xs.lo) / (f.xs.hi - f.xs.lo)) * IW;
  const y = (v: number) =>
    f.highUp ? PAD.top + ((f.ys.hi - v) / (f.ys.hi - f.ys.lo)) * IH : PAD.top + ((v - f.ys.lo) / (f.ys.hi - f.ys.lo)) * IH;
  const bottom = PAD.top + IH;
  const grid = f.xs.ticks.map((t) => `<line class="gx" x1="${x(t).toFixed(1)}" x2="${x(t).toFixed(1)}" y1="${PAD.top}" y2="${bottom}"/>`).join("");
  const xTicks = f.xs.ticks.map((t) => `<text class="tick" x="${x(t).toFixed(1)}" y="${bottom + 16}" text-anchor="middle">${f.xFmt(t)}</text>`).join("");
  const yGrid = f.ys.ticks.map((t) => `<line class="gy" x1="${PAD.left}" x2="${PAD.left + IW}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}"/>`).join("");
  const yTicks = f.ys.ticks
    .map((t) => `<text class="tick" x="${PAD.left - 8}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end">${f.yFmt(t)}</text>`)
    .join("");
  // Notes sit under the points (drawn before body) and clear of the tick labels, which lie outside the plot.
  const noteX = f.notes?.x ? `<text class="note" x="${PAD.left + IW - 6}" y="${bottom - 6}" text-anchor="end">${esc(f.notes.x)}</text>` : "";
  const noteY = f.notes?.y ? `<text class="note" x="${PAD.left + 6}" y="${PAD.top + 12}" text-anchor="start">${esc(f.notes.y)}</text>` : "";
  return (
    `<svg class="scatter" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="${f.id}-t ${f.id}-d">` +
    `<title id="${f.id}-t">${esc(f.title)}</title><desc id="${f.id}-d">${esc(f.desc)}</desc>` +
    `<rect class="plot" x="${PAD.left}" y="${PAD.top}" width="${IW}" height="${IH}"/>` +
    `<g class="grid">${grid}${yGrid}</g>` +
    `<g class="notes">${noteX}${noteY}</g>` +
    f.body(x, y) +
    `<g>${xTicks}${yTicks}</g>` +
    `<text class="axis" x="${PAD.left + IW / 2}" y="${H - 8}" text-anchor="middle">${esc(f.xTitle)}</text>` +
    `<text class="axis" transform="translate(14 ${PAD.top + IH / 2}) rotate(-90)" text-anchor="middle">${esc(f.yTitle)}</text>` +
    `</svg>`
  );
}

/** A two-tone disc: the left half in the club's body colour, the right half in its trim (lib/jersey.ts),
 * with a hairline edge so a dark or pale club still reads on paper and in dark mode. The code and the
 * figures show on hover or focus through the data-tip system. */
function disc(c: { code: string; name: string }, px: number, py: number, detail: string): string {
  const [body, trim] = colours(c.code);
  const cx = px.toFixed(1);
  const cy = py.toFixed(1);
  const top = (py - R).toFixed(1);
  const bottom = (py + R).toFixed(1);
  return (
    `<g class="pt" tabindex="0" role="img" aria-label="${esc(c.name)} (${esc(c.code)}): ${esc(detail)}"${dataTip(tip`<b>${c.code}</b> ${c.name}<br>${detail}`)}>` +
    `<circle cx="${cx}" cy="${cy}" r="${R}" fill="${trim}"/>` +
    `<path d="M${cx} ${top}A${R} ${R} 0 0 0 ${cx} ${bottom}Z" fill="${body}"/>` +
    `<circle class="edge" cx="${cx}" cy="${cy}" r="${R}"/></g>`
  );
}

/** A club's mark, as CLUB_MARK (lib/mark.ts) says. */
function mark(c: { code: string; name: string }, px: number, py: number, detail: string): string {
  // A crest would be drawn here. Crests need permission (PRODUCT.md:45), so the crest option falls back to the disc.
  if (CLUB_MARK === "crest") return disc(c, px, py, detail);
  return disc(c, px, py, detail);
}

/** ORtg on the x axis, DRtg on the y axis reversed (lower DRtg higher up, so up and right is good).
 * One scale for both axes, so the net 0 line (ORtg = DRtg) is a true diagonal. */
export function ratingsChart(plot: ClubPlot, label: string): string {
  const all = [...plot.clubs.flatMap((c) => [c.ortg, c.drtg]), plot.league.ortg, plot.league.drtg];
  const s = scale(all);
  const { lo, hi } = s;
  return svgFrame({
    id: "ratings",
    title: `Offence against defence, ${label} EuroLeague clubs`,
    desc: `${plot.clubs.length} clubs. Up and right is better: higher ORtg, lower DRtg. Dashed lines mark the league average; the diagonal is net 0.`,
    xs: s,
    ys: s,
    highUp: false,
    notes: { x: "Better offence →", y: "↑ Better defence" },
    xTitle: "ORtg: points scored per 100 possessions",
    yTitle: "DRtg: points allowed per 100 possessions",
    xFmt: whole,
    yFmt: whole,
    body: (x, y) => {
      const ref =
        `<line class="ref" x1="${x(plot.league.ortg).toFixed(1)}" x2="${x(plot.league.ortg).toFixed(1)}" y1="${PAD.top}" y2="${PAD.top + IH}"/>` +
        `<line class="ref" x1="${PAD.left}" x2="${PAD.left + IW}" y1="${y(plot.league.drtg).toFixed(1)}" y2="${y(plot.league.drtg).toFixed(1)}"/>`;
      const zero = `<line class="zero" x1="${x(lo).toFixed(1)}" y1="${y(lo).toFixed(1)}" x2="${x(hi).toFixed(1)}" y2="${y(hi).toFixed(1)}"/>`;
      const dots = plot.clubs
        .map((c) => mark(c, x(c.ortg), y(c.drtg), `ORtg ${one(c.ortg)}, DRtg ${one(c.drtg)}, net ${signed(c.net)}`))
        .join("");
      return `<g class="ref-set">${ref}${zero}</g><g class="pts">${dots}</g>`;
    },
  });
}

/** Pace on the x axis, net rating on the y axis, with the league pace and net 0 as reference lines. */
export function paceChart(plot: ClubPlot, label: string): string {
  const xs = scale([...plot.clubs.map((c) => c.pace), plot.league.pace]);
  const ys = scale([...plot.clubs.map((c) => c.net), 0]);
  return svgFrame({
    id: "pace",
    title: `Pace against net rating, ${label} EuroLeague clubs`,
    desc: `${plot.clubs.length} clubs. Right is faster; up is a better net rating. Dashed lines mark the league pace and net 0.`,
    xs,
    ys,
    highUp: true,
    notes: { x: "Faster →", y: "↑ Better net" },
    xTitle: "Pace: possessions per 40 minutes",
    yTitle: "Net rating: points per 100 possessions",
    xFmt: one,
    yFmt: net,
    body: (x, y) => {
      const ref =
        `<line class="ref" x1="${x(plot.league.pace).toFixed(1)}" x2="${x(plot.league.pace).toFixed(1)}" y1="${PAD.top}" y2="${PAD.top + IH}"/>` +
        `<line class="zero" x1="${PAD.left}" x2="${PAD.left + IW}" y1="${y(0).toFixed(1)}" y2="${y(0).toFixed(1)}"/>`;
      const dots = plot.clubs
        .map((c) => mark(c, x(c.pace), y(c.net), `pace ${one(c.pace)}, net ${signed(c.net)}`))
        .join("");
      return `<g class="ref-set">${ref}</g><g class="pts">${dots}</g>`;
    },
  });
}
