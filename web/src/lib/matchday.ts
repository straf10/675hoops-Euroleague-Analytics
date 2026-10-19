// The home page's matchday: which round is on now, and which two are shown when none is.
// A round is live from its first tip-off until its last tip-off plus a game length (publish.py).
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

export type RoundWindow = Pick<MatchdayRound, "round" | "start_utc" | "end_utc">;

type MatchdayState =
  | { kind: "live"; round: number }
  | { kind: "between"; last: number | null; next: number | null };

const ms = (iso: string): number => Date.parse(iso);

/**
 * The state at `now` (epoch ms). Live when a round's window contains it (the earliest round wins
 * if two overlap). Otherwise the last round whose window has ended and the first round not yet
 * started, each by round number, or null when there is none.
 */
export function matchdayState(rounds: RoundWindow[], now: number): MatchdayState {
  const live = rounds.find((r) => ms(r.start_utc) <= now && now < ms(r.end_utc));
  if (live) return { kind: "live", round: live.round };
  let last: RoundWindow | null = null;
  let next: RoundWindow | null = null;
  for (const r of rounds) {
    if (ms(r.end_utc) <= now && (last === null || r.round > last.round)) last = r;
    if (ms(r.start_utc) > now && (next === null || r.round < next.round)) next = r;
  }
  return { kind: "between", last: last?.round ?? null, next: next?.round ?? null };
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
