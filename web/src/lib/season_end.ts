// Projected season-end points per game (owner's formula, SITE_FEEDBACK Phase C #6, per game played):
//
//   projected PPG = M6 points per 100 possessions x minutes share x team pace / 100
//   season end    = (points so far + projected PPG x games left) / (his games so far + games left)
//
// minutes share = his minutes per game played / (team minutes per game / 5), from this season once
// he has played at least MIN_GAMES games, else from last season. Team pace = his current team's
// possessions per 40 minutes: this season's once the team has played MIN_GAMES games, else last
// season's. Games left = 2 x (teams - 1) minus the games his club has played; he is assumed to play
// every one. Pure numbers in and out, so every step can be checked by hand.

export const MIN_GAMES = 5;

export interface Basis {
  /** His seconds on court and games played in the season the share is read from. */
  sec: number;
  gp: number;
  /** That club's game seconds (40 minutes a game, more with overtime) and games; its minutes / 5. */
  teamSec: number;
  teamGp: number;
}

/** His share of one player's slot in the team's minutes: 1 is a man who never sits. */
export const minutesShare = ({ sec, gp, teamSec, teamGp }: Basis): number =>
  gp > 0 && teamSec > 0 && teamGp > 0 ? sec / gp / (teamSec / teamGp) : 0;

/** The team's possessions per 40 minutes. */
export const pacePer40 = (poss: number, gameSec: number): number => (gameSec > 0 ? (poss * 2400) / gameSec : 0);

export const totalGames = (teams: number): number => 2 * (teams - 1);

export interface SeasonEndInput {
  /** M6 projected points per 100 possessions. */
  per100: number;
  share: number;
  pace: number;
  pointsSoFar: number;
  gamesPlayed: number;
  teamGamesPlayed: number;
  total: number;
}

export interface SeasonEnd {
  projectedPpg: number;
  gamesLeft: number;
  /** Projected points per game at season's end. */
  seasonEnd: number;
  /** Points a game so far (his games played). */
  soFar: number;
}

export function seasonEnd(i: SeasonEndInput): SeasonEnd | null {
  const gamesLeft = i.total - i.teamGamesPlayed;
  if (!(i.per100 > 0) || !(i.share > 0) || !(i.pace > 0) || !(i.total > 0) || gamesLeft <= 0) return null;
  const projectedPpg = (i.per100 * i.share * i.pace) / 100;
  return {
    projectedPpg,
    gamesLeft,
    seasonEnd: (i.pointsSoFar + projectedPpg * gamesLeft) / (i.gamesPlayed + gamesLeft),
    soFar: i.gamesPlayed ? i.pointsSoFar / i.gamesPlayed : 0,
  };
}
