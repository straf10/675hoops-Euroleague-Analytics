// Players dashboard: measures, filtering, ranking, and the HTML for the ranked chart and table.
// Pure functions of the season data and the view state, run both at build time (the first
// paint) and in the browser (every filter change), so the two can never disagree. Values are per
// game; `rated` also serves the Compare page's per-36 and per-100 columns.

import { signClass } from "./delta";
import { esc } from "./format";
import { position, type Position } from "./position";
import { dataTip, tip } from "./tip";
import type { PlayerRow, SeasonPlayers } from "./stats";

export type Rate = "game" | "36" | "100";
export type ColumnSet = "box" | "shooting";

export interface View {
  season: number;
  metric: string; // the measure the players are ranked on
  dir: "desc" | "asc";
  minMin: number; // minutes per game, at least
  top: number; // players shown; 0 = all
  pos: Position | ""; // "" = every position
  set: ColumnSet; // which columns the table shows
}

type Totals = Record<string, number>;

export interface Measure {
  key: string;
  head: string; // column head
  name: string; // chart title and tooltip, e.g. "Points"
  about: string;
  kind: "count" | "pct" | "fixed"; // counts follow the rate; percentages and fixed values do not
  digits: number;
  value: (t: Totals) => number | null;
  /** Enough attempts to rank on this percentage (per game). */
  qualifies?: (t: Totals) => boolean;
  signed?: boolean;
}

const fga = (t: Totals) => t.fg2a + t.fg3a;
const fgm = (t: Totals) => t.fg2m + t.fg3m;
const ratio = (num: number, den: number) => (den > 0 ? (100 * num) / den : null);

const count = (key: string, head: string, name: string, about: string, extra: Partial<Measure> = {}): Measure => ({
  key,
  head,
  name,
  about,
  kind: "count",
  digits: 1,
  value: (t) => t[key],
  ...extra,
});

export const MEASURES: Measure[] = [
  { key: "gp", head: "GP", name: "Games played", about: "Games played", kind: "fixed", digits: 0, value: (t) => t.gp },
  {
    key: "min",
    head: "MIN",
    name: "Minutes",
    about: "Minutes per game, whatever the rate",
    kind: "fixed",
    digits: 1,
    value: (t) => (t.gp ? t.sec / t.gp / 60 : null),
  },
  count("pts", "PTS", "Points", "Points"),
  count("reb", "REB", "Rebounds", "Rebounds, offensive and defensive", { value: (t) => t.oreb + t.dreb }),
  count("ast", "AST", "Assists", "Assists"),
  count("stl", "STL", "Steals", "Steals"),
  count("blk", "BLK", "Blocks", "Shots blocked"),
  count("tov", "TOV", "Turnovers", "Turnovers"),
  count("pir", "PIR", "PIR", "Performance Index Rating, the EuroLeague's official efficiency score"),
  count("pm", "+/-", "Plus-minus", "Points scored minus points allowed while on court", { signed: true }),
  count("fga", "FGA", "Field-goal attempts", "Field-goal attempts, twos and threes", { value: fga }),
  {
    key: "fg_pct",
    head: "FG%",
    name: "Field-goal %",
    about: "Field goals made per attempt",
    kind: "pct",
    digits: 1,
    value: (t) => ratio(fgm(t), fga(t)),
    qualifies: (t) => fga(t) >= 3 * t.gp,
  },
  {
    key: "fg2_pct",
    head: "2P%",
    name: "Two-point %",
    about: "Two-pointers made per attempt",
    kind: "pct",
    digits: 1,
    value: (t) => ratio(t.fg2m, t.fg2a),
    qualifies: (t) => t.fg2a >= 2 * t.gp,
  },
  count("fg3a", "3PA", "Three-point attempts", "Three-point attempts"),
  {
    key: "fg3_pct",
    head: "3P%",
    name: "Three-point %",
    about: "Three-pointers made per attempt",
    kind: "pct",
    digits: 1,
    value: (t) => ratio(t.fg3m, t.fg3a),
    qualifies: (t) => t.fg3a >= t.gp,
  },
  count("fta", "FTA", "Free-throw attempts", "Free-throw attempts"),
  {
    key: "ft_pct",
    head: "FT%",
    name: "Free-throw %",
    about: "Free throws made per attempt",
    kind: "pct",
    digits: 1,
    value: (t) => ratio(t.ftm, t.fta),
    qualifies: (t) => t.fta >= t.gp,
  },
  {
    key: "efg",
    head: "eFG%",
    name: "Effective FG%",
    about: "Field-goal % with a made three worth one and a half makes",
    kind: "pct",
    digits: 1,
    value: (t) => ratio(fgm(t) + 0.5 * t.fg3m, fga(t)),
    qualifies: (t) => fga(t) >= 3 * t.gp,
  },
  {
    key: "ts",
    head: "TS%",
    name: "True shooting %",
    about: "Points per shooting chance, free throws included: PTS / (2 × (FGA + 0.44 × FTA))",
    kind: "pct",
    digits: 1,
    value: (t) => ratio(t.pts, 2 * (fga(t) + 0.44 * t.fta)),
    qualifies: (t) => fga(t) >= 3 * t.gp,
  },
  {
    key: "usg",
    head: "USG%",
    name: "Usage %",
    about: "Share of his team's shots, free throws and turnovers used while he was on court",
    kind: "pct",
    digits: 1,
    value: (t) => {
      const team = t.tm_fga + 0.44 * t.tm_fta + t.tm_tov;
      return t.sec > 0 && team > 0 ? (100 * (fga(t) + 0.44 * t.fta + t.tov) * t.game_sec) / (t.sec * team) : null;
    },
  },
];

export const BY_KEY = Object.fromEntries(MEASURES.map((m) => [m.key, m]));

export const SETS: Record<ColumnSet, string[]> = {
  box: ["gp", "min", "pts", "reb", "ast", "stl", "blk", "tov", "pir", "pm"],
  shooting: ["fga", "fg_pct", "fg2_pct", "fg3a", "fg3_pct", "fta", "ft_pct", "efg", "ts", "usg"],
};

/** On a phone each set sheds into two groups (GROUPS.players in lib/cols.ts, same order). The
 *  Players page's CSS hides the other columns by their place in SETS: keep the three in step. */
export const PHONE_GROUPS: { set: ColumnSet; keys: string[] }[] = [
  { set: "box", keys: ["gp", "min", "pts", "pir", "pm"] },
  { set: "box", keys: ["reb", "ast", "stl", "blk", "tov"] },
  { set: "shooting", keys: ["fga", "fg_pct", "fg2_pct", "fg3a", "fg3_pct"] },
  { set: "shooting", keys: ["fta", "ft_pct", "efg", "ts", "usg"] },
];

/** Minutes-per-game presets (the only minutes choices): from 2025-26, 275 players pass the games
 *  floor; 251 average 10+, 190 15+, 107 20+ and 32 25+. */
export const MIN_PRESETS = [0, 10, 15, 20, 25];
/** The preset at or below n, so a free value from an old link lands on a preset (12 -> 10). */
export const presetAtOrBelow = (n: number): number => {
  let best = MIN_PRESETS[0];
  for (const p of MIN_PRESETS) if (p <= n && p > best) best = p;
  return best;
};
/** "Show top" choices; 0 is All. */
export const TOPS = [5, 10, 25, 50, 100, 0];
export const topLabel = (n: number) => (n ? String(n) : "All");
export const POSITION_CHOICES: { key: Position | ""; label: string }[] = [
  { key: "", label: "All" },
  ...(["Guard", "Wing", "Big"] as const).map((p) => ({ key: p, label: p })),
];

export const DEFAULT_VIEW: Omit<View, "season"> = {
  metric: "pts",
  dir: "desc",
  minMin: 10,
  top: 25,
  pos: "",
  set: "box",
};

/** The column set a measure is shown in. */
export const setOf = (key: string): ColumnSet => (SETS.box.includes(key) ? "box" : "shooting");

/** The Metric select's groups, in column order. */
export const METRIC_GROUPS: { label: string; keys: string[] }[] = [
  { label: "Box score", keys: SETS.box },
  { label: "Shooting", keys: SETS.shooting },
];

export interface Line {
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

export function rated(m: Measure, t: Totals, rate: Rate): number | null {
  const raw = m.value(t);
  if (raw === null || m.kind !== "count") return raw;
  if (rate === "game") return t.gp ? raw / t.gp : null;
  if (rate === "36") return t.sec ? (raw * 2160) / t.sec : null;
  return t.poss ? (raw * 100) / t.poss : null;
}

/** Every player passing the filters, ranked on the metric (unranked last). Show top is applied by
 *  `shown`, so the chart's average still covers everyone ranked. */
export function lines(data: SeasonPlayers, view: View): Line[] {
  const measure = BY_KEY[view.metric] ?? BY_KEY.pts;
  const all = data.players.map((row) => {
    const totals = totalsOf(data.fields, row.totals.season);
    const values: Record<string, number | null> = {};
    for (const m of MEASURES) values[m.key] = rated(m, totals, "game");
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

export function format(m: Measure, v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "–";
  const text = Math.abs(v).toFixed(m.digits);
  if (m.signed && v > 0) return `+${text}`;
  if (v < 0 && Number(text) !== 0) return `−${text}`;
  return text;
}

export const teamHref = (base: string, code: string, season?: number) =>
  `${base.replace(/\/$/, "")}/teams/${code.toLowerCase()}/${season ? `?season=${season}` : ""}`;
export const playerHref = (base: string, slug: string) => `${base.replace(/\/$/, "")}/players/${slug}/`;

export function measureTitle(view: View): string {
  const m = BY_KEY[view.metric] ?? BY_KEY.pts;
  return m.kind === "count" ? `${m.name} per game` : m.key === "min" ? "Minutes per game" : m.name;
}

function niceTicks(lo: number, hi: number, count = 6): number[] {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((s) => s * mag).find((s) => span / s <= count) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

export interface Chart {
  title: string;
  rows: { line: Line; x: number; text: string; sc: string }[];
  ticks: { x: number; text: string }[];
  avg: { x: number; text: string; n: number } | null;
}

/** The ranked dot chart: the top ranked rows (Show top) on one scale, with the average of everyone ranked. */
export function chart(ls: Line[], view: View): Chart {
  const m = BY_KEY[view.metric] ?? BY_KEY.pts;
  const ranked = ls.filter((l) => l.ranked);
  const top = shown(ranked, view);
  const values = ranked.map((l) => l.values[m.key] as number);
  const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const inView = [...top.map((l) => l.values[m.key] as number), ...(mean === null ? [] : [mean])];
  let lo = Math.min(...inView);
  let hi = Math.max(...inView);
  if (!inView.length) [lo, hi] = [0, 1];
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
  lo -= pad;
  hi += pad;
  if (m.kind !== "pct" && !m.signed && lo < 0) lo = 0;
  const x = (v: number) => (100 * (v - lo)) / (hi - lo);
  const end = view.dir === "desc" ? "Highest" : "Lowest";
  return {
    title: `${end} ${top.length}: ${measureTitle(view)}`,
    rows: top.map((line) => ({
      line,
      x: x(line.values[m.key] as number),
      text: format(m, line.values[m.key]),
      sc: m.signed ? signClass(line.values[m.key], m.digits) : "",
    })),
    ticks: niceTicks(lo, hi).map((v) => ({ x: x(v), text: format({ ...m, digits: Number.isInteger(v) ? 0 : 1 }, v) })),
    avg: mean === null ? null : { x: x(mean), text: format(m, mean), n: values.length },
  };
}

/** The tooltip of one chart row: the player, his clubs and the value charted. */
export const slotTip = (row: PlayerRow, c: Chart, text: string) =>
  tip`<b>${row.name}</b> ${row.teams.join(", ")}<br>${c.title.split(": ")[1]}: ${text}`;

/** Chart rows as HTML, one slot per row. While the row count stays the same a change retargets the
 *  slots (dots slide); a new Show top rebuilds them. */
export function chartHtml(c: Chart, base: string): string {
  return c.rows
    .map((s, i) => {
      const { row } = s.line;
      const body = slotTip(row, c, s.text);
      return `<li class="slot" style="--x:${s.x.toFixed(2)}"><span class="rk">${i + 1}</span><a class="nm" href="${playerHref(base, row.slug)}">${esc(row.name)}</a><span class="track"${dataTip(body)} tabindex="-1"><span class="pos"></span></span><span class="val${s.sc ? ` ${s.sc}` : ""}">${s.text}</span></li>`;
    })
    .join("");
}

export function ticksHtml(c: Chart): string {
  return c.ticks.map((t) => `<span style="--x:${t.x.toFixed(2)}">${t.text}</span>`).join("");
}

export function gridHtml(c: Chart): string {
  return c.ticks.map((t) => `<i style="--x:${t.x.toFixed(2)}"></i>`).join("");
}

export function headHtml(view: View): string {
  const cols = SETS[view.set].map((key) => {
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

export function bodyHtml(ls: Line[], view: View, base: string): string {
  if (!ls.length) {
    return `<tr class="empty"><td colspan="${SETS[view.set].length + 2}">No players match. Lower the minutes or pick another position.</td></tr>`;
  }
  let rank = 0;
  return ls
    .map((l) => {
      if (l.ranked) rank += 1;
      const cells = SETS[view.set]
        .map((key) => {
          const m = BY_KEY[key];
          const v = l.values[key];
          const short = m.qualifies && !m.qualifies(l.totals);
          const cls = ["num", key === view.metric ? "on" : "", short ? "short" : ""].filter(Boolean).join(" ");
          // Sign Colour Rule: the +/- figure (signed measures) wears green or red; the sign is printed.
          const sc = m.signed ? signClass(v, m.digits) : "";
          return `<td class="${cls}">${sc ? `<span class="${sc}">${format(m, v)}</span>` : format(m, v)}</td>`;
        })
        .join("");
      return `<tr><td class="c-rk">${l.ranked ? rank : ""}</td><th scope="row" class="c-nm"><a href="${playerHref(base, l.row.slug)}">${esc(l.row.name)}</a>${teamCell(l.row.teams, base, view.season)}</th>${cells}</tr>`;
    })
    .join("");
}

/** View <-> query string: only values that differ from the defaults are written. Parameters from
 *  older versions of the page (sort, window, rate, team, q, minMin) are ignored. */
export function toQuery(view: View, defaultSeason: number): string {
  const p = new URLSearchParams();
  if (view.season !== defaultSeason) p.set("season", String(view.season));
  if (view.metric !== DEFAULT_VIEW.metric) p.set("metric", view.metric);
  if (view.dir !== DEFAULT_VIEW.dir) p.set("dir", view.dir);
  if (view.minMin !== DEFAULT_VIEW.minMin) p.set("min", String(view.minMin));
  if (view.top !== DEFAULT_VIEW.top) p.set("top", String(view.top));
  if (view.pos) p.set("pos", view.pos);
  if (view.set !== setOf(view.metric)) p.set("set", view.set); // a set that hides the metric
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function fromQuery(search: string, seasons: number[], defaultSeason: number): View {
  const p = new URLSearchParams(search);
  const pick = <T extends string>(key: string, allowed: readonly T[], fallback: T): T => {
    const v = p.get(key) as T | null;
    return v && allowed.includes(v) ? v : fallback;
  };
  const season = Number(p.get("season"));
  const min = p.has("min") && p.get("min") !== "" ? Number(p.get("min")) : NaN;
  // Any non-negative value from an old link snaps to a preset; junk keeps the default.
  const minMin = Number.isFinite(min) && min >= 0 ? presetAtOrBelow(min) : DEFAULT_VIEW.minMin;
  const top = p.has("top") ? Number(p.get("top")) : NaN;
  const metric = pick("metric", MEASURES.map((m) => m.key), DEFAULT_VIEW.metric);
  return {
    season: seasons.includes(season) ? season : defaultSeason,
    metric,
    dir: pick("dir", ["desc", "asc"] as const, DEFAULT_VIEW.dir),
    minMin,
    top: TOPS.includes(top) ? top : DEFAULT_VIEW.top,
    pos: pick("pos", ["Guard", "Wing", "Big"] as const, DEFAULT_VIEW.pos as Position | "") as Position | "",
    set: pick("set", ["box", "shooting"] as const, setOf(metric)),
  };
}
