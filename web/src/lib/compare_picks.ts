// The pick rules for Compare's player mode, kept apart from compare.ts (which imports the page's
// data code) so `node --test` runs them directly. A player is picked once, whatever his season or
// scope: a second pick of the same player is refused, and the picker stops offering him.

export interface PlayerPick {
  slug: string;
  season: number; // 0 = career (or the career scope)
}

/** The picks with each player once, the first pick of a player kept. */
export function uniquePlayers<T extends { slug: string }>(picks: T[]): T[] {
  const seen = new Set<string>();
  return picks.filter((p) => {
    if (seen.has(p.slug)) return false;
    seen.add(p.slug);
    return true;
  });
}

/** Adds a player unless he is already picked or the list is full. Returns the list unchanged then. */
export function addPlayer<T extends PlayerPick>(picks: T[], pick: T, max: number): T[] {
  if (picks.length >= max || picks.some((p) => p.slug === pick.slug)) return picks;
  return [...picks, pick];
}

/**
 * The names the player picker still offers: every [label, slug] whose player is not picked yet.
 * A picked player is removed from the picker rather than disabled, since a datalist cannot disable
 * its options.
 */
export function unpickedNames(names: [label: string, slug: string][], picks: PlayerPick[]): string[] {
  const picked = new Set(picks.map((p) => p.slug));
  return names.filter(([, slug]) => !picked.has(slug)).map(([label]) => label);
}
