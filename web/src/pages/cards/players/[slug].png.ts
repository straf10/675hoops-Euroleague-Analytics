// Player cards: /cards/players/{slug}.png (1080 x 1350), only for players in the live season.
import type { APIRoute, GetStaticPaths } from "astro";
import { cardPng, prerender } from "../../../lib/cards/render";
import { currentPlayers, playerSvgFor } from "../../../lib/cards/players";

export const getStaticPaths: GetStaticPaths = async () => {
  const players = await currentPlayers();
  await prerender(players.map((p) => ({ key: `player/${p.slug}`, svg: () => playerSvgFor(p.slug) })));
  return players.map((p) => ({ params: { slug: p.slug } }));
};

export const GET: APIRoute = async ({ params }) => {
  const out = await cardPng(`player/${params.slug}`, () => playerSvgFor(params.slug!));
  if (out === null) return new Response("Not found", { status: 404 });
  return new Response(out, { headers: { "Content-Type": "image/png" } });
};
