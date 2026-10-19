// On/off and clutch figures from the raw totals in stats/onoff.json (lib/stats.ts).

import type { OnOffSide, OnOffSeason } from "./stats";

const per100 = (x: number, poss: number): number | null => (poss > 0 ? (100 * x) / poss : null);

export interface Rates {
  minutes: number;
  off: number | null; // points scored per 100 possessions
  def: number | null; // points allowed per 100 possessions
  net: number | null;
}

function rates(s: OnOffSide): Rates {
  const off = per100(s.pf, s.poss);
  const def = per100(s.pa, s.poss);
  return { minutes: s.sec / 60, off, def, net: off !== null && def !== null ? off - def : null };
}

export interface OnOffView {
  on: Rates;
  off: Rates;
}

/** null when he has no possessions on court or none off it (no difference to show). */
export function onOffView(r: OnOffSeason): OnOffView | null {
  const on = rates(r.on);
  const off = rates(r.off);
  return on.net === null || off.net === null ? null : { on, off };
}

export interface Clutch {
  minutes: number;
  net: number | null;
  pts: number;
  poss: number;
}

/** null when he never played clutch time. */
export function clutchView(r: OnOffSeason): Clutch | null {
  const c = r.clutch;
  if (!(c.sec > 0)) return null;
  return { minutes: c.sec / 60, net: per100(c.pf - c.pa, c.poss), pts: c.pts, poss: c.poss };
}
