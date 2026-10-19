// The home page's headline numbers, rounded down so they never overstate what is in the data.
const count = (n: number): string => n.toLocaleString("en-GB");

export interface Volume {
  games: number;
  seasons: number;
  actions?: number;
}

/** Games to the nearest hundred, down, with "+": 5,102 -> "5,100+". */
export const roundedGames = (n: number): string => `${count(Math.floor(n / 100) * 100)}+`;

/** Actions to the nearest 0.1 million, down, with "M+": 2,620,369 -> "2.6M+". */
export const roundedActions = (n: number): string => `${(Math.floor(n / 100_000) / 10).toFixed(1)}M+`;

/** The three headline figures, EuroLeague only (the marts and the play-by-play cache). */
export function headlineNumbers(v: Volume): { seasons: string; games: string; actions: string | null } {
  return {
    seasons: count(v.seasons),
    games: roundedGames(v.games),
    actions: v.actions === undefined ? null : roundedActions(v.actions),
  };
}
