// Rendering the cards in parallel. Astro renders an endpoint's paths one at a time, and one 1080 x 1350
// card takes a quarter of a second to rasterise and encode, so each route's getStaticPaths prerenders
// its cards a few at a time (`prerender`) and the GET handler then reads the same memo (`cardPng`).
// The memo lives for one build process, so every card is rendered once.

import { png } from "./draw";

/** How many cards are rasterised at once. */
const LANES = 6;

const memo = new Map<string, Promise<Uint8Array | null>>();

/** The PNG for a card key, rendered once. `svg` gives the card's SVG, or null for no such card. */
export function cardPng(key: string, svg: () => string | null | Promise<string | null>): Promise<Uint8Array | null> {
  let done = memo.get(key);
  if (!done) {
    done = Promise.resolve()
      .then(svg)
      .then((s) => (s === null ? null : png(s)));
    memo.set(key, done);
  }
  return done;
}

/** Renders the given cards, LANES at a time. */
export async function prerender(jobs: { key: string; svg: () => string | null | Promise<string | null> }[]): Promise<void> {
  let next = 0;
  const lane = async () => {
    while (next < jobs.length) {
      const job = jobs[next++];
      await cardPng(job.key, job.svg);
    }
  };
  await Promise.all(Array.from({ length: Math.min(LANES, jobs.length) }, lane));
}
