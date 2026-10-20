// One match report per finished game, served at /data/reports/<comp>/<game_id>.json (docs/match_report.md,
// section 3). The Python pipeline writes web/src/data/api/reports/<comp>/<game_id>.json; with no files the
// route has no paths and the build still succeeds.
import type { APIRoute, GetStaticPaths } from "astro";
import type { MatchReport } from "../../../../lib/match_report";

const files = import.meta.glob<MatchReport>("../../../../data/api/reports/*/*.json", {
  eager: true,
  import: "default",
});

export const getStaticPaths: GetStaticPaths = () =>
  Object.entries(files).map(([path, report]) => {
    const [comp, file] = path.split("/").slice(-2);
    return { params: { comp, id: file.replace(/\.json$/, "") }, props: { report } };
  });

export const GET: APIRoute = ({ props }) => {
  const { report } = props as { report: MatchReport };
  return new Response(JSON.stringify(report), {
    headers: { "Content-Type": "application/json" },
  });
};
