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
  network: Network;
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
    .filter(([p, s, assists]) => p !== s && Number.isFinite(assists) && assists >= MIN_ASSISTS)
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
    network: network(club, names),
  };
}

// ---- The network: players at the vertices of a polygon, a line for each pair that assisted ----

/** The polygon draws this many players: the top by assists given and received. */
export const NETWORK_SIZE = 8;
/** The thinnest and thickest line, in viewBox units (the SVG scales with its column). A pair with
 *  one assist is EDGE_MIN; the team's largest pair is EDGE_MAX; the widths between are linear. */
export const EDGE_MIN = 1;
export const EDGE_MAX = 9;
/** Opacity: the weakest pair is OPACITY_MIN, the strongest OPACITY_MAX, linear in between. */
export const OPACITY_MIN = 0.25;
export const OPACITY_MAX = 1;
/** Above this many drawn pairs, the pairs with one assist are not drawn: the picture would be a tangle. */
export const MAX_DRAWN_PAIRS = 20;
/** The viewBox: the polygon's centre and radius, and the gap between a vertex and its label. */
export const VIEW = { w: 560, h: 440, cx: 280, cy: 220, r: 150, gap: 18 } as const;

export interface NetPlayer {
  id: string;
  name: string;
  /** the label on the vertex: the surname, with the initial when two drawn players share it */
  label: string;
  given: number;
  received: number;
  /** the vertex */
  x: number;
  y: number;
  /** the label's text anchor and its position (the baseline already moved clear of the vertex) */
  anchor: "start" | "middle" | "end";
  lx: number;
  ly: number;
}

export interface NetEdge {
  /** indices into Network.players, a < b */
  a: number;
  b: number;
  /** assists a to b, and b to a */
  ab: number;
  ba: number;
  /** the cooperation: ab + ba */
  total: number;
  /** stroke width in viewBox units */
  width: number;
  /** stroke opacity, 0 to 1 */
  opacity: number;
}

export interface Network {
  /** in vertex order, clockwise from the top */
  players: NetPlayer[];
  /** thinnest first, so the thick lines paint on top */
  edges: NetEdge[];
  /** pairs with one assist that are not drawn, because there are more than MAX_DRAWN_PAIRS pairs */
  hiddenPairs: number;
}

const SUFFIX = /^(jr\.?|sr\.?|i{2,3}|iv)$/i;

/** The surname of a player name: the last token, skipping a generational suffix. */
function surnameOf(name: string): { first: string; last: string } {
  const tokens = name.trim().split(/\s+/).filter(Boolean);
  let end = tokens.length;
  while (end > 1 && SUFFIX.test(tokens[end - 1])) end -= 1;
  return { first: tokens[0] ?? "", last: tokens[end - 1] ?? name };
}

/** Vertex labels: the surname, or the initial and surname where two players share one. */
export function labels(names: string[]): string[] {
  const parts = names.map(surnameOf);
  const count = new Map<string, number>();
  for (const { last } of parts) count.set(last, (count.get(last) ?? 0) + 1);
  return parts.map(({ first, last }, i) =>
    (count.get(last) ?? 0) > 1 && first ? `${first.charAt(0)}. ${last}` : last || names[i],
  );
}

/** The vertex of player i out of n, and its label's anchor and position. Vertex 0 is at the top. */
export function vertex(i: number, n: number): Pick<NetPlayer, "x" | "y" | "anchor" | "lx" | "ly"> {
  const angle = -Math.PI / 2 + (2 * Math.PI * i) / n;
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  const far = VIEW.r + VIEW.gap;
  // Text sits beside a side vertex, and above or below a top or bottom one.
  const anchor = c > 0.2 ? "start" : c < -0.2 ? "end" : "middle";
  const drop = s > 0.2 ? 12 : s < -0.2 ? 0 : 4;
  return {
    x: round1(VIEW.cx + VIEW.r * c),
    y: round1(VIEW.cy + VIEW.r * s),
    anchor,
    lx: round1(VIEW.cx + far * c),
    ly: round1(VIEW.cy + far * s + drop),
  };
}

function round1(x: number): number {
  return Math.round(x * 10) / 10;
}

const round2 = (x: number) => Math.round(x * 100) / 100;

/** Where a pair's cooperation sits from the weakest (one assist, 0) to the team's largest (1), linear
 *  in the count. With no spread (every pair one assist, or no pairs) it is 0. */
export function edgeShare(total: number, largest: number): number {
  if (largest <= 1 || total <= 1) return 0;
  return Math.min(1, (Math.min(total, largest) - 1) / (largest - 1));
}

/** The line width: EDGE_MIN for one assist, EDGE_MAX for the team's largest pair, linear between. */
export function edgeWidth(total: number, largest: number): number {
  return round1(EDGE_MIN + (EDGE_MAX - EDGE_MIN) * edgeShare(total, largest));
}

/** The line's opacity: OPACITY_MIN for one assist, OPACITY_MAX for the largest pair, linear between. */
export function edgeOpacity(total: number, largest: number): number {
  return round2(OPACITY_MIN + (OPACITY_MAX - OPACITY_MIN) * edgeShare(total, largest));
}

/** The players drawn: the top `n` by assists involvement (given plus received). */
export function networkPlayers(
  club: AssistClub,
  names: Map<string, string>,
  n = NETWORK_SIZE,
): { id: string; name: string; given: number; received: number }[] {
  const given = new Map<string, number>();
  const received = new Map<string, number>();
  for (const [p, s, assists] of club.pairs) {
    if (p === s || !Number.isFinite(assists) || assists < 1) continue;
    given.set(p, (given.get(p) ?? 0) + assists);
    received.set(s, (received.get(s) ?? 0) + assists);
  }
  const ids = new Set([...given.keys(), ...received.keys()]);
  const name = (id: string) => names.get(id) ?? id;
  const weight = (id: string) => (given.get(id) ?? 0) + (received.get(id) ?? 0);
  return [...ids]
    .sort((a, b) => weight(b) - weight(a) || name(a).localeCompare(name(b)) || a.localeCompare(b))
    .slice(0, n)
    .map((id) => ({ id, name: name(id), given: given.get(id) ?? 0, received: received.get(id) ?? 0 }));
}

/** The network of one club-season: the top players on the polygon, and a line for each pair among
 *  them with at least one assist (either direction). Pairs with a player outside the top are left out. */
export function network(club: AssistClub, names: Map<string, string>, n = NETWORK_SIZE): Network {
  const chosen = networkPlayers(club, names, n);
  const index = new Map(chosen.map((p, i) => [p.id, i]));
  const text = labels(chosen.map((p) => p.name));
  const players: NetPlayer[] = chosen.map((p, i) => ({
    ...p,
    label: text[i],
    ...vertex(i, chosen.length),
  }));
  const pairs = new Map<string, { a: number; b: number; ab: number; ba: number }>();
  for (const [p, s, assists] of club.pairs) {
    if (p === s || !Number.isFinite(assists) || assists < 1) continue;
    const i = index.get(p);
    const j = index.get(s);
    if (i === undefined || j === undefined) continue;
    const a = Math.min(i, j);
    const b = Math.max(i, j);
    const key = `${a}-${b}`;
    const e = pairs.get(key) ?? { a, b, ab: 0, ba: 0 };
    if (i === a) e.ab += assists;
    else e.ba += assists;
    pairs.set(key, e);
  }
  const counted = [...pairs.values()].map((e) => ({ ...e, total: e.ab + e.ba }));
  const largest = Math.max(0, ...counted.map((e) => e.total));
  const drawn = counted.length > MAX_DRAWN_PAIRS ? counted.filter((e) => e.total > 1) : counted;
  const edges = drawn
    .map((e) => ({ ...e, width: edgeWidth(e.total, largest), opacity: edgeOpacity(e.total, largest) }))
    .sort((x, y) => x.total - y.total || x.a - y.a || x.b - y.b);
  return { players, edges, hiddenPairs: counted.length - drawn.length };
}

/** The tooltip for a line: "A to B: x assists, B to A: y assists". */
export function edgeTitle(edge: NetEdge, players: NetPlayer[]): string {
  const [a, b] = [players[edge.a].name, players[edge.b].name];
  const count = (n: number) => (n === 1 ? "1 assist" : `${n} assists`);
  return `${a} to ${b}: ${count(edge.ab)}, ${b} to ${a}: ${count(edge.ba)}`;
}
