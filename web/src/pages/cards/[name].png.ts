// Round cards: /cards/round-{n}.png (the next round's preview) and /cards/round-{n}-recap.png (each
// finished round). Built from site.json at build time; see src/lib/cards/.
import type { APIRoute, GetStaticPaths } from "astro";
import { cardPng, prerender } from "../../lib/cards/render";
import { euroleague, roundCardNames, roundSvg } from "../../lib/cards/site";

export const getStaticPaths: GetStaticPaths = async () => {
  const c = euroleague();
  if (!c) return [];
  const names = roundCardNames(c);
  await prerender(names.map((r) => ({ key: `round/${r.name}`, svg: () => roundSvg(r.name) })));
  return names.map((r) => ({ params: { name: r.name } }));
};

export const GET: APIRoute = async ({ params }) => {
  const out = await cardPng(`round/${params.name}`, () => roundSvg(params.name!));
  if (out === null) return new Response("Not found", { status: 404 });
  return new Response(out, { headers: { "Content-Type": "image/png" } });
};
