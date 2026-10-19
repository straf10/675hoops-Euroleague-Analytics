// One season of the Teams index (its club rows and league rates), for the season switch on /teams/.
import type { APIRoute, GetStaticPaths } from "astro";
import { indexSeason } from "../../../lib/clubs_season";
import { meta } from "../../../lib/stats";

export const getStaticPaths: GetStaticPaths = async () =>
  ((await meta())?.seasons ?? []).map((s) => ({ params: { season: String(s.season) }, props: { ref: s } }));

export const GET: APIRoute = async ({ props }) => {
  const { ref } = props as { ref: { season: number; label: string; live: boolean } };
  return new Response(JSON.stringify(await indexSeason(ref)), {
    headers: { "Content-Type": "application/json" },
  });
};
