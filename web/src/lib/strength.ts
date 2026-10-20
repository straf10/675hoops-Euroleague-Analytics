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

/** The Teams index's two SoS figures from a team's schedule strength: the venue-adjusted mean opponent
 * Elo of the games played and of the games left (higher is a harder schedule). NaN where the block has
 * no games, so the index shows a dash. The team page shows the same blocks (ScheduleStrength). */
export const sosOf = (s: Strength): { played: number; ahead: number } => {
  const figure = (b: StrengthBlock) => (b.games > 0 && b.mean_opponent_elo_adjusted !== undefined ? b.mean_opponent_elo_adjusted : NaN);
  return { played: figure(s.played), ahead: figure(s.remaining) };
};
