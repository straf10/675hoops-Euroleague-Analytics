// The season the analysis sections read (Against the league, shot chart and quality, on/off, clutch):
// early-season samples say little, so it is his latest season with at least MIN_ANALYSIS_GAMES games
// (the live season once he has played that many), else simply his latest season.

import { totalsOf } from "./player";
import type { PlayerSeason } from "./stats";

const MIN_ANALYSIS_GAMES = 10;

/** `seasons` oldest first, never empty. */
export function analysisSeason(seasons: PlayerSeason[]): PlayerSeason {
  const full = seasons.filter((s) => totalsOf(s.fields, s.totals).gp >= MIN_ANALYSIS_GAMES);
  return full[full.length - 1] ?? seasons[seasons.length - 1];
}
