// Compare, Teams mode: club-seasons side by side. A column is one club in one season. The measures
// are the teams index's (lib/ranking.ts, so the same figures) plus a shot profile. The polygon ranks
// each club against every club of its own season (rankPool; the direction of each measure comes from
// betterOf, never a second table). Pure, so `node --test` runs it.

import { betterOf } from "./better.ts";
import { esc, signed } from "./format.ts";
import { metricOf, type IndexRow, type Metric } from "./ranking.ts";
import { rankPool, type Placements } from "./percentile.ts";
import { describeProfile, type Axis, type Profile, type SeriesShape } from "./polygon.ts";

/** Most clubs compared at once: the same cap as players (compare.ts MAX). */
export const TEAM_MAX = 5;

/** A column in the link: a club (the code the stats files use, which is the display code) and a season (its start year). */
export interface TeamPick {
  code: string;
  season: number;
}

/** One season's clubs (the teams index rows, shot shares included) and its label, such as "2025-26". */
export interface TeamSeasonRows {
  season: number;
  label: string;
  rows: IndexRow[];
}

/** Attempts and makes by distance band, as the stats export writes them. */
export type BandCounts = Record<string, [attempts: number, made: number]>;

const BANDS = ["rim", "short", "mid", "long2", "three", "deep3"];
const SHARES: Record<string, string[]> = {
  rim_share: ["rim", "short"],
  mid_share: ["mid", "long2"],
  three_share: ["three", "deep3"],
};

/** The shot profile's measures: shares of a club's own shots, so they have no better side (betterOf says "neither"). */
const SHOT_METRICS: Metric[] = [
  { key: "rim_share", name: "Rim and short share", head: "Rim+short", about: "Share of the club's shots taken at the rim or in the short range" },
  { key: "mid_share", name: "Mid-range share", head: "Mid", about: "Share of the club's shots taken from mid-range or the long two" },
  { key: "three_share", name: "Three-point share", head: "3PT", about: "Share of the club's shots taken from the three-point line" },
];

/** The table's groups, in order. Every key is a teams-index metric or a shot measure above. */
export const TEAM_GROUPS: { name: string; keys: string[] }[] = [
  { name: "Ratings", keys: ["ortg", "drtg", "net", "pace"] },
  { name: "Offense", keys: ["efg", "tov", "oreb", "ftr"] },
  { name: "Defense", keys: ["oefg", "otov", "dreb", "oftr"] },
  { name: "Shot profile", keys: ["rim_share", "mid_share", "three_share"] },
];

/** The polygon's eight axes: the two ratings and the six four-factor measures (eight is the player polygon's cap). */
export const POLYGON_KEYS = ["ortg", "drtg", "efg", "tov", "oreb", "oefg", "otov", "dreb"];

const ALL_KEYS = TEAM_GROUPS.flatMap((g) => g.keys);

export const metricFor = (key: string): Metric | undefined => metricOf(key) ?? SHOT_METRICS.find((m) => m.key === key);

export const POLYGON_AXES: Axis[] = POLYGON_KEYS.map((key) => {
  const m = metricFor(key);
  if (!m) throw new Error(`compare_teams: no metric for axis ${key}`);
  return { key, head: m.head, name: m.name, about: m.about };
});

/** The three shot shares, as percentages of the club's attempts across all six bands. */
export function shotShares(bands: BandCounts): Record<string, number> {
  const attempts = (keys: string[]) => keys.reduce((sum, k) => sum + (bands[k]?.[0] ?? 0), 0);
  const total = attempts(BANDS);
  return Object.fromEntries(Object.entries(SHARES).map(([key, keys]) => [key, total ? (100 * attempts(keys)) / total : NaN]));
}

/** The teams index rows with the shot shares added to each club's figures. A club with no bands gets NaN (a dash). */
export function withShots(rows: IndexRow[], bands: Record<string, BandCounts>): IndexRow[] {
  return rows.map((r) => ({ ...r, f: { ...r.f, ...shotShares(bands[r.code] ?? {}) } }));
}

/** Every club's place in one season, on the given measures. Lower-is-better measures come from betterOf. */
export function placeAll(rows: IndexRow[], keys: string[]): Placements {
  return rankPool(
    rows.map((r) => ({ id: r.code, values: r.f })),
    keys,
    (key) => (betterOf(key) === "lower" ? "lower" : "higher"),
  );
}

/** A column: the club in its season, with the season's places and its size. */
export interface TeamColumn {
  code: string;
  season: number;
  label: string;
  name: string;
  row: IndexRow;
  placements: Placements;
  /** Clubs in the season's pool. */
  pool: number;
}

/** The columns for the picks, in pick order. A pick with no such club-season is left out. */
export function teamColumns(picks: TeamPick[], seasons: TeamSeasonRows[]): TeamColumn[] {
  const placed = new Map<number, Placements>();
  const cols: TeamColumn[] = [];
  for (const p of picks) {
    const s = seasons.find((x) => x.season === p.season);
    const row = s?.rows.find((r) => r.code === p.code);
    if (!s || !row) continue;
    if (!placed.has(s.season)) placed.set(s.season, placeAll(s.rows, ALL_KEYS));
    cols.push({ code: row.code, season: s.season, label: s.label, name: row.name, row, placements: placed.get(s.season)!, pool: s.rows.length });
  }
  return cols;
}

const ordinal = (n: number) => {
  const tail = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${tail}`;
};

/** A figure as the table shows it: one decimal; Net signed; shares with a percent sign. */
export function figure(key: string, v: number | undefined): string {
  if (v === undefined || !Number.isFinite(v)) return "–";
  if (key === "net") return signed(v);
  if (key.endsWith("_share")) return `${v.toFixed(1)}%`;
  return v.toFixed(1);
}

/** Index of the one column that leads a measure among the columns (best value, unique), or -1. */
export function leaderOf(cols: TeamColumn[], key: string): number {
  const sign = betterOf(key) === "lower" ? -1 : 1;
  let best = -1;
  let bestScore = -Infinity;
  let tied = false;
  cols.forEach((c, i) => {
    const v = c.row.f[key];
    if (!Number.isFinite(v)) return;
    const score = sign * v;
    if (score > bestScore) {
      best = i;
      bestScore = score;
      tied = false;
    } else if (score === bestScore) {
      tied = true;
    }
  });
  return cols.length > 1 && !tied ? best : -1;
}

/** The table's head row: remove button, club code, name and season for each column. */
export function teamHeadHtml(cols: TeamColumn[], xIcon: string): string {
  const heads = cols.map(
    (c, i) =>
      `<th scope="col" class="card">` +
      `<button type="button" class="drop" data-drop="${i}" aria-label="Remove ${esc(c.name)} ${esc(c.label)}">${xIcon}</button>` +
      `<span class="tcode">${esc(c.code)}</span>` +
      `<span class="nm">${esc(c.name)}</span>` +
      `<span class="when">${esc(c.label)}</span>` +
      `</th>`,
  );
  return `<tr><td class="corner"></td>${heads.join("")}</tr>`;
}

/** The table's groups: one tbody per group, each figure with its place among the season's clubs. */
export function teamBodyHtml(cols: TeamColumn[]): string {
  const n = cols.length;
  return TEAM_GROUPS.map(
    (g) =>
      `<tbody><tr class="grp"><th scope="colgroup" colspan="${n + 1}">${esc(g.name)}</th></tr>` +
      g.keys
        .map((key) => {
          const m = metricFor(key);
          const lead = leaderOf(cols, key);
          const cells = cols.map((c, i) => {
            const place = c.placements.get(c.code)?.[key] ?? null;
            const dot = i === lead ? `<i class="lead-dot" aria-hidden="true"></i>` : "";
            const small = place ? `<small title="Place among the ${c.pool} clubs that season">${ordinal(place.rank)}</small>` : "<small></small>";
            return `<td class="num${i === lead ? " lead" : ""}"><span class="cell"><span class="v">${dot}${figure(key, c.row.f[key])}</span>${small}</span></td>`;
          });
          return `<tr><th scope="row"><span title="${esc(m?.about ?? "")}" tabindex="0">${esc(m?.head ?? key)}</span></th>${cells.join("")}</tr>`;
        })
        .join("") +
      `</tbody>`,
  ).join("");
}

/** The polygon's series: one shape per column, ranked within its own season. */
export function teamSeries(cols: TeamColumn[]): SeriesShape[] {
  return cols.map((c, i) => {
    const mine = c.placements.get(c.code);
    const profile: Profile = {
      slug: c.code,
      note: mine ? null : "Not in this season's data.",
      pool: c.pool,
      axes: POLYGON_KEYS.map((key) => {
        const p = mine?.[key] ?? null;
        return { key, pct: p ? p.pct : null, rank: p ? p.rank : null, of: p ? p.of : 0 };
      }),
    };
    return { name: `${c.name} ${c.label}`, slot: (i % 5) + 1, profile };
  });
}

/** The polygon's text fallback, one sentence per column. */
export function teamDescription(cols: TeamColumn[]): string {
  return teamSeries(cols)
    .map((s) => describeProfile(s.name, s.profile, POLYGON_AXES))
    .join(" ");
}

/** Every club-season the picker offers: its label (the datalist text) and the pick it stands for. */
export function teamOptions(seasons: TeamSeasonRows[]): { text: string; pick: TeamPick }[] {
  return seasons.flatMap((s) => s.rows.map((r) => ({ text: `${r.name} (${s.label})`, pick: { code: r.code, season: s.season } })));
}

/** The query string for Teams mode: `?mode=teams&t=PAO-2025,OLY-2025`. */
export function teamsToQuery(picks: TeamPick[]): string {
  const q = new URLSearchParams();
  q.set("mode", "teams");
  if (picks.length) q.set("t", picks.map((p) => `${p.code}-${p.season}`).join(","));
  return `?${q.toString().replace(/%2C/g, ",")}`;
}

/**
 * The mode and the team picks in a query string. Unknown or repeated picks are dropped, codes are
 * upper-cased, and the list stops at TEAM_MAX. `known` says whether a club-season exists.
 */
export function teamsFromQuery(search: string, known: (code: string, season: number) => boolean): { mode: "players" | "teams"; picks: TeamPick[] } {
  const q = new URLSearchParams(search);
  const seen = new Set<string>();
  const picks: TeamPick[] = [];
  for (const part of (q.get("t") ?? "").split(",")) {
    const m = /^([a-z0-9]{2,4})-(\d{4})$/i.exec(part.trim());
    if (!m) continue;
    const pick = { code: m[1].toUpperCase(), season: Number(m[2]) };
    const key = `${pick.code}-${pick.season}`;
    if (seen.has(key) || !known(pick.code, pick.season)) continue;
    seen.add(key);
    picks.push(pick);
  }
  return { mode: q.get("mode") === "teams" ? "teams" : "players", picks: picks.slice(0, TEAM_MAX) };
}
