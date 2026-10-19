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

export interface CoachIndex {
  h2h_min_games: number;
  coverage: Coverage[];
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
  style: CoachStyle | null;
}

/** Coaching style (stats/coach_style.py): the coach's figures and the league's over the same seasons. */
export interface CoachStyle {
  ato: { possessions: number; points: number; ppp: number | null; league_ppp: number | null };
  clutch: {
    games: number;
    team_games: number;
    wins: number;
    losses: number;
    league_share: number | null;
  };
  rotation: {
    games: number;
    players_per_game: number | null;
    top7_share: number | null;
    league_players_per_game: number | null;
    league_top7_share: number | null;
  };
  challenges: {
    from_season: number;
    games: number;
    per_game: number | null;
    late_share: number | null;
    league_per_game: number | null;
    league_late_share: number | null;
  } | null;
}

/** Wins over games as a percentage with one decimal ("61.3%"); "-" with no games. */
export function winPct(c: Pick<Counts, "games" | "wins">): string {
  return c.games === 0 ? "-" : `${((100 * c.wins) / c.games).toFixed(1)}%`;
}

/** A signed figure with one decimal: "+17.4", "-3.0", "0.0". */
/** A per-game figure with the given decimals ("1.05"); "-" without a value. */
export function rate(value: number | null, digits = 2): string {
  return value === null ? "-" : value.toFixed(digits);
}

/** A share as a whole percentage ("55%"); "-" without a value. */
export function share(value: number | null): string {
  return value === null ? "-" : `${Math.round(100 * value)}%`;
}

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
