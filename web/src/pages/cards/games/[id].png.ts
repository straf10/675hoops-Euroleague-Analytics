// Game previews: /cards/games/{game_id}.png, one per logged game still to play (1200 x 630).
import type { APIRoute, GetStaticPaths } from "astro";
import { cardPng, prerender } from "../../../lib/cards/render";
import { euroleague, gameCards, gameSvgFor } from "../../../lib/cards/site";

export const getStaticPaths: GetStaticPaths = async () => {
  const c = euroleague();
  if (!c) return [];
  const games = gameCards(c);
  await prerender(games.map((g) => ({ key: `game/${g.id}`, svg: () => gameSvgFor(g.id) })));
  return games.map((g) => ({ params: { id: g.id } }));
};

export const GET: APIRoute = async ({ params }) => {
  const out = await cardPng(`game/${params.id}`, () => gameSvgFor(params.id!));
  if (out === null) return new Response("Not found", { status: 404 });
  return new Response(out, { headers: { "Content-Type": "image/png" } });
};
