// One round of one competition's forecast record, for the forecast page's round picker: the page carries
// only its default round. The games are those the published model called, the same rows the page prints.
import type { APIRoute, GetStaticPaths } from "astro";
import raw from "../../../../data/site.json";
import type { SiteData } from "../../../../lib/format";
import type { FcGame } from "../../../../lib/forecasts";
import { leadModel, roundGroups } from "../../../../lib/forecast_rounds";

const data = raw as SiteData;

export const getStaticPaths: GetStaticPaths = () =>
  data.competitions.flatMap((c) => {
    const fc = c.forecasts;
    const model = leadModel(fc);
    if (!fc || !model) return [];
    return roundGroups(fc.games, model).map((g) => ({
      params: { comp: c.key, round: g.id },
      props: { games: g.games },
    }));
  });

export const GET: APIRoute = async ({ props }) => {
  const { games } = props as { games: FcGame[] };
  return new Response(JSON.stringify({ games }), {
    headers: { "Content-Type": "application/json" },
  });
};
