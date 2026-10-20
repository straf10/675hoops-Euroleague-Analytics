// Round cards: /cards/round-{n}.png (the next round's preview) and /cards/round-{n}-recap.png (each
// finished round), each with a dark twin at /cards/round-{n}-dark.png and /cards/round-{n}-recap-dark.png.
// Built from site.json at build time; see src/lib/cards/.
import type { APIRoute, GetStaticPaths } from "astro";
import { cardPng, prerender } from "../../lib/cards/render";
import { euroleague, roundCardNames, roundSvg } from "../../lib/cards/site";
import { cardNames, splitTheme } from "../../lib/cards/theme";

export const getStaticPaths: GetStaticPaths = async () => {
  const c = euroleague();
  if (!c) return [];
  const names = roundCardNames(c);
  await prerender(names.map((r) => ({ key: `round/${r.name}`, svg: () => roundSvg(r.name) })));
  return names.flatMap((r) => cardNames(r.name).map((name) => ({ params: { name } })));
};

export const GET: APIRoute = async ({ params }) => {
  const { base, theme } = splitTheme(params.name!);
  const out = await cardPng(`round/${base}`, () => roundSvg(base), theme);
  if (out === null) return new Response("Not found", { status: 404 });
  return new Response(out, { headers: { "Content-Type": "image/png" } });
};
