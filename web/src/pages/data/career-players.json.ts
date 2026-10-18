// Every player's career totals (summed over his seasons) in the shape of a season's players file,
// for the Compare percentile profile's career pool. Built once at build time.
import type { APIRoute } from "astro";
import { meta, season } from "../../lib/stats";

export const GET: APIRoute = async () => {
  const m = await meta();
  const files = await Promise.all((m?.seasons ?? []).map((s) => season(s.season, "players")));
  const fields = files[0]?.fields ?? [];
  const careers = new Map<string, { id: string; name: string; slug: string; pos: string | null; totals: number[] }>();
  for (const file of files) {
    if (file.fields.length !== fields.length) continue;
    for (const p of file.players) {
      const values = p.totals.season;
      const cur = careers.get(p.id);
      if (!cur) {
        careers.set(p.id, { id: p.id, name: p.name, slug: p.slug, pos: p.pos ?? null, totals: [...values] });
      } else {
        cur.totals = cur.totals.map((v, i) => v + (values[i] ?? 0));
        cur.name = p.name;
        cur.slug = p.slug;
        cur.pos = p.pos ?? cur.pos;
      }
    }
  }
  // Same row shape as a season's players file: totals.season holds the career sums.
  const players = [...careers.values()].map((c) => ({ id: c.id, name: c.name, slug: c.slug, teams: [], dorsal: "", totals: { season: c.totals }, bands: {}, pos: c.pos }));
  const body = { season: 0, fields, bands: [], players };
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
};
