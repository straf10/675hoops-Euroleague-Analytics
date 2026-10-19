// Accolades on Compare: a player's furthest stage per season (his club's, from achievements.json),
// his stat titles (achievements.json, stat_titles) and his career rows. Pure functions, shared by
// the build and the tests.
//
// An entry is [season, club, furthest stage, champion]. A season can hold two entries when he
// changed clubs in it, so every count below goes by season, not by entry.

export type Reached = "RS" | "PI" | "PO" | "FF" | "F" | "W";
export type AchEntry = [season: number, club: string, reached: Reached, champion: 0 | 1];

/** A season's leader on one stat among the qualified players (see the Python module). */
export type TitleStat = "pts" | "reb" | "ast" | "stl" | "blk" | "pir";
export type StatTitle = [season: number, stat: TitleStat];

const RANK: Record<Reached, number> = { RS: 0, PI: 1, PO: 2, FF: 3, F: 4, W: 5 };

export const REACHED_LABEL: Record<Reached, string> = {
  RS: "Regular season",
  PI: "Play-in",
  PO: "Playoffs",
  FF: "Final Four",
  F: "Lost the final",
  W: "Champion",
};

const TITLE_LABEL: Record<TitleStat, string> = {
  pts: "Points",
  reb: "Rebounds",
  ast: "Assists",
  stl: "Steals",
  blk: "Blocks",
  pir: "PIR",
};

/** The furthest stage in one season over all his clubs that season, with the club it came from. */
interface SeasonAch {
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

/** The stats he led that season (for example ["Points", "PIR"]); empty when he led none. */
export function seasonTitles(titles: StatTitle[], season: number): string[] {
  return titles.filter((t) => t[0] === season).map((t) => TITLE_LABEL[t[1]]);
}

interface CareerAch {
  seasons: number; // seasons with an entry, since 2007-08
  clubs: number; // distinct clubs he played for, since 2007-08
  titles: number; // seasons his club won the EuroLeague (he played for it)
  finals: number; // seasons he reached the final (lost or won)
  finalFours: number; // seasons he reached the Final Four (semis, third place or the final)
  finalFourRate: number | null; // finalFours / seasons
  playoffs: number; // seasons he reached the playoffs (the Final Four counts too)
  playoffRate: number | null; // playoffs / seasons
  statTitles: number; // stat titles (a season and a stat each; a tie counts for each leader)
}

/** Career rows from a player's entries and stat titles: counts by season, rates over the seasons he played. */
export function careerAchievements(entries: AchEntry[], statTitles: StatTitle[] = []): CareerAch {
  const seasons = new Set<number>();
  const clubs = new Set<string>();
  const titles = new Set<number>();
  const best = new Map<number, number>(); // season -> furthest rank that season
  for (const [season, club, reached, champion] of entries) {
    seasons.add(season);
    clubs.add(club);
    if (champion === 1) titles.add(season); // his club won that season
    best.set(season, Math.max(best.get(season) ?? 0, RANK[reached]));
  }
  let finals = 0;
  let finalFours = 0;
  let playoffs = 0;
  for (const rank of best.values()) {
    if (rank >= RANK.F) finals++;
    if (rank >= RANK.PO) playoffs++;
    if (rank >= RANK.FF) finalFours++;
  }
  const n = seasons.size;
  return {
    seasons: n,
    clubs: clubs.size,
    titles: titles.size,
    finals,
    finalFours,
    finalFourRate: n ? finalFours / n : null,
    playoffs,
    playoffRate: n ? playoffs / n : null,
    statTitles: statTitles.length,
  };
}

export function formatRate(rate: number | null): string {
  if (rate === null) return "–";
  return `${Math.round(rate * 100)}%`;
}
