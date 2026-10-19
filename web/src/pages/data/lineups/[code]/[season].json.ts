// One club's lineups for one season, for the team page's Lineups tab when the visitor switches season.
// The page itself carries only the season it opens on (teams/[code].astro).
import type { APIRoute, GetStaticPaths } from "astro";
import { clubLineups, teamIndex } from "../../../../lib/stats";

export const getStaticPaths: GetStaticPaths = async () =>
  (await teamIndex()).flatMap((t) =>
    t.seasons.map((s) => ({ params: { code: t.code.toLowerCase(), season: String(s) }, props: { code: t.code, s } })),
  );

export const GET: APIRoute = async ({ props }) => {
  const { code, s } = props as { code: string; s: number };
  return new Response(JSON.stringify(await clubLineups(code, s)), {
    headers: { "Content-Type": "application/json" },
  });
};
