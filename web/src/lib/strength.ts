// Schedule strength of a team (the API's factors file, schedule_strength): the opponents it has
// played, the games it has left and the next few. Pure, so the page and the tests share it.

/** One block: the opponents in some set of games. An empty block has no figures, only a reason. */
export interface StrengthBlock {
  games: number;
  reason?: string | null;
  home?: number;
  away?: number;
  /** Mean opponent Elo, as rated. */
  mean_opponent_elo?: number;
  /** Mean opponent Elo less the home-court advantage when the team is at home, plus it when away. */
  mean_opponent_elo_adjusted?: number;
  /** Expected win probability (0 to 1) of an average team in the same games and venues. */
  average_team_win_pct?: number;
  /** Mean days of rest of the team before these games. */
  rest_days?: number;
  /** Mean days of rest of the opponents before these games. */
  opponent_rest_days?: number;
}

export interface Strength {
  rating?: string;
  next?: number;
  played: StrengthBlock;
  remaining: StrengthBlock;
  next5: StrengthBlock;
}

/** True when the team has any games in the season (played or left): the Schedule tab shows then. */
export const hasSchedule = (s: Strength | null | undefined): s is Strength =>
  !!s && s.played.games + s.remaining.games > 0;

/** The average team's win share as a whole percentage: 0.4612 gives 46. */
export const winPct = (p: number): string => `${Math.round(100 * p)}%`;

/** One decimal, with a thousands separator: 1506.83 gives "1,506.8". */
export const elo = (x: number): string =>
  x.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** One decimal of days: 4.96 gives "5.0". */
export const days = (x: number): string => x.toFixed(1);

/** "16 at home, 17 away". */
export function venueLine(b: StrengthBlock): string {
  const home = b.home ?? 0;
  const away = b.away ?? 0;
  return `${home} at home, ${away} away`;
}
