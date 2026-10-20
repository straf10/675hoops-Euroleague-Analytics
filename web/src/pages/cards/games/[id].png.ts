// Game previews: /cards/games/{game_id}.png, one per logged game still to play (1200 x 630), and
// /cards/games/{game_id}-dark.png for the dark theme.
import type { APIRoute, GetStaticPaths } from "astro";
import { cardPng, prerender } from "../../../lib/cards/render";
import { euroleague, gameCards, gameSvgFor } from "../../../lib/cards/site";
import { cardNames, splitTheme } from "../../../lib/cards/theme";

export const getStaticPaths: GetStaticPaths = async () => {
  const c = euroleague();
  if (!c) return [];
  const games = gameCards(c);
  await prerender(games.map((g) => ({ key: `game/${g.id}`, svg: () => gameSvgFor(g.id) })));
  return games.flatMap((g) => cardNames(g.id).map((id) => ({ params: { id } })));
};

export const GET: APIRoute = async ({ params }) => {
  const { base, theme } = splitTheme(params.id!);
  const out = await cardPng(`game/${base}`, () => gameSvgFor(base), theme);
  if (out === null) return new Response("Not found", { status: 404 });
  return new Response(out, { headers: { "Content-Type": "image/png" } });
};
