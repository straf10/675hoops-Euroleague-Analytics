// Rendering the cards in parallel. Astro renders an endpoint's paths one at a time, and one 1080 x 1350
// card takes a quarter of a second to rasterise and encode, so each route's getStaticPaths prerenders
// its cards a few at a time (`prerender`) and the GET handler then reads the same memo (`cardPng`).
// The memo lives for one build process, so every card is rendered once per theme.

import { png } from "./draw";
import { recolour, type Theme } from "./theme";

/** How many cards are rasterised at once. */
const LANES = 6;

/** A card's SVG in the light palette, or null for no such card. */
export type CardSvg = () => string | null | Promise<string | null>;

const memo = new Map<string, Promise<Uint8Array | null>>();

/** The PNG for a card key in a theme, rendered once. */
export function cardPng(key: string, svg: CardSvg, theme: Theme = "light"): Promise<Uint8Array | null> {
  const id = `${theme}/${key}`;
  let done = memo.get(id);
  if (!done) {
    done = Promise.resolve()
      .then(svg)
      .then((s) => (s === null ? null : png(recolour(s, theme))));
    memo.set(id, done);
  }
  return done;
}

/** Renders the given cards in both themes, LANES at a time. Each job's card is `key`, and its dark
 * version is rendered beside it. */
export async function prerender(jobs: { key: string; svg: CardSvg }[]): Promise<void> {
  const tasks = jobs.flatMap((job) => (["light", "dark"] as const).map((theme) => ({ ...job, theme })));
  let next = 0;
  const lane = async () => {
    while (next < tasks.length) {
      const job = tasks[next++];
      await cardPng(job.key, job.svg, job.theme);
    }
  };
  await Promise.all(Array.from({ length: Math.min(LANES, tasks.length) }, lane));
}
