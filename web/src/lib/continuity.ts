// Returning minutes (IDEAS #17): the share of a club's last-season minutes played by players on
// this season's roster, with its biggest returners and departures. The figures come from
// teams.json (src/eurohoops/stats/export.py, `continuity`). Pure, so `node --test` runs it.

/** One player in the returning or departure lists. `sec` is his last-season seconds for the club. */
export interface ContinuityPlayer {
  id: string;
  name: string;
  sec: number;
}

/** A club's returning minutes for one season, or null when there is no last season to compare. */
export interface Continuity {
  last_sec: number;
  returning_sec: number;
  /** 0 to 1: returning seconds over last season's seconds */
  share: number;
  /** the biggest last-season minutes among players still on the roster, biggest first */
  returning: ContinuityPlayer[];
  /** the biggest last-season minutes among players who have left, biggest first */
  departures: ContinuityPlayer[];
}

/** Seconds as whole minutes. */
export const minutesOf = (sec: number): number => Math.round(sec / 60);

/** A share as a whole percentage: 0.624 -> 62. */
export const percentOf = (share: number): number => Math.round(share * 100);

/** The headline figure's percentage, or null when the club has no value. */
export const returningPercent = (c: Continuity | null): number | null => (c ? percentOf(c.share) : null);
