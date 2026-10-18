// Team page renderers: ratings and four factors from team and opponent totals, the Four Factors
// rows (club value, rank, rail against the league, delta), both shot charts, the bands and the roster.
// Pure (types only from ./stats), so the build and the in-page season switch share them.

import type { HexCell } from "./court";
import { freqHeat, qualityHeat, type Lit } from "./heat";
import { betterOf } from "./better";
import { deltaHtml, signClass } from "./delta";
import { esc, signed } from "./format";
import { dataTip, tip } from "./tip";
import { SEASON_COLS, bandRows, totalsOf, type Totals } from "./player";
import type { ClubLine, TeamSeason } from "./stats";
import type { IndexRow, Rates } from "./ranking";

/** Ratings and four factors of one side, from its totals and its opponents'. */
export function factors(fields: string[], own: number[], against: number[]) {
  const t = totalsOf(fields, own);
  const o = totalsOf(fields, against);
  const fga = (x: Totals) => x.fg2a + x.fg3a;
  const efg = (x: Totals) => (100 * (x.fg2m + x.fg3m + 0.5 * x.fg3m)) / fga(x);
  const tov = (x: Totals) => (100 * x.tov) / (fga(x) + 0.44 * x.fta + x.tov);
  const ortg = (100 * t.pts) / t.poss;
  const drtg = (100 * o.pts) / o.poss;
  return {
    pace: ((t.poss + o.poss) / 2 / t.game_sec) * 2400,
    ortg,
    drtg,
    net: ortg - drtg,
    efg: efg(t),
    tov: tov(t),
    oreb: (100 * t.oreb) / (t.oreb + o.dreb),
    ftr: (100 * t.ftm) / fga(t),
    oefg: efg(o),
    otov: tov(o),
    dreb: (100 * t.dreb) / (t.dreb + o.oreb),
    oftr: (100 * o.ftm) / fga(o),
  };
}
type Factors = ReturnType<typeof factors>;
type Key = keyof Factors;

/** One measure of the Four Factors layout. Its direction comes from `betterOf` (./better). */
interface Metric {
  key: Key;
  name: string;
  about: string;
}

export const OFFENSE: Metric[] = [
  { key: "ortg", name: "Offensive rating", about: "Points scored per 100 possessions" },
  { key: "efg", name: "Effective FG%", about: "(FGM + 0.5 × 3PM) / FGA" },
  { key: "tov", name: "Turnover rate", about: "Turnovers per 100 plays: TOV / (FGA + 0.44 × FTA + TOV)" },
  { key: "oreb", name: "Offensive rebound %", about: "Share of its own misses the club rebounded" },
  { key: "ftr", name: "Free-throw rate", about: "Free throws made per 100 field-goal attempts" },
];
export const DEFENSE: Metric[] = [
  { key: "drtg", name: "Defensive rating", about: "Points allowed per 100 opponent possessions" },
  { key: "oefg", name: "Opponent eFG%", about: "Opponents' effective FG%" },
  { key: "otov", name: "Turnovers forced", about: "Opponent turnovers per 100 opponent plays" },
  { key: "dreb", name: "Defensive rebound %", about: "Share of opponents' misses the club rebounded" },
  { key: "oftr", name: "Opponent free-throw rate", about: "Opponent free throws made per 100 of their field-goal attempts" },
];

export const ordinal = (n: number) => {
  const tail = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${tail}`;
};
export { signed };

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const mid = s.length >> 1;
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
};

export interface FactorRow {
  key: Key;
  name: string;
  about: string;
  value: string;
  rank: string;
  delta: string; // deltaHtml of the club minus the league average
  /** rail positions, 0-100, right = better on every row */
  me: number;
  avg: number;
  med: number;
  meTip: string;
  avgTip: string;
  medTip: string;
}

/** Where the club sits among every club that season, one row per measure. */
export function factorRows(t: TeamSeason, metrics: Metric[]): FactorRow[] {
  const all = t.clubs.map((c) => factors(t.fields, c.totals, c.opp));
  const league = factors(t.fields, t.league, t.league);
  const me = factors(t.fields, t.totals, t.opp);
  return metrics.map(({ key, name, about }) => {
    const better = betterOf(key);
    const values = all.map((f) => f[key]);
    const mid = median(values);
    const lo = Math.min(...values, league[key]);
    const hi = Math.max(...values, league[key]);
    const pad = (hi - lo) * 0.06 || 1;
    const along = (v: number) => (100 * (v - lo + pad)) / (hi - lo + 2 * pad);
    const at = (v: number) => (better === "higher" ? along(v) : 100 - along(v));
    const ahead = values.filter((v) => (better === "higher" ? v > me[key] : v < me[key])).length;
    const rank = `${ordinal(ahead + 1)} of ${values.length}`;
    const text = (v: number) => v.toFixed(1);
    return {
      key,
      name,
      about,
      value: text(me[key]),
      rank,
      delta: deltaHtml(me[key] - league[key], { better }),
      me: at(me[key]),
      avg: at(league[key]),
      med: at(mid),
      meTip: tip`<b>${t.code}</b> ${t.name}<br>${name}: ${text(me[key])}, ${rank}`,
      avgTip: tip`League average: ${text(league[key])}`,
      medTip: tip`League median: ${text(mid)}`,
    };
  });
}

/** The orange bar runs from the league average to the club. */
const barStyle = (r: FactorRow) =>
  `left:${Math.min(r.me, r.avg).toFixed(2)}%;width:${Math.abs(r.me - r.avg).toFixed(2)}%`;

export const factorRowHtml = (r: FactorRow) =>
  `<div class="ff-row" data-key="${r.key}"><span class="ff-name"><span${dataTip(tip`<b>${r.name}</b><br>${r.about}`)} tabindex="0">${esc(r.name)}</span></span>` +
  `<span class="ff-val">${r.value}</span><span class="ff-rank">${r.rank}</span>` +
  `<span class="ff-rail"><span class="ff-bar" style="${barStyle(r)}"></span>` +
  `<span class="ff-med" style="left:${r.med.toFixed(2)}%"${dataTip(r.medTip)} tabindex="0"></span>` +
  `<span class="ff-avg" style="left:${r.avg.toFixed(2)}%"${dataTip(r.avgTip)} tabindex="0"></span>` +
  `<span class="ff-me" style="left:${r.me.toFixed(2)}%"${dataTip(r.meTip)} tabindex="0"></span></span>` +
  `<span class="ff-delta">${r.delta}</span></div>`;

/** Patch a rendered row in place so its marks slide to the new season's places. */
export function patchFactorRow(row: HTMLElement, r: FactorRow) {
  row.querySelector(".ff-val")!.textContent = r.value;
  row.querySelector(".ff-rank")!.textContent = r.rank;
  row.querySelector(".ff-delta")!.innerHTML = r.delta;
  row.querySelector<HTMLElement>(".ff-bar")!.setAttribute("style", barStyle(r));
  for (const [cls, at, text] of [
    [".ff-med", r.med, r.medTip],
    [".ff-avg", r.avg, r.avgTip],
    [".ff-me", r.me, r.meTip],
  ] as const) {
    const mark = row.querySelector<HTMLElement>(cls)!;
    mark.style.left = `${at.toFixed(2)}%`;
    mark.dataset.tip = text;
  }
}

// ---- Head ----------------------------------------------------------------------------------

/** The header's cells for one club-season. Values may carry Delta markup, so each is HTML. */
export function headCells(t: TeamSeason) {
  const f = factors(t.fields, t.totals, t.opp);
  const pace = t.clubs
    .map((c) => factors(t.fields, c.totals, c.opp).pace)
    .filter((p) => p > f.pace).length;
  const place = ordinal(t.standing);
  return {
    record: `${t.w}–${t.l} <span class="muted">${esc(t.label)}</span>`,
    // Net is a signed figure against zero (the league average is 0), so it takes the Sign Colour Rule, not a Delta arrow.
    net: `<span class="${signClass(f.net)}">${signed(f.net)}</span>`,
    netSub: `${f.ortg.toFixed(1)} off · ${f.drtg.toFixed(1)} def`,
    pace: f.pace.toFixed(1),
    paceSub: `per 40 min · ${ordinal(pace + 1)} fastest`,
    seasons: String(t.elSeasons),
    seasonsSub: "since 2007-08",
    rank: `${place} <span class="muted">in the league</span>`,
    playoff: t.playoff ?? "Season in progress",
    playoffSub: t.playoff ? "" : `${place} now`,
  };
}
export type HeadCells = ReturnType<typeof headCells>;

// ---- Shots ---------------------------------------------------------------------------------

/** Both sides' heatmaps for the team page: frequency and shot quality, taken and allowed. `lit` dims the
 * squares outside the picked shot zones (lib/zones.ts); with none, every square is lit. */
export function teamCharts(t: TeamSeason, radius: number, lit?: Lit) {
  const n = (cells: HexCell[]) => cells.reduce((a, c) => a + c[2], 0);
  const head = `${t.code} ${t.label}:`;
  const taken = `${head} ${n(t.taken)} located field-goal attempts taken`;
  const allowed = `${head} ${n(t.allowed)} located opponent attempts allowed`;
  return {
    freq: {
      taken: freqHeat(t.taken, radius, `${taken}, shot frequency`, lit),
      allowed: freqHeat(t.allowed, radius, `${allowed}, shot frequency`, lit),
    },
    quality: {
      taken: qualityHeat(t.taken, radius, `${taken}, shot quality`, lit),
      allowed: qualityHeat(t.allowed, radius, `${allowed}, shot quality`, lit),
    },
  };
}

export const teamBands = (t: TeamSeason, up: string, down: string) => ({
  taken: bandRows(t.bands, t.leagueBands, up, down),
  allowed: bandRows(t.bandsAllowed, t.leagueBands, up, down, true),
});

// ---- Roster --------------------------------------------------------------------------------

export function rosterHtml(t: TeamSeason, base: string): string {
  if (!t.roster.length) return `<tr class="empty"><td colspan="16">No box-score lines this season.</td></tr>`;
  return t.roster
    .map((p) => {
      const tt = totalsOf(t.rosterFields, p.totals);
      const name = p.slug ? `<a href="${base}/players/${p.slug}/">${esc(p.name)}</a>` : esc(p.name);
      return `<tr><td class="num muted">${esc(p.dorsal)}</td><th scope="row">${name}</th>${SEASON_COLS.map((c) => `<td class="num">${c.cell(tt)}</td>`).join("")}</tr>`;
    })
    .join("");
}

// ---- Teams index -----------------------------------------------------------------------------

/** A season's clubs for the teams index: the figures unrounded, keyed by the ranking's metrics (lib/ranking.ts),
 * in net order. The share metrics (3PA rate, and the opponent's) come from the field-goal totals. */
export function clubRows(fields: string[], teams: ClubLine[]): IndexRow[] {
  return teams
    .map((t) => {
      const f = factors(fields, t.totals, t.opp);
      const own = totalsOf(fields, t.totals);
      const opp = totalsOf(fields, t.opp);
      const share = (x: Totals) => (100 * x.fg3a) / (x.fg2a + x.fg3a);
      return { code: t.code, name: t.name, w: t.w, l: t.l, f: { ...f, tpar: share(own), otpar: share(opp) } };
    })
    .sort((a, b) => b.f.net - a.f.net);
}

/** The league's own rates for the index charts' reference lines, from the league totals. */
export function leagueRates(fields: string[], league: { totals: number[] }): Rates {
  const lg = factors(fields, league.totals, league.totals);
  return { ortg: lg.ortg, drtg: lg.drtg, pace: lg.pace };
}
