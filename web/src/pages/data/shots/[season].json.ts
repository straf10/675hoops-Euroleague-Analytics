// One season's located attempts for the Shots explorer (fetched on first use and on a season
// change), packed: see packAttempts in lib/shots.ts.
import type { APIRoute, GetStaticPaths } from "astro";
import { PUBLISH_SHOTS_DATA, packAttempts } from "../../../lib/shots";
import { explorerData, meta } from "../../../lib/stats";

export const getStaticPaths: GetStaticPaths = async () => {
  if (!PUBLISH_SHOTS_DATA) return [];
  const m = await meta();
  return (m?.seasons ?? []).map((s) => ({ params: { season: String(s.season) } }));
};

export const GET: APIRoute = async ({ params }) => {
  const a = await explorerData(Number(params.season));
  return new Response(JSON.stringify(a && packAttempts(a)), { headers: { "Content-Type": "application/json" } });
};
