// Loads the coach files `eurohoops export-stats` writes to src/data/stats/coaches (build time only).
// Kept apart from coaches.ts so the pure helpers stay testable under plain Node.

import type { CoachIndex, CoachPage, CoachStyle } from "./coaches";

const files = import.meta.glob<unknown>("../data/stats/coaches/*.json", { import: "default" });

async function load<T>(name: string): Promise<T | null> {
  const loader = files[`../data/stats/coaches/${name}.json`] as (() => Promise<unknown>) | undefined;
  return loader ? ((await loader()) as T) : null;
}

export async function coachIndex(): Promise<CoachIndex | null> {
  return load<CoachIndex>("index");
}

export async function coachPage(slug: string): Promise<CoachPage> {
  const page = await load<CoachPage>(slug);
  if (!page) throw new Error(`no coach file for ${slug}; run eurohoops export-stats`);
  return page;
}

/** Each coach's style block (null without one), keyed by slug: the index table's style columns. */
export async function coachStyles(slugs: string[]): Promise<Record<string, CoachStyle | null>> {
  const pages = await Promise.all(slugs.map((slug) => coachPage(slug)));
  return Object.fromEntries(pages.map((page) => [page.slug, page.style]));
}
