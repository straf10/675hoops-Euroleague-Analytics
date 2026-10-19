// One season of the Teams index (the club table and the charts' data), built at build time. The page
// embeds only the season it opens on; every other season is fetched from data/clubs/{season}.json.
import { sourceCode, teamFactors } from "./live";
import type { IndexRow, IndexSeason } from "./ranking";
import { sosOf } from "./strength";
import { clubRows, leagueRates } from "./team";
import { season } from "./stats";

export interface SeasonRef {
  season: number;
  label: string;
  live: boolean;
}

// The live season's rows carry schedule strength (played and ahead) from the factors file.
const withSos = (rows: IndexRow[], live: number) =>
  Promise.all(
    rows.map(async (r) => {
      const factors = await teamFactors("euroleague", sourceCode("euroleague", r.code));
      if (!factors || factors.season !== live) return r;
      const { played, ahead } = sosOf(factors.schedule_strength);
      return { ...r, f: { ...r.f, sos_played: played, sos_ahead: ahead } };
    }),
  );

export async function indexSeason(ref: SeasonRef): Promise<IndexSeason> {
  const data = await season(ref.season, "teams");
  const rows = clubRows(data.fields, data.teams);
  return {
    label: ref.label,
    league: leagueRates(data.fields, data.league),
    rows: ref.live ? await withSos(rows, ref.season) : rows,
  };
}
