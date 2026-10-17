// Regenerates public/og.png, the 1200x630 social card every page links to (Base.astro).
// Geist is set as outlines from the variable woff2's default instance, so the card does not depend on
// a font installed on the machine. (fontkitten cannot instance variable fonts, so the weight is 400.) Logo geometry mirrors src/components/Logo.astro and
// scripts/make-icons.mjs. Run from web/: node scripts/make-og.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { create } from "fontkitten";
import sharp from "sharp";

const W = 1200;
const H = 630;
const PAD = 80;
const INK = "#111110";
const INK_SOFT = "#52514e";
const MUTED = "#6d6b66";
const ORANGE = "#d9590b";
const PAPER = "#f9f9f7";
const RULE = "#e1e0d9";

const FONT = new URL("../node_modules/@fontsource-variable/geist/files/geist-latin-wght-normal.woff2", import.meta.url);
const font = create(readFileSync(FONT));

// Sets `text` as outlines with its left edge at x and baseline at y. Tracking is in em.
// No kerning pass (fontkitten has no shaper); at these sizes and this tracking the gaps read fine.
const setText = (text, size, x, y, fill, tracking = 0) => {
  const k = size / font.unitsPerEm;
  let cx = x;
  const paths = [];
  for (const ch of text) {
    const g = font.glyphForCodePoint(ch.codePointAt(0));
    paths.push(`<path transform="translate(${cx.toFixed(2)} ${y}) scale(${k} ${-k})" d="${g.path.toSVG()}"/>`);
    cx += g.advanceWidth * k + tracking * size;
  }
  return `<g fill="${fill}">${paths.join("")}</g>`;
};

// The 6.75 mark, large basket cut, drawn in a 32-unit box with its top-left at (x, y) and scale s.
const mark = (x, y, s) => `<g transform="translate(${x} ${y}) scale(${s})">
  <g transform="translate(0 3)" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <g stroke="${INK}"><path d="M2 3h28" stroke-width="2.6"/><path d="M12.6 5.8h6.8" stroke-width="2"/><path d="M16 5.8v1" stroke-width="1.5"/><circle cx="16" cy="9.1" r="2.3" stroke-width="1.6"/></g>
    <path d="M4.5 3v9a11.5 11.5 0 0 0 23 0V3" stroke="${ORANGE}" stroke-width="3"/>
  </g>
</g>`;

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <rect width="${W}" height="${H}" fill="${PAPER}"/>
  ${mark(PAD, PAD - 4, 2.1)}
  ${setText("6.75 Analytics", 40, PAD + 80, PAD + 42, INK, -0.02)}
  ${setText("EuroLeague 2026-27 win forecasts,", 64, PAD, 280, INK, -0.03)}
  ${setText("pre-registered and scored in public", 64, PAD, 364, INK_SOFT, -0.03)}
  <rect x="${PAD}" y="${H - 150}" width="${W - 2 * PAD}" height="1" fill="${RULE}"/>
  ${setText("675hoops.com  ·  Every forecast logged before tip-off", 28, PAD, H - 90, MUTED, 0)}
</svg>`;

writeFileSync("public/og.png", await sharp(Buffer.from(svg)).png().toBuffer());
