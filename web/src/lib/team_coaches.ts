// The coaches a team page lists: its current head coach first, then the most recent previous
// coaches, with the rest counted. Pure: the page loads each coach's last season with the club.

export interface ClubCoach {
  slug: string;
  name: string;
  /** The last season the coach was at this club. */
  last: number;
}

/** How many coaches the team page names before "+N more". */
export const COACHES_SHOWN = 4;

/**
 * The coaches to name: the current one first (when there is one), then by last season, newest first.
 * `more` counts the coaches not named.
 */
export function shownCoaches(
  coaches: ClubCoach[],
  current: string | undefined,
  shown = COACHES_SHOWN,
): { shown: ClubCoach[]; more: number } {
  const ordered = [...coaches].sort(
    (a, b) => Number(b.slug === current) - Number(a.slug === current) || b.last - a.last,
  );
  return { shown: ordered.slice(0, shown), more: Math.max(0, ordered.length - shown) };
}
