// Players dashboard: ranking, and the HTML for the ranked table and the strip plot. Pure functions of
// the season data and the view state, run both at build time (the first paint) and in the browser
// (every filter change), so the two can never disagree. The measures and the query string live in
// measures.ts, which this module re-exports.

import { signClass } from "./delta";
import { esc } from "./format";
import { position } from "./position";
import { dataTip, linkTip, tip } from "./tip";
import { DEFAULT_HALF_WIDTH, STRIP_HEIGHT, domainOf, isTop, stripLayout, valueY, type StripDot } from "./strip";
import type { PlayerRow, SeasonPlayers } from "./stats";
import { BY_KEY, columnsOf, format, MEASURES, measureTitle, rated, type RapmData, type View } from "./measures";

export * from "./measures";

interface Line {
  row: PlayerRow;
  totals: Totals;
  values: Record<string, number | null>;
  ranked: boolean; // qualifies for the ranked measure
  pos: Position | null;
}

function totalsOf(fields: string[], values: number[]): Totals {
  const t: Totals = {};
  fields.forEach((f, i) => (t[f] = values[i]));
  return t;
}

/** Every player passing the filters, ranked on the metric (unranked last). Show top is applied by
 *  `shown`. `rapm` is the season's board, if it has one. */
export function lines(data: SeasonPlayers, view: View, rapm: RapmData | null = null): Line[] {
  const measure = BY_KEY[view.metric] ?? BY_KEY.pts;
  const board = rapm && rapm.season === view.season ? rapm : null;
  const all = data.players.map((row) => {
    const totals = totalsOf(data.fields, row.totals.season);
    const found = board?.players[row.id];
    if (board && found) {
      totals.rapm = found.total;
      totals.rapm_min = found.minutes;
      totals.rapm_floor = board.minimum;
    }
    const values: Record<string, number | null> = {};
    for (const m of MEASURES) values[m.key] = rated(m, totals, view.rate);
    return { row, totals, values, ranked: true, pos: position(row.pos) };
  });
  // The games floor keeps cameo seasons out: a quarter of the most games anyone played.
  const most = Math.max(0, ...all.map((l) => l.totals.gp));
  const floorGames = view.minMin > 0 ? Math.ceil(most / 4) : 0;
  const kept = all.filter(
    (l) =>
      l.totals.gp >= floorGames &&
      (l.totals.gp ? l.totals.sec / l.totals.gp / 60 : 0) >= view.minMin &&
      (!view.pos || l.pos === view.pos),
  );
  for (const l of kept) l.ranked = l.values[measure.key] !== null && (measure.qualifies?.(l.totals) ?? true);
  const sign = view.dir === "desc" ? -1 : 1;
  return kept.sort((a, b) => {
    if (a.ranked !== b.ranked) return a.ranked ? -1 : 1;
    const av = a.values[measure.key] ?? -Infinity;
    const bv = b.values[measure.key] ?? -Infinity;
    return av === bv ? a.row.name.localeCompare(b.row.name) : sign * (av - bv);
  });
}

/** "25 of 143 players" when Show top cuts the list, else "143 players". */
export const countText = (n: number, total: number) =>
  n < total ? `${n} of ${total} players` : `${total} player${total === 1 ? "" : "s"}`;

/** Show top: the first `top` lines of a ranked list (all of them when `top` is 0). */
export const shown = <T>(ls: T[], view: View): T[] => (view.top ? ls.slice(0, view.top) : ls);


export const teamHref = (base: string, code: string, season?: number) =>
  `${base.replace(/\/$/, "")}/teams/${code.toLowerCase()}/${season ? `?season=${season}` : ""}`;
export const playerHref = (base: string, slug: string) => `${base.replace(/\/$/, "")}/players/${slug}/`;

export interface StripPoint {
  line: Line;
  dot: StripDot;
  text: string;
}

/** The strip plot: one dot per ranked player on the measure's value axis. */
export interface Strip {
  title: string;
  points: StripPoint[];
  ticks: { y: number; text: string }[];
  avg: { y: number; text: string; n: number } | null;
}

/** `halfWidth`: how far a tie group may spread from the axis, in px (the plot's real width on the page). */
export function strip(ls: Line[], view: View, halfWidth = DEFAULT_HALF_WIDTH): Strip {
  const m = BY_KEY[view.metric] ?? BY_KEY.pts;
  const ranked = ls.filter((l) => l.ranked);
  const byId = new Map(ranked.map((l) => [l.row.id, l] as const));
  const values = ranked.map((l) => l.values[m.key] as number);
  const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const [lo, hi] = domainOf(values, m.kind !== "pct" && !m.signed);
  const { dots, ticks } = stripLayout(
    ranked.map((l, i) => ({ key: l.row.id, value: l.values[m.key] as number, top: isTop(i, view.top) })),
    lo,
    hi,
    STRIP_HEIGHT,
    halfWidth,
  );
  return {
    title: measureTitle(view),
    points: dots.map((dot) => {
      const line = byId.get(dot.key)!;
      return { line, dot, text: format(m, line.values[m.key]) };
    }),
    ticks: ticks.map((t) => ({ y: t.y, text: format({ ...m, digits: Number.isInteger(t.value) ? 0 : 1 }, t.value) })),
    avg: mean === null ? null : { y: valueY(mean, lo, hi), text: format(m, mean), n: values.length },
  };
}

/** One strip dot as HTML: a link to the player, with a tip. No name is printed on the dot. */
export function dotHtml(p: StripPoint, s: Strip, base: string): string {
  const { row } = p.line;
  const body = tip`<b>${row.name}</b> ${row.teams.join(", ")}<br>${s.title}: ${p.text}`;
  const cls = p.dot.top ? "dot top" : "dot";
  return `<a class="${cls}" href="${playerHref(base, row.slug)}" data-id="${row.id}" style="--dx:${p.dot.dx};--y:${p.dot.y}"${linkTip(body)}></a>`;
}

export const dotsHtml = (s: Strip, base: string): string => s.points.map((p) => dotHtml(p, s, base)).join("");
export const ticksHtml = (s: Strip): string =>
  s.ticks.map((t) => `<span style="--y:${t.y.toFixed(2)}">${t.text}</span>`).join("");
export const gridHtml = (s: Strip): string => s.ticks.map((t) => `<i style="--y:${t.y.toFixed(2)}"></i>`).join("");

export function headHtml(view: View, rapm: boolean): string {
  const cols = columnsOf(view, rapm).map((key) => {
    const m = BY_KEY[key];
    const on = key === view.metric;
    const sort = on ? (view.dir === "desc" ? "descending" : "ascending") : "none";
    return `<th scope="col" class="num${on ? " on" : ""}" aria-sort="${sort}"><button type="button" data-sort="${key}"${dataTip(tip`<b>${m.name}</b><br>${m.about}`)}>${m.head}</button></th>`;
  });
  return `<tr><th scope="col" class="c-rk"><span class="sr-only">Rank</span></th><th scope="col" class="c-nm">Player</th>${cols.join("")}</tr>`;
}

/** The team code(s) under a name: a lone club is the link itself (one element per row, not two). */
const teamCell = (teams: string[], base: string, season: number) => {
  const links = teams.map((t) => `<a${teams.length === 1 ? ' class="tm"' : ""} href="${teamHref(base, t, season)}">${esc(t)}</a>`);
  return teams.length === 1 ? links[0] : `<span class="tm">${links.join(" · ")}</span>`;
};

export function bodyHtml(ls: Line[], view: View, base: string, rapm: boolean): string {
  const keys = columnsOf(view, rapm);
  if (!ls.length) {
    return `<tr class="empty"><td colspan="${keys.length + 2}">No players match. Lower the minutes or pick another position.</td></tr>`;
  }
  let rank = 0;
  return ls
    .map((l) => {
      if (l.ranked) rank += 1;
      const cells = keys
        .map((key) => {
          const m = BY_KEY[key];
          const v = l.values[key];
          const short = m.qualifies && !m.qualifies(l.totals);
          const cls = ["num", key === view.metric ? "on" : "", short ? "short" : ""].filter(Boolean).join(" ");
          // Sign Colour Rule: the signed measures (+/- and net rating) wear green or red; the sign is printed.
          const sc = m.signed ? signClass(v, m.digits) : "";
          return `<td class="${cls}">${sc ? `<span class="${sc}">${format(m, v)}</span>` : format(m, v)}</td>`;
        })
        .join("");
      return `<tr data-id="${l.row.id}"><td class="c-rk">${l.ranked ? rank : ""}</td><th scope="row" class="c-nm"><a href="${playerHref(base, l.row.slug)}">${esc(l.row.name)}</a>${teamCell(l.row.teams, base, view.season)}</th>${cells}</tr>`;
    })
    .join("");
}

