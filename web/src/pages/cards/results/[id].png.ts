// Result cards: /cards/results/{game_id}.png, one per played game (1200 x 630), and
// /cards/results/{game_id}-dark.png for the dark theme. The game page links its card as its share image.
import type { APIRoute, GetStaticPaths } from "astro";
import { cardPng, prerender } from "../../../lib/cards/render";
import { euroleague, resultCards, resultSvgFor } from "../../../lib/cards/site";
import { cardNames, splitTheme } from "../../../lib/cards/theme";

export const getStaticPaths: GetStaticPaths = async () => {
  const c = euroleague();
  if (!c) return [];
  const games = resultCards(c);
  await prerender(games.map((g) => ({ key: `result/${g.game_id}`, svg: () => resultSvgFor(g.game_id) })));
  return games.flatMap((g) => cardNames(g.game_id).map((id) => ({ params: { id } })));
};

export const GET: APIRoute = async ({ params }) => {
  const { base, theme } = splitTheme(params.id!);
  const out = await cardPng(`result/${base}`, () => resultSvgFor(base), theme);
  if (out === null) return new Response("Not found", { status: 404 });
  return new Response(out, { headers: { "Content-Type": "image/png" } });
};
