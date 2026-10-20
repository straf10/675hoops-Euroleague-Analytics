// One season of the coaches list (its coach rows, the same shape the page embeds), for the season
// switch on /coaches/. Only the season the page opens on is embedded; the others load from here.
import type { APIRoute, GetStaticPaths } from "astro";
import { coachIndex, coachSeasons } from "../../../lib/coach_files";
import { namedSeasons, seasonOf } from "../../../lib/coaches";

export const getStaticPaths: GetStaticPaths = async () => {
  const index = await coachIndex();
  const seasons = index ? namedSeasons(index.coverage) : [];
  return seasons.map((season) => ({ params: { season: String(season) } }));
};

export const GET: APIRoute = async ({ params }) => {
  const rows = seasonOf(await coachSeasons(), Number(params.season));
  return new Response(JSON.stringify(rows), {
    headers: { "Content-Type": "application/json" },
  });
};
