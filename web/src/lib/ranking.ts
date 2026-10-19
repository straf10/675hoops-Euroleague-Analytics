// The Teams index ranking: the metrics it can sort by, the sort, the heading and the query string.
// Pure (types and better.ts only), so the build and the in-page season switch share it, and
// `node --test` runs it. The page's table and charts are built from these in clubs.ts and scatter.ts.

import { betterOf } from "./better.ts";
import type { ClubPlot } from "./scatter.ts";

export type Dir = "asc" | "desc";

/** One club's season on the index: its figures unrounded, keyed by metric (see METRICS). */
export interface IndexRow {
  code: string;
  name: string;
  w: number;
  l: number;
  f: Record<string, number>;
}

/** The league's own rates: the chart's reference lines. */
export interface Rates {
  ortg: number;
  drtg: number;
  pace: number;
}

/** One season on the index, clubs in net order. */
export interface IndexSeason {
  label: string;
  league: Rates;
  rows: IndexRow[];
}

export interface Metric {
  key: string;
  /** The name: the heading says "By" + this, lower-case first letter. */
  name: string;
  /** The column head. */
  head: string;
  about: string;
}

export const METRICS: Metric[] = [
  { key: "net", name: "Net rating", head: "Net", about: "Offensive rating minus defensive rating, points per 100 possessions" },
  { key: "ortg", name: "Offensive rating", head: "ORtg", about: "Points scored per 100 possessions" },
  { key: "drtg", name: "Defensive rating", head: "DRtg", about: "Points allowed per 100 opponent possessions" },
  { key: "pace", name: "Pace", head: "Pace", about: "Possessions per 40 minutes" },
  { key: "efg", name: "Effective FG%", head: "eFG%", about: "(FGM + 0.5 × 3PM) / FGA" },
  { key: "tov", name: "Turnover rate", head: "TOV%", about: "Turnovers per 100 plays: TOV / (FGA + 0.44 × FTA + TOV)" },
  { key: "oreb", name: "Offensive rebound %", head: "ORB%", about: "Share of its own misses the club rebounded" },
  { key: "ftr", name: "Free-throw rate", head: "FT rate", about: "Free throws made per 100 field-goal attempts" },
  { key: "tpar", name: "3PA rate", head: "3PA rate", about: "Three-point attempts per 100 field-goal attempts" },
  { key: "oefg", name: "Opponent eFG%", head: "Opp eFG%", about: "Opponents' effective FG%" },
  { key: "otov", name: "Turnovers forced", head: "Forced TOV%", about: "Opponent turnovers per 100 opponent plays" },
  { key: "dreb", name: "Defensive rebound %", head: "DRB%", about: "Share of opponents' misses the club rebounded" },
  { key: "oftr", name: "Opponent free-throw rate", head: "Opp FT rate", about: "Opponent free throws made per 100 of their field-goal attempts" },
  { key: "otpar", name: "Opponent 3PA rate", head: "Opp 3PA rate", about: "Opponent three-point attempts per 100 of their field-goal attempts" },
  { key: "returning", name: "Returning minutes", head: "Returning", about: "Share of last season's club minutes played by players on this season's roster" },
  { key: "sos_played", name: "Schedule strength, played so far", head: "SoS played", about: "Venue-adjusted mean Elo of the opponents played so far. Higher is a harder schedule" },
  { key: "sos_ahead", name: "Schedule strength, upcoming", head: "SoS ahead", about: "Venue-adjusted mean Elo of the games still to play. Higher is a harder schedule" },
];

/** The Metric select's groups, in the order they show. */
export const METRIC_GROUPS: { label: string; keys: string[] }[] = [
  { label: "Ratings and pace", keys: ["net", "ortg", "drtg", "pace"] },
  { label: "Shooting and turnovers", keys: ["efg", "tov", "oreb", "ftr", "tpar"] },
  { label: "Opponent", keys: ["oefg", "otov", "dreb", "oftr", "otpar"] },
  { label: "Roster", keys: ["returning"] },
  { label: "Schedule", keys: ["sos_played", "sos_ahead"] },
];

export const DEFAULT_METRIC = "net";

/** The columns every table shows (the sortable ones); a metric outside them gets a column after Pace. */
export const BASE_KEYS = ["ortg", "drtg", "net", "pace", "sos_played", "sos_ahead"];

export const metricOf = (key: string): Metric | undefined => METRICS.find((m) => m.key === key);

/** The better end first: a lower-is-better metric starts ascending, every other one descending. */
export const bestDir = (key: string): Dir => (betterOf(key) === "lower" ? "asc" : "desc");

/** The table's columns for a metric, in order. */
export const columnKeys = (metric: string): string[] => (BASE_KEYS.includes(metric) ? BASE_KEYS : [...BASE_KEYS, metric]);

/** The phone column group (lib/cols.ts GROUPS.clubs) that holds a metric's column, or -1 for any group. */
export const phoneGroup = (metric: string): number =>
  metric === "ortg" || metric === "drtg" ? 1 : metric === "pace" ? 2 : metric.startsWith("sos_") ? 3 : -1;

/**
 * Rows in the order of a metric. A tie keeps the order the rows came in (net order), and a missing
 * figure goes last whichever way the sort runs.
 */
export function sortRows(rows: IndexRow[], key: string, dir: Dir): IndexRow[] {
  const sign = dir === "desc" ? -1 : 1;
  const value = (r: IndexRow) => (Number.isFinite(r.f[key]) ? r.f[key] : null);
  return rows
    .map((row, i) => ({ row, i, v: value(row) }))
    .sort((a, b) => {
      if (a.v === null || b.v === null) return a.v === b.v ? a.i - b.i : a.v === null ? 1 : -1;
      return sign * (a.v - b.v) || a.i - b.i;
    })
    .map(({ row }) => row);
}

/** "By net rating", "By offensive rating": the heading follows the metric. */
export const headingOf = (key: string): string => {
  const name = metricOf(key)?.name ?? "Net rating";
  return `By ${name.charAt(0).toLowerCase()}${name.slice(1)}`;
};

/** The table's caption for screen readers: "2025-26 clubs by net rating". */
export const captionOf = (label: string, key: string): string => {
  const h = headingOf(key);
  return `${label} clubs ${h.charAt(0).toLowerCase()}${h.slice(1)}`;
};

/** The chart's data for one season: the same figures the table ranks on. */
export function plotOf(season: IndexSeason): ClubPlot {
  return {
    league: season.league,
    clubs: season.rows.map((r) => ({ code: r.code, name: r.name, ortg: r.f.ortg, drtg: r.f.drtg, net: r.f.net, pace: r.f.pace })),
  };
}

export interface View {
  season: number;
  metric: string;
  dir: Dir;
}

/** View <-> query string. Only values that differ from the defaults are written. */
export function toQuery(view: View, defaultSeason: number): string {
  const p = new URLSearchParams();
  if (view.season !== defaultSeason) p.set("season", String(view.season));
  if (view.metric !== DEFAULT_METRIC) p.set("metric", view.metric);
  if (view.dir !== bestDir(view.metric)) p.set("sort", view.dir);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** Unknown or missing values fall back to the defaults; a season must be one the page holds. */
export function fromQuery(search: string, seasons: number[], defaultSeason: number): View {
  const p = new URLSearchParams(search);
  const season = Number(p.get("season"));
  const asked = p.get("metric") ?? "";
  const metric = metricOf(asked) ? asked : DEFAULT_METRIC;
  const sort = p.get("sort");
  return {
    season: seasons.includes(season) ? season : defaultSeason,
    metric,
    dir: sort === "asc" || sort === "desc" ? sort : bestDir(metric),
  };
}
