// One club's shots taken and allowed in one season, for the team page's Shot attempts chart. The live
// season is inlined on the page; other seasons are fetched when the visitor changes season.
import type { APIRoute, GetStaticPaths } from "astro";
import { clubShots, teamIndex } from "../../../../../lib/stats";

export const getStaticPaths: GetStaticPaths = async () =>
  (await teamIndex()).flatMap((t) =>
    t.seasons.map((s) => ({ params: { code: t.code.toLowerCase(), season: String(s) }, props: { code: t.code, s } })),
  );

export const GET: APIRoute = async ({ props }) => {
  const { code, s } = props as { code: string; s: number };
  return new Response(JSON.stringify(await clubShots(code, s)), {
    headers: { "Content-Type": "application/json" },
  });
};
