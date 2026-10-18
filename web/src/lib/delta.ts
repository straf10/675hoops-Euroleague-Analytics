// The Delta Rule (docs/DESIGN.md): a metric against the league average gets an arrow glyph
// beside it. The arrow follows the sign (▲ above the league, ▼ below); its colour follows
// better or worse for the subject (green or red). The figure stays ink, and the sign and a
// screen-reader phrase carry the reading without colour. This file is the one place that
// decides "better"; pages and client scripts both render through `deltaHtml`.

import up from "@phosphor-icons/core/assets/fill/caret-up-fill.svg?raw";
import down from "@phosphor-icons/core/assets/fill/caret-down-fill.svg?raw";
import { signed } from "./format";
import type { BetterIs } from "./better";

export type { BetterIs };

export interface DeltaOptions {
  better?: BetterIs;
  /** Decimal places of the figure (default 1). */
  digits?: number;
  /** Text after the figure, e.g. " pts" or "%" (default none). */
  unit?: string;
  /** What the figure is compared with, for screen readers (default "the league"). */
  versus?: string;
}

/** The Sign Colour Rule (docs/DESIGN.md): a signed for-minus-against figure (+/-, net rating)
 * wears green when above zero, red when below, and stays ink at zero or when missing. The sign
 * is printed beside it, so colour is never the only cue. `digits` is the figure's decimal
 * places, so a value that rounds to 0.0 stays ink. Pages and client scripts both use this. */
export function signClass(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "";
  const shown = Number(v.toFixed(digits));
  return shown > 0 ? "sign-pos" : shown < 0 ? "sign-neg" : "";
}

export type Verdict = "better" | "worse" | "even" | "neutral";

/** The reading of a difference (subject − comparison) for the subject. */
export function deltaVerdict(diff: number, better: BetterIs = "higher"): Verdict {
  if (!Number.isFinite(diff) || diff === 0) return "even";
  if (better === "neither") return "neutral";
  return (diff > 0) === (better === "higher") ? "better" : "worse";
}

/** The arrow and signed figure for a difference from the league average, as HTML. */
export function deltaHtml(
  diff: number,
  { better = "higher", digits = 1, unit = "", versus = "the league" }: DeltaOptions = {},
): string {
  const shown = Number(diff.toFixed(digits));
  const verdict = deltaVerdict(shown, better);
  const figure = `${signed(shown, digits)}${unit}`;
  if (verdict === "even") return `<span class="delta" data-verdict="even">${figure}<span class="sr-only"> level with ${versus}</span></span>`;
  const above = shown > 0;
  const said = `${above ? "above" : "below"} ${versus}${verdict === "neutral" ? "" : `, ${verdict}`}`;
  return (
    `<span class="delta" data-verdict="${verdict}">` +
    `<span class="delta-arrow" aria-hidden="true">${above ? up : down}</span>${figure}` +
    `<span class="sr-only"> ${said}</span></span>`
  );
}
