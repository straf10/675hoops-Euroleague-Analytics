// Coach pages: the files `eurohoops export-stats` writes to src/data/stats/coaches (stats/coaches.py).
// Every number is a raw total or a rounded expectation; the pages derive win percentages here.

export interface Counts {
  games: number;
  wins: number;
  losses: number;
  expected_wins: number;
  wins_above_expectation: number;
}

export interface CoachIndexRow extends Counts {
  slug: string;
  name: string;
  seasons_played: number[];
  clubs: string[];
}

export interface Coverage {
  season: number;
  games: number;
  with_coach: number;
}

/** The coach of a club in the latest season: their most recent game there (display code). */
export interface CoachCurrent {
  team: string;
  slug: string;
}

export interface CoachIndex {
  h2h_min_games: number;
  coverage: Coverage[];
  /** The latest season with coach rows, or null without any. */
  current_season: number | null;
  /** The day (YYYY-MM-DD) of the latest box score behind `current`; null without one. */
  current_through: string | null;
  current: CoachCurrent[];
  coaches: CoachIndexRow[];
}

export interface CoachSeason extends Counts {
  season: number;
  team: string;
  team_name: string;
}

export interface CoachClub {
  team: string;
  team_name: string;
  seasons: number[];
}

export interface CoachHeadToHead extends Counts {
  slug: string;
  name: string;
}

export interface CoachPage {
  slug: string;
  name: string;
  career: Counts;
  seasons: CoachSeason[];
  clubs: CoachClub[];
  h2h: CoachHeadToHead[];
}

/** Wins over games as a percentage with one decimal ("61.3%"); "-" with no games. */
export function winPct(c: Pick<Counts, "games" | "wins">): string {
  return c.games === 0 ? "-" : `${((100 * c.wins) / c.games).toFixed(1)}%`;
}

/** A signed figure with one decimal: "+17.4", "-3.0", "0.0". */
export function signed(value: number): string {
  const text = value.toFixed(1);
  if (/^-?0\.0$/.test(text)) return "0.0";
  return text.startsWith("-") ? text : `+${text}`;
}

/** The first and last season of a list, as "2015-16" and "2026-27" (or one season). */
export function seasonRange(seasons: number[]): string {
  if (seasons.length === 0) return "-";
  const label = (y: number) => `${y}-${String((y + 1) % 100).padStart(2, "0")}`;
  const first = Math.min(...seasons);
  const last = Math.max(...seasons);
  return first === last ? label(first) : `${label(first)} to ${label(last)}`;
}

/** One entry of the coach search list the coaches page embeds (every coach, any season). */
export interface CoachSearchEntry {
  name: string;
  href: string;
  seasons: number[];
  clubs: string[];
}

/** Lower case, no accents, single spaces: "Željko  Obradović" becomes "zeljko obradovic". */
export function normaliseName(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
}

/** The entries whose name holds every word of the query (parts of words, any order); none for a blank query. */
export function searchCoaches<T extends { name: string }>(entries: T[], query: string): T[] {
  const words = normaliseName(query).split(" ").filter(Boolean);
  if (words.length === 0) return [];
  return entries.filter((e) => {
    const name = normaliseName(e.name);
    return words.every((w) => name.includes(w));
  });
}
