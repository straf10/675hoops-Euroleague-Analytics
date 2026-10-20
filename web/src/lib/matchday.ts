// The home page's matchday: which rounds to show, from the rounds and the open ones.
import type { Team } from "./format";

export interface MatchdayGame {
  game_id: string;
  tipoff_utc: string;
  tipoff_time_confirmed: boolean;
  home: Team;
  away: Team;
  /** The logged chance that the home side wins; null when no forecast was logged before tip-off. */
  p_home: number | null;
  played: boolean;
  home_score: number | null;
  away_score: number | null;
  /** Whether the logged pick held; null when unplayed, unforecast or not provable. */
  hit: boolean | null;
}

export interface MatchdayRound {
  round: number;
  start_utc: string;
  end_utc: string;
  games: MatchdayGame[];
}

/**
 * What the home page's matchday shows for one competition. While any round is open (a logged
 * forecast and a game still to play, site.json open_rounds) that is all it shows: each open round,
 * earliest first, so a double week shows both until the earlier one is finished. With none open it
 * shows the latest finished round's recap and the next round's fixtures.
 */
export interface MatchdayPlan {
  open: MatchdayRound[];
  recap: MatchdayRound | null;
  next: MatchdayRound | null;
}

/**
 * The plan from every round of the season and the round numbers that are open. A round with a
 * played game and no longer open is finished; a round with no played game is not started yet.
 */
export function matchdayPlan(rounds: MatchdayRound[], openNumbers: readonly number[]): MatchdayPlan {
  const open = new Set(openNumbers);
  const byRound = (a: MatchdayRound, b: MatchdayRound) => a.round - b.round;
  const openRounds = rounds.filter((r) => open.has(r.round)).sort(byRound);
  if (openRounds.length > 0) return { open: openRounds, recap: null, next: null };
  const started = rounds.filter((r) => r.games.some((g) => g.played)).sort(byRound);
  const unstarted = rounds.filter((r) => !r.games.some((g) => g.played)).sort(byRound);
  return { open: [], recap: started.at(-1) ?? null, next: unstarted[0] ?? null };
}

/** Games the logged picks got right, out of those scored (a pick and a played, provable game). */
export function scorecard(round: MatchdayRound): { right: number; scored: number } {
  const scored = round.games.filter((g) => g.hit !== null);
  return { right: scored.filter((g) => g.hit === true).length, scored: scored.length };
}

/**
 * A finished game against the model's expected home margin, both in whole points as the page
 * shows them. `predicted` and `actual` are home-side margins (negative: the away side won by that
 * much); `off` is their gap.
 */
export interface MarginCheck {
  predicted: number;
  actual: number;
  off: number;
}

/** The margin check for a game with a final score and a logged expected margin; null otherwise. */
export function marginCheck(g: MatchdayGame, expMargin: number | null | undefined): MarginCheck | null {
  if (!g.played || g.home_score === null || g.away_score === null || expMargin == null) return null;
  const predicted = Math.round(expMargin) + 0; // + 0 turns a rounded -0 into 0
  const actual = g.home_score - g.away_score;
  return { predicted, actual, off: Math.abs(predicted - actual) };
}

/** Mean absolute margin error over the games that have a check; null when none does. */
export function averageMiss(checks: (MarginCheck | null)[]): number | null {
  const known = checks.filter((c): c is MarginCheck => c !== null);
  if (known.length === 0) return null;
  return known.reduce((sum, c) => sum + c.off, 0) / known.length;
}

/**
 * "Predicted PAN by 4 · Final PAN by 9 · off by 5". The predicted side follows the sign of the
 * rounded margin ("Predicted even" at 0); the final side is the winner.
 */
export function marginText(g: MatchdayGame, c: MarginCheck): string {
  const side = (margin: number) => (margin > 0 ? g.home.code : g.away.code);
  const predicted = c.predicted === 0 ? "Predicted even" : `Predicted ${side(c.predicted)} by ${Math.abs(c.predicted)}`;
  const final = c.actual === 0 ? "Final even" : `Final ${side(c.actual)} by ${Math.abs(c.actual)}`;
  return `${predicted} · ${final} · off by ${c.off}`;
}
