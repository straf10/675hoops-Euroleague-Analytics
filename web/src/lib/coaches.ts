// Coach pages: the files `eurohoops export-stats` writes to src/data/stats/coaches (stats/coaches.py).
// Every number is a raw total or a rounded expectation; the pages derive win percentages here.
// The index page's sortable table (the metrics, the sort, the query string and the markup) is at the end.

import { esc } from "./format.ts";
import { dataTip, tip } from "./tip.ts";

export interface Counts {
  games: number;
  wins: number;
  losses: number;
  expected_wins: number;
  wins_above_expectation: number;
}

/** Seasons (career) with a playoff game, with a Final Four game and with the Final Four title. */
export interface CoachPlayoffs {
  seasons: number;
  final_four: number;
  titles: number;
}

export interface CoachIndexRow extends Counts {
  slug: string;
  name: string;
  seasons_played: number[];
  clubs: string[];
  playoffs?: CoachPlayoffs; // missing in coach data exported before playoffs were added
}

export interface Coverage {
  season: number;
  games: number;
  with_coach: number;
}

/** The coach of a club in the latest season: their most recent game there (display code). */
export interface CoachCurrent {
  team: string;
  slug: string;
}

export interface CoachIndex {
  h2h_min_games: number;
  coverage: Coverage[];
  /** The latest season with coach rows, or null without any. */
  current_season: number | null;
  /** The day (YYYY-MM-DD) of the latest box score behind `current`; null without one. */
  current_through: string | null;
  current: CoachCurrent[];
  coaches: CoachIndexRow[];
}

export interface CoachSeason extends Counts {
  season: number;
  team: string;
  team_name: string;
}

export interface CoachClub {
  team: string;
  team_name: string;
  seasons: number[];
}

export interface CoachHeadToHead extends Counts {
  slug: string;
  name: string;
}

export interface CoachPage {
  slug: string;
  name: string;
  career: Counts;
  seasons: CoachSeason[];
  clubs: CoachClub[];
  h2h: CoachHeadToHead[];
  style: CoachStyle | null;
}

/** Coaching style (stats/coach_style.py): the coach's figures and the league's over the same seasons. */
export interface CoachStyle {
  ato: { possessions: number; points: number; ppp: number | null; league_ppp: number | null };
  clutch: {
    games: number;
    team_games: number;
    wins: number;
    losses: number;
    league_share: number | null;
  };
  rotation: {
    games: number;
    players_per_game: number | null;
    top7_share: number | null;
    league_players_per_game: number | null;
    league_top7_share: number | null;
  };
  challenges: {
    from_season: number;
    games: number;
    per_game: number | null;
    late_share: number | null;
    league_per_game: number | null;
    league_late_share: number | null;
  } | null;
}

/** Wins over games as a percentage with one decimal ("61.3%"); "-" with no games. */
export function winPct(c: Pick<Counts, "games" | "wins">): string {
  return c.games === 0 ? "-" : `${((100 * c.wins) / c.games).toFixed(1)}%`;
}

/** A signed figure with one decimal: "+17.4", "-3.0", "0.0". */
/** A per-game figure with the given decimals ("1.05"); "-" without a value. */
export function rate(value: number | null, digits = 2): string {
  return value === null ? "-" : value.toFixed(digits);
}

/** A share as a whole percentage ("55%"); "-" without a value. */
export function share(value: number | null): string {
  return value === null ? "-" : `${Math.round(100 * value)}%`;
}

export function signed(value: number): string {
  const text = value.toFixed(1);
  if (/^-?0\.0$/.test(text)) return "0.0";
  return text.startsWith("-") ? text : `+${text}`;
}

/** The first and last season of a list, as "2015-16" and "2026-27" (or one season). */
export function seasonRange(seasons: number[]): string {
  if (seasons.length === 0) return "-";
  const label = (y: number) => `${y}-${String((y + 1) % 100).padStart(2, "0")}`;
  const first = Math.min(...seasons);
  const last = Math.max(...seasons);
  return first === last ? label(first) : `${label(first)} to ${label(last)}`;
}

/** One entry of the coach search list the coaches page embeds (every coach, any season). */
export interface CoachSearchEntry {
  name: string;
  href: string;
  seasons: number[];
  clubs: string[];
}

/** Lower case, no accents, single spaces: "Željko  Obradović" becomes "zeljko obradovic". */
export function normaliseName(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
}

/** The entries whose name holds every word of the query (parts of words, any order); none for a blank query. */
export function searchCoaches<T extends { name: string }>(entries: T[], query: string): T[] {
  const words = normaliseName(query).split(" ").filter(Boolean);
  if (words.length === 0) return [];
  return entries.filter((e) => {
    const name = normaliseName(e.name);
    return words.every((w) => name.includes(w));
  });
}

/* ---- The index table: metrics, sort, scope, markup ---------------------------------------- */

/** Minimum samples for a rate to be ranked (below them the figure shows greyed and sorts last). */
export const MIN_SAMPLE = {
  /** Games, for win %, and for the players used and top-7 share (rotation games). */
  games: 20,
  /** After-timeout possessions. */
  possessions: 50,
  /** Clutch games, for clutch win %. */
  clutch: 10,
} as const;

export type Dir = "asc" | "desc";

/** One coach on the index table: career record and playoffs, and the style figures (null without a coach page). */
export interface CoachRow {
  slug: string;
  name: string;
  href: string;
  games: number;
  wins: number;
  losses: number;
  seasons: number;
  /** The display code of the club the coach holds now, or null. */
  now: string | null;
  playoffs?: CoachPlayoffs;
  style: CoachStyle | null;
}

/** A metric's figure. `thin` marks a rate below its minimum sample: shown greyed, never ranked. */
interface Measure {
  value: number | null;
  thin: boolean;
}

type Kind = "int" | "pct1" | "pct0" | "dec1" | "dec2";

interface CoachMetric {
  key: string;
  /** The column head (plain words). */
  head: string;
  /** The tooltip: what the column counts and any minimum sample. */
  about: string;
  kind: Kind;
  read: (r: CoachRow) => Measure;
}

const plain = (value: number | null): Measure => ({ value, thin: false });
const sampled = (value: number | null, n: number, min: number): Measure => ({
  value,
  thin: n < min,
});

/** Every sortable column, in table order. */
export const COACH_METRICS: CoachMetric[] = [
  {
    key: "games",
    head: "Games",
    about: "Games in the box scores that name him as coach.",
    kind: "int",
    read: (r) => plain(r.games),
  },
  {
    key: "wins",
    head: "Wins",
    about: "Wins in those games.",
    kind: "int",
    read: (r) => plain(r.wins),
  },
  {
    key: "losses",
    head: "Losses",
    about: "Losses in those games.",
    kind: "int",
    read: (r) => plain(r.losses),
  },
  {
    key: "win_pct",
    head: "Win %",
    about: `Wins as a share of games. Needs ${MIN_SAMPLE.games} games to be ranked.`,
    kind: "pct1",
    read: (r) => sampled(r.games ? r.wins / r.games : null, r.games, MIN_SAMPLE.games),
  },
  {
    key: "seasons",
    head: "Seasons",
    about: "Seasons with at least one game the box scores credit to him.",
    kind: "int",
    read: (r) => plain(r.seasons),
  },
  {
    key: "playoffs",
    head: "Playoffs",
    about: "Seasons with a playoff game (the play-in does not count). The box scores name coaches from 2015-16 on; earlier seasons are not counted.",
    kind: "int",
    read: (r) => plain(r.playoffs?.seasons ?? null),
  },
  {
    key: "final_four",
    head: "Final Four",
    about: "Seasons with a Final Four game. Counted from 2015-16 on, as for playoffs.",
    kind: "int",
    read: (r) => plain(r.playoffs?.final_four ?? null),
  },
  {
    key: "titles",
    head: "Titles",
    about: "Seasons he coached the Final Four champion in the final. Counted from 2015-16 on, as for playoffs.",
    kind: "int",
    read: (r) => plain(r.playoffs?.titles ?? null),
  },
  {
    key: "ato",
    head: "After timeout",
    about: `Points per possession on the first possession after his own timeouts. Needs ${MIN_SAMPLE.possessions} possessions.`,
    kind: "dec2",
    read: (r) =>
      r.style
        ? sampled(r.style.ato.ppp, r.style.ato.possessions, MIN_SAMPLE.possessions)
        : plain(null),
  },
  {
    key: "clutch_pct",
    head: "Clutch win %",
    about: `Wins in clutch games: within 5 points with 5:00 or less left in the 4th or in overtime. Needs ${MIN_SAMPLE.clutch} clutch games.`,
    kind: "pct0",
    read: (r) => {
      if (!r.style) return plain(null);
      const { wins, losses, games } = r.style.clutch;
      const decided = wins + losses;
      return sampled(decided ? wins / decided : null, games, MIN_SAMPLE.clutch);
    },
  },
  {
    key: "clutch_games",
    head: "Clutch games",
    about: "Games that were clutch games (see Clutch win %).",
    kind: "int",
    read: (r) => plain(r.style ? r.style.clutch.games : null),
  },
  {
    key: "players",
    head: "Players used",
    about: `Players who played a minute, per game. Needs ${MIN_SAMPLE.games} games.`,
    kind: "dec1",
    read: (r) =>
      r.style
        ? sampled(r.style.rotation.players_per_game, r.style.rotation.games, MIN_SAMPLE.games)
        : plain(null),
  },
  {
    key: "top7",
    head: "Top 7 minutes",
    about: `Share of minutes played by the top seven players by minutes. Needs ${MIN_SAMPLE.games} games.`,
    kind: "pct0",
    read: (r) =>
      r.style
        ? sampled(r.style.rotation.top7_share, r.style.rotation.games, MIN_SAMPLE.games)
        : plain(null),
  },
  {
    key: "challenges",
    head: "Challenges per game",
    about: `Coach challenges per game, from 2021-22. The data does not show whether they were upheld. Needs ${MIN_SAMPLE.games} games.`,
    kind: "dec2",
    read: (r) => {
      const c = r.style?.challenges;
      return c ? sampled(c.per_game, c.games, MIN_SAMPLE.games) : plain(null);
    },
  },
  {
    key: "late",
    head: "Late challenges",
    about: `Share of challenges used in the 4th quarter or overtime. Needs ${MIN_SAMPLE.games} games.`,
    kind: "pct0",
    read: (r) => {
      const c = r.style?.challenges;
      return c ? sampled(c.late_share, c.games, MIN_SAMPLE.games) : plain(null);
    },
  },
];

export const DEFAULT_METRIC = "games";

const metricOf = (key: string): CoachMetric | undefined =>
  COACH_METRICS.find((m) => m.key === key);

/** The rows of the index, with each coach's figures; `styles` is keyed by slug (null: no coach page). */
export function coachRows(
  index: CoachIndex,
  styles: Record<string, CoachStyle | null>,
  base: string,
): CoachRow[] {
  const now = new Map(index.current.map((c) => [c.slug, c.team]));
  const href = base.replace(/\/$/, "");
  return index.coaches.map((c) => ({
    slug: c.slug,
    name: c.name,
    href: `${href}/coaches/${c.slug}/`,
    games: c.games,
    wins: c.wins,
    losses: c.losses,
    seasons: c.seasons_played.length,
    now: now.get(c.slug) ?? null,
    playoffs: c.playoffs,
    style: styles[c.slug] ?? null,
  }));
}

/** The rows in the order of a metric. A tie keeps the order the rows came in; a missing or thin
 * figure goes last whichever way the sort runs. */
export function sortCoaches(rows: CoachRow[], key: string, dir: Dir): CoachRow[] {
  const read = (metricOf(key) ?? COACH_METRICS[0]).read;
  const sign = dir === "desc" ? -1 : 1;
  const value = (r: CoachRow) => {
    const m = read(r);
    return m.thin ? null : m.value;
  };
  return rows
    .map((row, i) => ({ row, i, v: value(row) }))
    .sort((a, b) => {
      if (a.v === null || b.v === null) return a.v === b.v ? a.i - b.i : a.v === null ? 1 : -1;
      return sign * (a.v - b.v) || a.i - b.i;
    })
    .map(({ row }) => row);
}

export type Scope = "current" | "all";

/** The coaches a scope lists: "current" the holders of a club now, "all" every coach. */
export function scopeRows(rows: CoachRow[], scope: Scope): CoachRow[] {
  return scope === "current" ? rows.filter((r) => r.now !== null) : rows;
}

export interface CoachView {
  scope: Scope;
  metric: string;
  dir: Dir;
}

/** Unknown or missing values fall back to the defaults: the page's scope, then games, most first. */
export function coachViewFromQuery(search: string, fallback: Scope): CoachView {
  const p = new URLSearchParams(search);
  const asked = p.get("metric") ?? "";
  const sort = p.get("sort");
  const scope = p.get("scope");
  return {
    scope: scope === "all" || scope === "current" ? scope : fallback,
    metric: metricOf(asked) ? asked : DEFAULT_METRIC,
    dir: sort === "asc" || sort === "desc" ? sort : "desc",
  };
}

/** The view as a query string; defaults (the page's scope, games, most first) are left out. */
export function coachViewToQuery(view: CoachView, fallback: Scope): string {
  const p = new URLSearchParams();
  if (view.scope !== fallback) p.set("scope", view.scope);
  if (view.metric !== DEFAULT_METRIC) p.set("metric", view.metric);
  if (view.dir === "asc") p.set("sort", "asc");
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** One figure as the table prints it: "-" without a value. */
export function formatMeasure(m: Measure, kind: Kind): string {
  const v = m.value;
  if (v === null) return "-";
  switch (kind) {
    case "int":
      return String(Math.round(v));
    case "pct1":
      return `${(100 * v).toFixed(1)}%`;
    case "pct0":
      return share(v);
    case "dec1":
      return rate(v, 1);
    case "dec2":
      return rate(v, 2);
  }
}

/** The head row: the plain columns (coach, club now), then one sortable column per metric. */
export function coachHeadHtml(view: CoachView): string {
  const cols = COACH_METRICS.map((m) => {
    const on = m.key === view.metric;
    const sort = on ? (view.dir === "desc" ? "descending" : "ascending") : "none";
    const info = dataTip(tip`<b>${m.head}</b><br>${m.about}`);
    return (
      `<th scope="col" class="num${on ? " on" : ""}" aria-sort="${sort}"><span class="head">` +
      `<button type="button" data-sort="${m.key}">${esc(m.head)}</button>` +
      `<button type="button" class="info-tip" aria-label="What does ${esc(m.head)} mean?"${info}>?</button>` +
      `</span></th>`
    );
  });
  return (
    `<tr><th scope="col">Coach</th><th scope="col">Club now</th>${cols.join("")}</tr>`
  );
}

/** The body rows for the rows given (the caller filters and sorts); a thin rate is greyed. */
export function coachRowsHtml(rows: CoachRow[], metric: string): string {
  return rows
    .map((r) => {
      const cells = COACH_METRICS.map((m) => {
        const measure = m.read(r);
        const classes = ["num"];
        if (m.key === metric) classes.push("strong");
        if (measure.thin) classes.push("thin");
        return `<td class="${classes.join(" ")}">${formatMeasure(measure, m.kind)}</td>`;
      }).join("");
      return (
        `<tr><th scope="row"><a href="${esc(r.href)}">${esc(r.name)}</a></th>` +
        `<td class="now">${esc(r.now ?? "–")}</td>${cells}</tr>`
      );
    })
    .join("");
}

/** The table's caption for screen readers: "Coaches this season, by win %". */
export function coachCaption(view: CoachView, title: string): string {
  const name = metricOf(view.metric)?.head ?? "Games";
  return `${title}, by ${name.toLowerCase()}`;
}
