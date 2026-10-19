// The Compare page's Teams mode data: every published club-season, with the teams index's figures and
// the shot shares. Built at build time into data/compare/teams.json; the page fetches it only when the
// visitor opens Teams mode, so the page HTML does not grow with the number of seasons.
import { meta, season } from "./stats";
import { clubRows } from "./team";
import { withShots, type BandCounts, type TeamSeasonRows } from "./compare_teams";

export async function teamSeasonRows(): Promise<TeamSeasonRows[]> {
  const m = await meta();
  if (!m) return [];
  return Promise.all(
    m.seasons.map(async (s) => {
      const d = await season(s.season, "teams");
      const bands = Object.fromEntries(d.teams.map((t) => [t.code, t.bands as BandCounts]));
      return { season: s.season, label: s.label, rows: withShots(clubRows(d.fields, d.teams), bands) };
    }),
  );
}
