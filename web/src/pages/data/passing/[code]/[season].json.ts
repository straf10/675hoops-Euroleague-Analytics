// One club's assist network for one season, rendered by the Passing component, for the team page's
// season switch. The page itself carries only the season it opens on.
import type { APIRoute, GetStaticPaths } from "astro";
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import Passing from "../../../../components/team/Passing.astro";
import { teamIndex, teamOwn } from "../../../../lib/stats";

export const getStaticPaths: GetStaticPaths = async () =>
  (await teamIndex()).flatMap((t) =>
    t.seasons.map((s) => ({ params: { code: t.code.toLowerCase(), season: String(s) }, props: { code: t.code, s } })),
  );

export const GET: APIRoute = async ({ props }) => {
  const { code, s } = props as { code: string; s: number };
  const own = await teamOwn(code, s);
  const seasons = own ? [{ season: s, roster: own.roster, fields: own.rosterFields }] : [];
  const container = await AstroContainer.create();
  const html = await container.renderToString(Passing, { props: { code, current: s, seasons } });
  return new Response(JSON.stringify({ html }), { headers: { "Content-Type": "application/json" } });
};
