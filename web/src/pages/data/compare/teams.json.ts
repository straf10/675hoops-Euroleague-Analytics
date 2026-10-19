// Every club-season for the Compare page's Teams mode, fetched when the page opens in that mode.
import type { APIRoute } from "astro";
import { teamSeasonRows } from "../../../lib/compare_seasons";

export const GET: APIRoute = async () =>
  new Response(JSON.stringify(await teamSeasonRows()), {
    headers: { "Content-Type": "application/json" },
  });
