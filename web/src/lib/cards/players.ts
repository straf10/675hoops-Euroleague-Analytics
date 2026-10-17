// The player cards' inputs: the players of the live season, and what each card shows from the data
// the player page reads (the same loaders, so the card and the page cannot disagree).

import { analysisSeason } from "../analysis";
import { COMPETITIONS, PROJECTED, playerM6, seasonLabel } from "../m6";
import { position } from "../position";
import { meta, playerData, playerIndex, type PlayerIndexRow, type PlayerData } from "../stats";
import { playerSvg, type CardRate, type CardTwin, type PlayerCardInput } from "./player";

/** The live season, as the site's metadata marks it. */
export async function liveSeason(): Promise<number | null> {
  const m = await meta();
  return m?.seasons.find((s) => s.live)?.season ?? null;
}

/** Players whose latest season is the live one: the only players with a card. */
export async function currentPlayers(): Promise<PlayerIndexRow[]> {
  const live = await liveSeason();
  if (live === null) return [];
  return (await playerIndex()).filter((p) => p.seasons.length > 0 && Math.max(...p.seasons) === live);
}

/** The card's input for one player, from the page's data. Sections with no data come back empty. */
export async function playerCardInput(p: PlayerIndexRow): Promise<PlayerCardInput | null> {
  const m = (await meta())!;
  const live = m.seasons.find((s) => s.live);
  if (!live) return null;
  const data: PlayerData = await playerData(p);
  const seasons = data.seasons;
  const latest = seasons[seasons.length - 1];
  if (!latest || latest.season !== live.season) return null;
  const { projection, similar } = await playerM6(p.id);

  const rates: CardRate[] = [];
  const proj = projection?.season === live.season ? projection.projections[0] : undefined;
  if (proj) {
    for (const key of ["pts", "ast", "ts"]) {
      const band = proj.stats[key];
      const info = PROJECTED.find((s) => s.key === key);
      if (!band || !info) continue;
      rates.push({ label: info.label, unit: info.unit, pct: !!info.pct, mean: band.mean, lo80: band.lo80, hi80: band.hi80 });
    }
  }

  // The shot season is the player page's: his latest season with a full-enough sample, when it has shots.
  const withShots = seasons.filter((s) => s.hex.length > 0);
  const analysis = analysisSeason(seasons);
  const shotSeason = withShots.find((s) => s.season === analysis.season) ?? withShots.at(-1);

  const twinRows = (similar?.similar ?? []).slice(0, 5);
  const twins: CardTwin[] = twinRows.map((r) => ({
    name: r.name,
    club: `${seasonLabel(r.season)}, ${COMPETITIONS[r.competition] ?? r.competition}`,
    score: r.score,
  }));
  const query = twinRows[0]?.query_season ?? similar?.season;

  return {
    name: data.name,
    club: latest.teams.map((code) => m.teams[code] ?? code).join(", "),
    position: position(latest.pos) ?? null,
    season: live.label,
    projection: proj && rates.length ? { season: seasonLabel(projection!.season), rates } : null,
    shots: shotSeason && shotSeason.dots.length ? { season: shotSeason.label, dots: shotSeason.dots } : null,
    twins: twins.length && query !== undefined ? { query: seasonLabel(query), list: twins } : null,
  };
}

/** The SVG of a player's card by slug, or null when he has none (not in the live season). */
export async function playerSvgFor(slug: string): Promise<string | null> {
  const row = (await playerIndex()).find((p) => p.slug === slug);
  const input = row ? await playerCardInput(row) : null;
  return input ? playerSvg(input) : null;
}
