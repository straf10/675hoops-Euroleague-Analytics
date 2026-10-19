// Titles and meta text for EuroLeague games: what a searcher types ("Team A vs Team B",
// "EuroLeague") and our pre-game call, as words. Pure: plain data in, strings out.

const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** "6 Oct 2022" for a calendar date (YYYY-MM-DD). */
export function dayLabel(date: string): string {
  return DAY.format(new Date(`${date}T12:00:00Z`));
}

interface GameTitleInput {
  /** Club names as shown on the site (home side first). */
  home: string;
  away: string;
  /** The calendar day (YYYY-MM-DD) in Athens, the zone the site shows times in. */
  date: string;
  /** Both scores when the game is played; omitted for a game still to play. */
  homeScore?: number;
  awayScore?: number;
}

/**
 * "Team A 85–80 Team B: EuroLeague, 6 Oct 2022" when played, "Team A vs Team B: EuroLeague, 6 Oct
 * 2022" when not. The page title adds the site name after it.
 */
export function gameTitle(g: GameTitleInput): string {
  const played = g.homeScore !== undefined && g.awayScore !== undefined;
  const head = played ? `${g.home} ${g.homeScore}–${g.awayScore} ${g.away}` : `${g.home} vs ${g.away}`;
  return `${head}: EuroLeague, ${dayLabel(g.date)}`;
}

/** One row of the forecast record: the models that logged the game before tip-off. */
export interface PreGameRow {
  game_id: string;
  models: Record<string, { p_home: number }>;
}

/** Our pre-tip-off chance that the home side wins, from the headline model; null when none was logged. */
export function preGameHomeChance(rows: PreGameRow[], model: string, gameId: string): number | null {
  const row = rows.find((r) => r.game_id === gameId);
  const p = row?.models[model]?.p_home;
  return p === undefined ? null : p;
}

/** A probability as a whole percentage: 0.6517 reads 65%. */
export const percent = (p: number): string => `${Math.round(p * 100)}%`;
