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

export type MatchdayState =
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
