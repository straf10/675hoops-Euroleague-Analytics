// Achievements on Compare: a player's furthest phase per season (the club's, from achievements.json)
// and his career rows. Pure functions, shared by the build and the tests.
//
// An entry is [season, club, furthest stage, champion]. A season can hold two entries when he
// changed clubs in it, so every count below goes by season, not by entry.

export type Reached = "RS" | "PI" | "PO" | "FF" | "F" | "W";
export type AchEntry = [season: number, club: string, reached: Reached, champion: 0 | 1];

const RANK: Record<Reached, number> = { RS: 0, PI: 1, PO: 2, FF: 3, F: 4, W: 5 };

export const REACHED_LABEL: Record<Reached, string> = {
  RS: "Regular season",
  PI: "Play-in",
  PO: "Playoffs",
  FF: "Final Four",
  F: "Lost the final",
  W: "Champion",
};

/** The first season the achievements cover; careers that started earlier are cut short. */
export const ACH_SINCE = "2007-08";

/** The furthest stage in one season over all his clubs that season, with the club it came from. */
export interface SeasonAch {
  reached: Reached;
  club: string;
  clubs: number; // how many clubs he played for that season
  champion: boolean;
}

/** One season's furthest stage. Null when he has no entry for that season. */
export function seasonAchievement(entries: AchEntry[], season: number): SeasonAch | null {
  const own = entries.filter((e) => e[0] === season);
  if (!own.length) return null;
  const top = own.reduce((a, b) => (RANK[b[2]] > RANK[a[2]] ? b : a));
  return { reached: top[2], club: top[1], clubs: own.length, champion: own.some((e) => e[3] === 1) };
}

export interface CareerAch {
  seasons: number; // seasons with an entry, since 2007-08
  titles: number; // seasons he played in the final his club won
  finalFours: number; // seasons he reached the Final Four (semis, third place or the final)
  finalFourRate: number | null; // finalFours / seasons
  playoffs: number; // seasons he reached the playoffs (the Final Four counts too)
  playoffRate: number | null; // playoffs / seasons
}

/** Career rows from a player's entries: counts by season, rates over the seasons he played. */
export function careerAchievements(entries: AchEntry[]): CareerAch {
  const seasons = new Set<number>();
  const titles = new Set<number>();
  const best = new Map<number, number>(); // season -> furthest rank that season
  for (const [season, , reached, champion] of entries) {
    seasons.add(season);
    if (champion === 1 && reached === "W") titles.add(season); // he played in the final
    best.set(season, Math.max(best.get(season) ?? 0, RANK[reached]));
  }
  let finalFours = 0;
  let playoffs = 0;
  for (const rank of best.values()) {
    if (rank >= RANK.PO) playoffs++;
    if (rank >= RANK.FF) finalFours++;
  }
  const n = seasons.size;
  return {
    seasons: n,
    titles: titles.size,
    finalFours,
    finalFourRate: n ? finalFours / n : null,
    playoffs,
    playoffRate: n ? playoffs / n : null,
  };
}

export function formatRate(rate: number | null): string {
  if (rate === null) return "–";
  return `${Math.round(rate * 100)}%`;
}
