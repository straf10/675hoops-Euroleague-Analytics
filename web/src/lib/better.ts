// The one place that says which way is good for each metric on the site: "higher", "lower", or
// "neither" for a style measure (usage, pace) with no better side. Delta arrows, the Against-the-
// league boards, the team Four Factors and the Compare ranks all read it through `betterOf`.
// No runtime imports, so Node can run it directly.

/** Which direction is good for the subject. "neither" keeps the arrow ink and is not ranked. */
export type BetterIs = "higher" | "lower" | "neither";

/** Metrics where a lower figure is good. Opponent measures count as lower when they are what the
 * club allows (eFG%, free-throw rate, rating); turnovers forced (`otov`) is higher: the club wants
 * more of them. Keys not listed here are "higher". */
const DIRECTION = new Map<string, BetterIs>([
  // Lower is better
  ["tov", "lower"], // turnovers (player) and turnover rate (club)
  ["pf", "lower"],
  ["fouls", "lower"],
  ["drtg", "lower"], // defensive rating: points allowed per 100 possessions
  ["oefg", "lower"], // opponent eFG%
  ["oftr", "lower"], // opponent free-throw rate
  ["tov_pct", "lower"], // turnover % (TOV_PCT in measures.ts): share of possessions that end in a turnover
  // Higher is better (listed where the site ranks them, so the table reads whole)
  ["pts", "higher"],
  ["reb", "higher"],
  ["ast", "higher"],
  ["ts", "higher"],
  ["pir", "higher"],
  ["ortg", "higher"],
  ["efg", "higher"],
  ["oreb", "higher"],
  ["ftr", "higher"],
  ["otov", "higher"], // turnovers forced
  ["dreb", "higher"],
  ["net", "higher"], // net rating: points scored minus allowed per 100 possessions
  ["ast_tov", "higher"],
  ["ast_pct", "higher"],
  ["reb_pct", "higher"],
  ["rapm", "higher"],
  // No better side (styles, like usage and pace)
  ["usg", "neither"],
  ["pace", "neither"], // possessions per 40 minutes: a style, not a better side
  ["tpar", "neither"], // three-point attempt rate (club): a style
  ["otpar", "neither"], // opponent three-point attempt rate: what the club allows, a style
  // Returning minutes: neither. Continuity is not better or worse by itself: a club can keep its
  // roster and still be weak, or rebuild and be strong. It is context, not a rating.
  ["returning", "neither"],
  // Schedule strength (venue-adjusted mean opponent Elo): higher is a harder schedule, not a better
  // one, so it is ranked high-first and carries no colour.
  ["sos_played", "neither"],
  ["sos_ahead", "neither"],
]);

/** The direction of a metric by its key. Unknown keys read as "higher". */
export function betterOf(key: string): BetterIs {
  return DIRECTION.get(key) ?? "higher";
}
