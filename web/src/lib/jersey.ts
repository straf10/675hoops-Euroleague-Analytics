// Fantasy-style jersey backs: surname and number across the back of a plain two-colour shirt.
// Club colours are the site's one bounded exception to Colour-Is-Data (docs/DESIGN.md): they live
// here, apart from the chart palette, and only ever paint a shirt's body and trim. No crests,
// sponsor marks or kit patterns; the cut is one generic sleeveless shirt for every club.

import { esc } from "./format";

/** Display code -> [body, trim]. A club's usual colours across 2007-2026, not any one kit. */
const CLUB_COLOURS: Record<string, [body: string, trim: string]> = {
  ASV: ["#16181d", "#e9e8e3"], // ASVEL: black, white (green in the older years)
  BAR: ["#a50044", "#1d3f8f"], // Barcelona: garnet, blue
  BAY: ["#c8102e", "#f4f4f1"], // Bayern: red, white
  BJK: ["#16181d", "#f4f4f1"], // Besiktas: black, white
  CZV: ["#d51c2a", "#f4f4f1"], // Crvena Zvezda: red, white
  DUB: ["#16181d", "#c9a45c"], // Dubai: black, gold
  EFS: ["#113a74", "#f4f4f1"], // Efes: navy, white
  FBT: ["#f5d80f", "#0e2346"], // Fenerbahce: yellow, navy blue
  HTA: ["#d0101e", "#f4f4f1"], // Hapoel Tel Aviv: red, white
  KBA: ["#12398f", "#c8102e"], // Baskonia: blue, red
  MIL: ["#c8102e", "#f4f4f1"], // Olimpia Milano: red, white
  MTA: ["#f5d000", "#123f94"], // Maccabi: yellow, blue
  OLY: ["#c8102e", "#f4f4f1"], // Olympiacos: red, white
  PAO: ["#0a7a3b", "#f4f4f1"], // Panathinaikos: green, white
  PAR: ["#16181d", "#f4f4f1"], // Partizan: black, white
  PBB: ["#16181d", "#e9e8e3"], // Paris: black, white
  RMB: ["#f4f4f1", "#3b2a78"], // Real Madrid: white, purple
  VBC: ["#f07c00", "#16181d"], // Valencia: orange, black
  VIR: ["#16181d", "#f4f4f1"], // Virtus: black, white
  ZAL: ["#0a6b43", "#f4f4f1"], // Zalgiris: green, white
};

const FALLBACK: [string, string] = ["#8f8d86", "#f4f4f1"];
const DARK_INK = "#111110";
const LIGHT_INK = "#fcfcfb";

export function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
}

const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

/** Name and number ink for a shirt body: whichever of the two page inks reads better on it. */
const inkOn = (body: string) => (contrast(body, DARK_INK) >= contrast(body, LIGHT_INK) ? DARK_INK : LIGHT_INK);

export const colours = (code: string) => CLUB_COLOURS[code] ?? FALLBACK;

/** "Nando De Colo" -> "DE COLO"; family names with particles keep them. */
function surname(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length < 2) return name.toUpperCase();
  let i = parts.length - 1;
  while (i > 1 && /^(de|da|del|della|di|van|von|der|la|le|dos|du|mc)$/i.test(parts[i - 1])) i--;
  if (/^(jr\.?|sr\.?|i{2,3}|iv)$/i.test(parts[parts.length - 1]) && i === parts.length - 1 && i > 1) i--;
  return parts.slice(i).join(" ").toUpperCase();
}

// One sleeveless shirt, back view, in a 100 x 112 box.
const BODY =
  "M27 4H39Q50 12 61 4H73C74 21 82 31 93 33L91 108H9L7 33C18 31 26 21 27 4Z";
const TRIM = ["M39 4Q50 12 61 4", "M73 4C74 21 82 31 93 33", "M27 4C26 21 18 31 7 33", "M9 104.5H91"];

interface Shirt {
  code: string; // display code
  name: string;
  number: string;
  size?: number; // rendered width in px
  label?: boolean; // false: decorative (the name sits beside it in text)
}

/** The shirt as inline SVG. The body and trim are the club's; the outline is a page hairline. */
export function jerseySvg({ code, name, number, size = 72, label = false }: Shirt): string {
  const [body, trim] = colours(code);
  const ink = inkOn(body);
  const last = surname(name);
  const fit = last.length > 9 ? ` textLength="${Math.min(62, 6.4 * last.length).toFixed(0)}" lengthAdjust="spacingAndGlyphs"` : "";
  const num = number.replace(/\D/g, "").slice(0, 2);
  const a11y = label
    ? `role="img" aria-label="${esc(`${name}, number ${num || "unknown"}, ${code}`)}"`
    : `aria-hidden="true"`;
  return (
    `<svg class="shirt" viewBox="0 0 100 112" width="${size}" height="${Math.round((size * 112) / 100)}" ${a11y}>` +
    `<path d="${BODY}" fill="${body}"/>` +
    TRIM.map((d) => `<path d="${d}" fill="none" stroke="${trim}" stroke-width="4.5"/>`).join("") +
    `<path class="shirt-edge" d="${BODY}" fill="none"/>` +
    // Under 48px the surname would render around 5px: small shirts carry the number only.
    (size >= 48 ? `<text x="50" y="37" text-anchor="middle" font-size="8.6" font-weight="650" letter-spacing="0.4" fill="${ink}"${fit}>${esc(last)}</text>` : "") +
    (num ? `<text x="50" y="85" text-anchor="middle" font-size="40" font-weight="700" fill="${ink}">${num}</text>` : "") +
    `</svg>`
  );
}
