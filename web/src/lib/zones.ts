// Shot zones for the team page's Shot attempts chart. A zone is worked out from where the shot was
// taken (court centimetres from the basket: x sideways, y in front of it), so no zone is stored.
// Also here: one club's attempts for a season, split into the shots it took and the shots taken
// against it, and the table of zones. Pure, so the build, the page and the tests share it.
// (Imports stay out of this file: its test runs under plain node, which needs no extensions.)

/** Inside this distance from the basket it is "At the rim" (metres). */
export const RIM_MAX_M = 1.5;
/** The paint: this far either side of the centre, and up to the free-throw line (5.80 m). */
export const PAINT_HALF_WIDTH_M = 2.45;
export const PAINT_DEPTH_M = 5.8;
/** The three-point line: 6.75 m in the arc, 6.60 m from the centre line in the corners. */
export const THREE_ARC_M = 6.75;
export const THREE_CORNER_X_M = 6.6;
/** Where the corner lines meet the arc: sqrt(6.75² - 6.6²), about 1.42 m from the basket. */
export const THREE_CORNER_DEPTH_M = Math.sqrt(THREE_ARC_M ** 2 - THREE_CORNER_X_M ** 2);
/** From this distance a three is "Deep 3". */
export const DEEP_MIN_M = 8.0;

export type Zone = "rim" | "paint" | "mid" | "corner3" | "above3" | "deep3";
export type ClubSide = "taken" | "allowed";

/** The six zones in the order the chips and the table show them. */
export const ZONES: [zone: Zone, label: string][] = [
  ["rim", "At the rim"],
  ["paint", "Paint"],
  ["mid", "Mid-range"],
  ["corner3", "Corner 3"],
  ["above3", "Above-break 3"],
  ["deep3", "Deep 3"],
];

/** The zone of a shot at (x, y) court centimetres. */
export function zoneOf(x: number, y: number): Zone {
  const ax = Math.abs(x) / 100;
  const fy = y / 100;
  const dist = Math.hypot(ax, fy);
  if (dist <= RIM_MAX_M) return "rim";
  if (ax <= PAINT_HALF_WIDTH_M && fy >= 0 && fy <= PAINT_DEPTH_M) return "paint";
  if (ax >= THREE_CORNER_X_M && fy <= THREE_CORNER_DEPTH_M) return "corner3";
  if (dist < THREE_ARC_M) return "mid";
  if (dist >= DEEP_MIN_M) return "deep3";
  return "above3";
}

/** One club's shots for one season: what the team page's chart reads (data/shots/club/{code}/{season}.json). */
export interface ClubShots {
  season: number;
  code: string;
  /** Flat [x, y, made, three] per attempt, in court centimetres (the shape markChart reads). */
  taken: number[];
  allowed: number[];
  /** Every attempt in the league that season, by zone. */
  league: Totals;
}

/** [attempts, made, points] per zone. */
export type Totals = Record<Zone, [att: number, made: number, pts: number]>;

/** The attempts.json fields this reads (the stats loader's RawAttempts has them all). */
export interface RawShots {
  teams: string[];
  x: number[];
  y: number[];
  flags: number[];
  team: number[];
  opp: number[];
  bits: { made: number; three: number };
}

export const emptyTotals = (): Totals => Object.fromEntries(ZONES.map(([z]) => [z, [0, 0, 0]])) as Totals;

/** Adds the attempt at stride-4 index `i` of `dots` to a zone's totals. */
function add(t: Totals, dots: number[], i: number): void {
  const row = t[zoneOf(dots[i], dots[i + 1])];
  row[0]++;
  row[1] += dots[i + 2];
  row[2] += dots[i + 2] ? (dots[i + 3] ? 3 : 2) : 0;
}

/** The zone totals of a flat dot list. */
export function zoneTotals(dots: number[]): Totals {
  const t = emptyTotals();
  for (let i = 0; i < dots.length; i += 4) add(t, dots, i);
  return t;
}

/** The club's taken and allowed shots, and the league's zone totals, from one season's attempts. */
export function clubShotsOf(raw: RawShots, code: string, season: number): ClubShots {
  const ci = raw.teams.indexOf(code);
  const taken: number[] = [];
  const allowed: number[] = [];
  const league = emptyTotals();
  for (let i = 0; i < raw.x.length; i++) {
    const made = (raw.flags[i] >> raw.bits.made) & 1;
    const three = (raw.flags[i] >> raw.bits.three) & 1;
    const dot = [raw.x[i], raw.y[i], made, three];
    add(league, dot, 0);
    if (raw.team[i] === ci) taken.push(...dot);
    if (raw.opp[i] === ci) allowed.push(...dot);
  }
  return { season, code, taken, allowed, league };
}

/** The dots that pass the zone chips: every dot when none is picked ("All"). */
export function sideDots(file: ClubShots, side: ClubSide, picked: ReadonlySet<Zone>): number[] {
  const dots = file[side];
  if (picked.size === 0) return dots;
  const out: number[] = [];
  for (let i = 0; i < dots.length; i += 4)
    if (picked.has(zoneOf(dots[i], dots[i + 1]))) out.push(dots[i], dots[i + 1], dots[i + 2], dots[i + 3]);
  return out;
}

const pct = (m: number, n: number) => (n ? ((100 * m) / n).toFixed(1) : "–");
const signed = (x: number) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(1)}`;

/** Table rows: one per zone, with FGA, FG%, share of the side's attempts, points per shot and FG%
 * against the league's in the same zone (points). Zones not picked are dimmed when some are picked. */
export function zoneRowsHtml(file: ClubShots, side: ClubSide, picked: ReadonlySet<Zone>): string {
  const t = zoneTotals(file[side]);
  const all = ZONES.reduce((n, [z]) => n + t[z][0], 0);
  return ZONES.map(([zone, label]) => {
    const [att, made, pts] = t[zone];
    const [lAtt, lMade] = file.league[zone];
    const off = picked.size > 0 && !picked.has(zone);
    const diff = att && lAtt ? (100 * made) / att - (100 * lMade) / lAtt : null;
    const cls = diff === null || Math.abs(diff) < 0.05 ? "" : diff > 0 ? "sign-pos" : "sign-neg";
    return (
      `<tr data-zone="${zone}"${off ? ' class="off"' : ""}>` +
      `<th scope="row">${label}</th>` +
      `<td class="num">${att}</td>` +
      `<td class="num">${pct(made, att)}</td>` +
      `<td class="num">${all ? `${((100 * att) / all).toFixed(1)}%` : "–"}</td>` +
      `<td class="num">${att ? (pts / att).toFixed(2) : "–"}</td>` +
      `<td class="num ${cls}">${diff === null ? "–" : signed(diff)}</td>` +
      `</tr>`
    );
  }).join("");
}

/** The dots in the picked zones; every dot when none is picked. The player page's chips use it. */
export function zoneDots(dots: number[], picked: ReadonlySet<Zone>): number[] {
  if (picked.size === 0) return dots;
  const out: number[] = [];
  for (let i = 0; i < dots.length; i += 4)
    if (picked.has(zoneOf(dots[i], dots[i + 1]))) out.push(dots[i], dots[i + 1], dots[i + 2], dots[i + 3]);
  return out;
}

/** The attempts the 2PT / 3PT switch keeps: all, two-pointers ("2") or threes ("3"). Flat dots. */
export function pointsFilter(dots: number[], kind: "all" | "2" | "3"): number[] {
  if (kind === "all") return dots;
  const want = kind === "3" ? 1 : 0;
  const out: number[] = [];
  for (let i = 0; i < dots.length; i += 4) if (dots[i + 3] === want) out.push(dots[i], dots[i + 1], dots[i + 2], dots[i + 3]);
  return out;
}

/** For a heatmap square whose centre is (x, y) in court metres (x sideways, y from the basket): lit when
 * no zone is picked, or when the square's centre falls in a picked zone. Other squares are dimmed. */
export function zoneLit(picked: ReadonlySet<Zone>): (x: number, y: number) => boolean {
  if (picked.size === 0) return () => true;
  return (x, y) => picked.has(zoneOf(x * 100, y * 100));
}

/** The picked zones' attempts and makes, against all the attempts passed in (flat dots, already filtered
 * by the 2PT / 3PT switch). */
export function zoneSummary(dots: number[], picked: ReadonlySet<Zone>): { total: number; att: number; made: number } {
  let total = 0;
  let att = 0;
  let made = 0;
  for (let i = 0; i < dots.length; i += 4) {
    total++;
    if (picked.size === 0 || picked.has(zoneOf(dots[i], dots[i + 1]))) {
      att++;
      made += dots[i + 2];
    }
  }
  return { total, att, made };
}

/** "At the rim and Paint: 12.3% of his attempts, 4 of 9 made (44.4%)" for the picked zones. Empty when none is
 * picked. Labels come from ZONES, in the chips' order. */
export function zoneLineText(dots: number[], picked: ReadonlySet<Zone>, scope = "his attempts"): string {
  if (picked.size === 0) return "";
  const { total, att, made } = zoneSummary(dots, picked);
  const names = ZONES.filter(([z]) => picked.has(z)).map(([, label]) => label);
  const list = names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}` : names[0];
  if (!att) return `${list}: no attempts from here.`;
  const share = ((100 * att) / total).toFixed(1);
  const fg = ((100 * made) / att).toFixed(1);
  return `${list}: ${share}% of ${scope}, ${made} of ${att} made (${fg}%).`;
}

/** The distance bands (the keys of lib/player.ts's BAND_LABELS) that one zone covers exactly. Rim (under 1.5 m)
 * and Deep three (8 m and out) do. The other bands cut across zones (the 3 m to 5 m band holds both the paint
 * and the mid-range), so they are never dimmed. */
const BAND_ZONE: Record<string, Zone> = { rim: "rim", deep3: "deep3" };

/** Whether a distance band's table row is dimmed: its one zone is not among the picked ones. */
export function bandDimmed(band: string, picked: ReadonlySet<Zone>): boolean {
  const zone = BAND_ZONE[band];
  return picked.size > 0 && zone !== undefined && !picked.has(zone);
}
