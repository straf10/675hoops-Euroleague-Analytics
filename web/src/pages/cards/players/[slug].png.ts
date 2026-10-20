// Player cards: /cards/players/{slug}.png (1080 x 1350), and /cards/players/{slug}-dark.png for the
// dark theme. Only players in the live season have one.
import type { APIRoute, GetStaticPaths } from "astro";
import { cardPng, prerender } from "../../../lib/cards/render";
import { currentPlayers, playerSvgFor } from "../../../lib/cards/players";
import { cardNames, splitTheme } from "../../../lib/cards/theme";

export const getStaticPaths: GetStaticPaths = async () => {
  const players = await currentPlayers();
  await prerender(players.map((p) => ({ key: `player/${p.slug}`, svg: () => playerSvgFor(p.slug) })));
  return players.flatMap((p) => cardNames(p.slug).map((slug) => ({ params: { slug } })));
};

export const GET: APIRoute = async ({ params }) => {
  const { base, theme } = splitTheme(params.slug!);
  const out = await cardPng(`player/${base}`, () => playerSvgFor(base), theme);
  if (out === null) return new Response("Not found", { status: 404 });
  return new Response(out, { headers: { "Content-Type": "image/png" } });
};
