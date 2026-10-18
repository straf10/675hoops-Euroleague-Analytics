// The team page's Passing tab: the assist network of one club-season (seasons/{y}/assists.json,
// stats/assists.py). Pure helpers: the matrix, the top connections and the matched share.
// Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

/** [passer, scorer, assists, points]: the assists a passer gave a scorer, and the points they made. */
export type PairRow = [passer: string, scorer: string, assists: number, points: number];
/** [passer, AS rows, linked AS rows, points produced]. */
export type PasserRow = [passer: string, asRows: number, linked: number, points: number];

export interface AssistClub {
  as_rows: number;
  linked: number;
  /** box-score assists over the same games that have a play-by-play */
  box: number;
  pairs: PairRow[];
  passers: PasserRow[];
}

export interface AssistsFile {
  season: number;
  clubs: Record<string, AssistClub>;
}

/** A club player with the two counts the matrix ranks by: assists and made field goals. */
export interface Person {
  id: string;
  name: string;
  slug: string;
  assists: number;
  made: number;
}

/** A pair needs this many assists to be drawn in the matrix or listed. */
export const MIN_ASSISTS = 2;
/** The matrix shows this many players: the top by assists plus made field goals. */
export const MATRIX_SIZE = 8;
/** The connections list stops at this many pairs. */
export const LIST_SIZE = 10;
/** The pairing target: the share of box-score assists that should be linked to a basket. */
export const TARGET = 0.98;

export interface Connection {
  passer: string;
  scorer: string;
  assists: number;
  points: number;
}

export interface MatrixCell {
  assists: number;
  points: number;
  /** 0 to 1: the cell's share of the largest cell, for the ink shade */
  shade: number;
}

export interface Matrix {
  players: Person[];
  /** cells[row][col]: row = passer, col = scorer; null on the diagonal and below the threshold */
  cells: (MatrixCell | null)[][];
}

export interface PassingView {
  season: number;
  matched: number | null;
  linked: number;
  asRows: number;
  box: number;
  matrix: Matrix;
  connections: Connection[];
}

/** The club's player list from the season roster: assists and made field goals per player. */
export function roster(
  lines: { id: string; name: string; slug: string; totals: number[] }[],
  fields: string[],
): Person[] {
  const at = (f: string) => fields.indexOf(f);
  const ast = at("ast");
  const fg2m = at("fg2m");
  const fg3m = at("fg3m");
  const value = (values: number[], i: number) => (i < 0 ? 0 : (values[i] ?? 0));
  return lines.map((p) => ({
    id: p.id,
    name: p.name,
    slug: p.slug,
    assists: value(p.totals, ast),
    made: value(p.totals, fg2m) + value(p.totals, fg3m),
  }));
}

/** Share of box-score assists that the pairing linked to a basket; null without box assists. */
export function matchedShare(club: Pick<AssistClub, "linked" | "box">): number | null {
  return club.box > 0 ? club.linked / club.box : null;
}

/** The top players by assists plus made field goals; players with neither are left out. */
export function topPlayers(people: Person[], n = MATRIX_SIZE): Person[] {
  return people
    .filter((p) => p.assists + p.made > 0)
    .sort((a, b) => b.assists + b.made - (a.assists + a.made) || a.name.localeCompare(b.name))
    .slice(0, n);
}

/** Pairs with at least MIN_ASSISTS assists, most assists first (ties: more points, then names). */
export function strongPairs(club: AssistClub): PairRow[] {
  return club.pairs
    .filter(([, , assists]) => assists >= MIN_ASSISTS)
    .sort((a, b) => b[2] - a[2] || b[3] - a[3] || a[0].localeCompare(b[0]) || a[1].localeCompare(b[1]));
}

/** The passer-by-scorer matrix over the given players. Cells below MIN_ASSISTS stay empty. */
export function buildMatrix(pairs: PairRow[], players: Person[]): Matrix {
  const index = new Map(players.map((p, i) => [p.id, i]));
  const counts: { assists: number; points: number }[][] = players.map(() =>
    players.map(() => ({ assists: 0, points: 0 })),
  );
  for (const [passer, scorer, assists, points] of pairs) {
    const r = index.get(passer);
    const c = index.get(scorer);
    if (r === undefined || c === undefined || r === c || assists < MIN_ASSISTS) continue;
    counts[r][c].assists += assists;
    counts[r][c].points += points;
  }
  const largest = Math.max(1, ...counts.flat().map((c) => c.assists));
  const cells = counts.map((row) =>
    row.map((c) =>
      c.assists >= MIN_ASSISTS ? { assists: c.assists, points: c.points, shade: c.assists / largest } : null,
    ),
  );
  return { players, cells };
}

/** The top connections as the list reads them: passer to scorer, assists and points. */
export function connections(
  club: AssistClub,
  names: Map<string, string>,
  n = LIST_SIZE,
): Connection[] {
  const name = (id: string) => names.get(id) ?? id;
  return strongPairs(club)
    .slice(0, n)
    .map(([passer, scorer, assists, points]) => ({
      passer: name(passer),
      scorer: name(scorer),
      assists,
      points,
    }));
}

/** The view the tab renders, or null when the season has no assist file for the club. */
export function passingView(
  season: number,
  club: AssistClub | undefined,
  people: Person[],
): PassingView | null {
  if (!club) return null;
  const top = topPlayers(people);
  const names = new Map(people.map((p) => [p.id, p.name]));
  return {
    season,
    matched: matchedShare(club),
    linked: club.linked,
    asRows: club.as_rows,
    box: club.box,
    matrix: buildMatrix(strongPairs(club), top),
    connections: connections(club, names),
  };
}
