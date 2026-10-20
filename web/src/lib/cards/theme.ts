// Card themes. Every card is drawn once in the light palette (draw.ts) and, for the dark version, its
// colours are swapped for the night tokens of src/styles/global.css. The swap is by exact hex, so the
// layout is the same in both themes. This module has no font or raster dependency, so it is testable.

export type Theme = "light" | "dark";

/** The light palette: the page tokens of global.css (`:root`). */
export const LIGHT = {
  paper: "#f9f9f7",
  surface: "#fcfcfb",
  ink: "#111110",
  inkSoft: "#52514e",
  muted: "#6d6b66",
  axis: "#898781",
  rule: "#e1e0d9",
  ruleStrong: "#c3c2b7",
  orange: "#d9590b",
  gray: "#8f8d86",
  blue: "#2a78d6",
} as const;

/** The dark palette: the night tokens of global.css (`:root[data-theme="dark"]`, `prefers-color-scheme: dark`).
 * Page, surface, ink, muted, axis and rules map one to one; the data marks follow the night data tokens
 * (`--data-1`, `--data-2`, `--data-neg`), so a card's orange, gray and blue match the page's. */
export const DARK: Record<keyof typeof LIGHT, string> = {
  paper: "#0e0e0d",
  surface: "#1a1a19",
  ink: "#f2f1ec",
  inkSoft: "#c3c2b7",
  muted: "#9c9a92",
  axis: "#898781",
  rule: "#2c2c2a",
  ruleStrong: "#45453f",
  orange: "#e2691f",
  gray: "#6a6862",
  blue: "#3987e5",
};

/** Light hex (lower case) to its dark counterpart. Every light colour is distinct, so the map is exact. */
const SWAP = new Map<string, string>(
  (Object.keys(LIGHT) as (keyof typeof LIGHT)[]).map((k) => [LIGHT[k].toLowerCase(), DARK[k]]),
);

/** The SVG in the given theme. Light is the drawn SVG unchanged; dark swaps each light palette colour. */
export function recolour(svg: string, theme: Theme): string {
  if (theme === "light") return svg;
  return svg.replace(/#[0-9a-fA-F]{6}\b/g, (hex) => SWAP.get(hex.toLowerCase()) ?? hex);
}

/** The suffix a dark card carries in its route name and file name: `x.png` and `x-dark.png`. */
export const DARK_SUFFIX = "-dark";

/** A card's route or file name for a theme: "round-4" becomes "round-4-dark" for the dark card. */
export function themedName(base: string, theme: Theme): string {
  return theme === "dark" ? base + DARK_SUFFIX : base;
}

/** Both route names of a card, light first. */
export function cardNames(base: string): [string, string] {
  return [base, themedName(base, "dark")];
}

/** A route name split into its card and theme: "round-4-dark" is { base: "round-4", theme: "dark" }. */
export function splitTheme(name: string): { base: string; theme: Theme } {
  return name.endsWith(DARK_SUFFIX)
    ? { base: name.slice(0, -DARK_SUFFIX.length), theme: "dark" }
    : { base: name, theme: "light" };
}
