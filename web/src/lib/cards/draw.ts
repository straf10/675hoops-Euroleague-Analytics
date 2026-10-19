// Share-card drawing. A card is an SVG string that sharp rasterises to PNG at build time. Geist is
// set as glyph outlines (fontkitten, as web/scripts/make-og.mjs does), so no card depends on a font
// installed on the machine. fontkitten cannot instance the variable font, so the heavier weights are
// the regular outlines with a stroke of their own colour: a faux weight, close enough at card size.

import { create, type Font } from "fontkitten";
import sharp from "sharp";
import latin from "@fontsource-variable/geist/files/geist-latin-wght-normal.woff2?inline";
import latinExt from "@fontsource-variable/geist/files/geist-latin-ext-wght-normal.woff2?inline";

// Colours: the page tokens of src/styles/global.css (light theme). Cards are always light.
const PAPER = "#f9f9f7";
export const SURFACE = "#fcfcfb";
export const INK = "#111110";
export const INK_SOFT = "#52514e";
export const MUTED = "#6d6b66";
export const AXIS = "#898781";
export const RULE = "#e1e0d9";
export const RULE_STRONG = "#c3c2b7";
export const ORANGE = "#d9590b";
export const GRAY = "#8f8d86";
export const BLUE = "#2a78d6";

const FOOTER = "675hoops.com · Every forecast logged before tip-off";

const decode = (dataUrl: string) => Buffer.from(dataUrl.slice(dataUrl.indexOf(",") + 1), "base64");
const FONTS: Font[] = [create(decode(latin)), create(decode(latinExt))];

interface Glyph {
  /** The outline's commands in font units, y up. */
  cmds: { command: string; args: number[] }[];
  /** Advance in em. */
  adv: number;
  upem: number;
}

const glyphs = new Map<number, Glyph>();

function glyph(cp: number): Glyph {
  let g = glyphs.get(cp);
  if (!g) {
    const font = FONTS.find((f) => f.hasGlyphForCodePoint(cp)) ?? FONTS[0];
    const gl = font.glyphForCodePoint(cp);
    g = { cmds: gl.path.commands, adv: gl.advanceWidth / font.unitsPerEm, upem: font.unitsPerEm };
    glyphs.set(cp, g);
  }
  return g;
}

const LETTERS: Record<string, string> = {
  moveTo: "M",
  lineTo: "L",
  quadraticCurveTo: "Q",
  bezierCurveTo: "C",
  closePath: "Z",
};

/** A glyph's outline as path data, placed at (ox, oy) with its em scaled by k (y flipped). One path
 * per text run keeps the SVG small: rasterising hundreds of tiny paths is what costs the build time. */
function outline(cmds: Glyph["cmds"], ox: number, oy: number, k: number): string {
  let d = "";
  for (const { command, args } of cmds) {
    d += LETTERS[command];
    for (let i = 0; i < args.length; i += 2) d += ` ${(ox + args[i] * k).toFixed(1)} ${(oy - args[i + 1] * k).toFixed(1)}`;
  }
  return d;
}

interface TextStyle {
  size: number;
  weight?: number;
  fill?: string;
  anchor?: "start" | "middle" | "end";
  /** Letter spacing in em. */
  track?: number;
}

/** Advance width of a string in px. */
export function width(s: string, size: number, track = 0): number {
  let w = 0;
  for (const ch of s) w += glyph(ch.codePointAt(0)!).adv * size + track * size;
  return w;
}

/** A line of text as outlines, its baseline at y. */
export function text(x: number, y: number, s: string, st: TextStyle): string {
  const { size, weight = 400, fill = INK, anchor = "start", track = 0 } = st;
  const total = width(s, size, track);
  let cx = anchor === "end" ? x - total : anchor === "middle" ? x - total / 2 : x;
  const faux = weight >= 600 ? ` stroke="${fill}" stroke-width="${(size * (weight >= 640 ? 0.04 : 0.028)).toFixed(2)}" stroke-linejoin="round"` : "";
  let d = "";
  for (const ch of s) {
    const g = glyph(ch.codePointAt(0)!);
    if (g.cmds.length) d += outline(g.cmds, cx, y, size / g.upem);
    cx += g.adv * size + track * size;
  }
  return d ? `<path fill="${fill}" d="${d}"${faux}/>` : "";
}

/** The largest size (at most `size`) at which the string fits in `maxW` px. */
export function fitSize(s: string, size: number, maxW: number, track = 0): number {
  const w = width(s, size, track);
  return w <= maxW ? size : Math.floor(size * (maxW / w));
}

export const line = (x1: number, y1: number, x2: number, y2: number, stroke = RULE, w = 1) =>
  `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${stroke}" stroke-width="${w}"/>`;

export const rect = (x: number, y: number, w: number, h: number, fill: string, rx = 0, opacity = 1) =>
  `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="${rx}" fill="${fill}"${opacity < 1 ? ` fill-opacity="${opacity}"` : ""}/>`;

export const circle = (cx: number, cy: number, r: number, fill: string) =>
  `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r}" fill="${fill}"/>`;

export const canvas = (w: number, h: number, body: string): string =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">` +
  `<rect width="${w}" height="${h}" fill="${PAPER}"/>${body}</svg>`;

/** Rasterises a card. A palette keeps the flat colours small on disk. */
export async function png(svg: string): Promise<Uint8Array> {
  return new Uint8Array(await sharp(Buffer.from(svg)).png({ palette: true, compressionLevel: 9 }).toBuffer());
}

/** The 6.75 mark (web/public/favicon.svg, light colours) at 32px, then the wordmark. (x, y) is the
 * wordmark's baseline-left, as the demo cards set it. */
export function logo(x: number, y: number): string {
  const mark =
    `<g transform="translate(${x} ${y - 6})"><g transform="translate(0 3)" fill="none" stroke-linecap="round" stroke-linejoin="round">` +
    `<path d="M2 3h28" stroke="${INK}" stroke-width="2.6"/>` +
    `<path d="M4.5 3v9a11.5 11.5 0 0 0 23 0V3" stroke="${ORANGE}" stroke-width="3"/>` +
    `<path d="M12.2 6h7.6" stroke="${INK}" stroke-width="2.6"/>` +
    `<circle cx="16" cy="9.8" r="2.6" stroke="${INK}" stroke-width="2.2"/>` +
    `</g></g>`;
  return (
    mark +
    text(x + 42, y + 22, "6.75", { size: 28, weight: 620 }) +
    text(x + 114, y + 22, "Analytics", { size: 28, fill: INK_SOFT })
  );
}

/** The footer rule and line, at baseline y. */
export function footer(x0: number, x1: number, y: number): string {
  return line(x0, y - 36, x1, y - 36, RULE, 1) + text(x0, y, FOOTER, { size: 18, fill: MUTED });
}

/** Forecast split bar: the away share in gray on the left, the home share in orange on the right,
 * meeting at p_home, with a thin tick at the 50% midpoint. */
export function split(x: number, y: number, w: number, h: number, pHome: number, gap = 2, r = 4): string {
  const aw = (1 - pHome) * w - gap / 2;
  const hx = x + (1 - pHome) * w + gap / 2;
  const a = seg(x, x + aw, y, h, Math.min(r, aw / 2), 0);
  const hm = seg(hx, x + w, y, h, 0, Math.min(r, (x + w - hx) / 2));
  return `<path d="${a}" fill="${GRAY}"/><path d="${hm}" fill="${ORANGE}"/>` + line(x + w / 2, y - 6, x + w / 2, y + h + 6, AXIS, 1.5);
}

/** A bar's outline with optional rounded ends (rl left, rr right). */
function seg(x0: number, x1: number, y: number, h: number, rl: number, rr: number): string {
  let d = `M${x0 + rl},${y} H${x1 - rr} `;
  if (rr) d += `A${rr},${rr} 0 0 1 ${x1},${y + rr} `;
  d += `V${y + h - rr} `;
  if (rr) d += `A${rr},${rr} 0 0 1 ${x1 - rr},${y + h} `;
  d += `H${x0 + rl} `;
  if (rl) d += `A${rl},${rl} 0 0 1 ${x0},${y + h - rl} `;
  d += `V${y + rl} `;
  if (rl) d += `A${rl},${rl} 0 0 1 ${x0 + rl},${y} `;
  return d + "Z";
}

/** Home-win chance in whole percents: [away, home]. They always sum to 100. */
export function pcts(pHome: number): [number, number] {
  const home = Math.round(pHome * 100);
  return [100 - home, home];
}
