// Coach pages: the files `eurohoops export-stats` writes to src/data/stats/coaches (stats/coaches.py).
// Every number is a raw total or a rounded expectation; the pages derive win percentages here.
// The coaches list shows one season at a time (coaches/seasons.json); its table is at the end.

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
  /** Seasons that lost the Final Four final. Missing in coach data exported before it was added. */
  runner_ups?: number;
  /** Seasons with a play-in game. Missing in coach data exported before it was added. */
  play_ins?: number;
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

/** One coach in one season (coaches/seasons.json): the season's record with its clubs merged (in
 *  order of first game), the season's playoff flags (0 or 1 each) and its style block. */
export interface CoachSeasonRow extends Counts {
  slug: string;
  name: string;
  season: number;
  clubs: string[];
  playoffs: CoachPlayoffs;
  style: CoachStyle | null;
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
    league_per_game: number | null;
    /** Challenges in the clutch window (last 5:00 of the 4th quarter, or overtime) of clutch games. */
    clutch: number;
    clutch_per_clutch_game: number | null;
    league_clutch_per_clutch_game: number | null;
  } | null;
}

/** Wins over games as a percentage with one decimal ("61.3%"); "-" with no games. */
export function winPct(c: Pick<Counts, "games" | "wins">): string {
  return c.games === 0 ? "-" : `${((100 * c.wins) / c.games).toFixed(1)}%`;
}

/** A per-game figure with the given decimals ("1.05"); "-" without a value. */
export function rate(value: number | null, digits = 2): string {
  return value === null ? "-" : value.toFixed(digits);
}

/** A share as a whole percentage ("55%"); "-" without a value. */
export function share(value: number | null): string {
  return value === null ? "-" : `${Math.round(100 * value)}%`;
}

/** A signed figure with one decimal: "+17.4", "-3.0", "0.0". */
export function signed(value: number): string {
  const text = value.toFixed(1);
  if (/^-?0\.0$/.test(text)) return "0.0";
  return text.startsWith("-") ? text : `+${text}`;
}

/** A season as its label: 2026 is "2026-27". */
export function seasonLabel(year: number): string {
  return `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
}

/** The first and last season of a list, as "2015-16" and "2026-27" (or one season). */
export function seasonRange(seasons: number[]): string {
  if (seasons.length === 0) return "-";
  const first = Math.min(...seasons);
  const last = Math.max(...seasons);
  return first === last ? seasonLabel(first) : `${seasonLabel(first)} to ${seasonLabel(last)}`;
}

/** The seasons whose box scores name a coach for most games, newest first (the list's season options). */
export function namedSeasons(coverage: Coverage[]): number[] {
  return coverage
    .filter((c) => 2 * c.with_coach >= c.games)
    .map((c) => c.season)
    .sort((a, b) => b - a);
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

/* ---- The season table: sections, metrics, thresholds, sort, view, markup ----------------- */

/** Minimum samples within one season (about 34 regular-season games a club): a figure below its
 *  sample shows greyed and sorts last, as a dash does. */
export const SEASON_MIN_SAMPLE = {
  /** Games: win %, players used, top 7 minutes and challenges per game. */
  games: 5,
  /** After-timeout possessions. */
  possessions: 25,
  /** Clutch games, for clutch win %. */
  clutch: 5,
} as const;

export type Dir = "asc" | "desc";

/** A figure with its sample: `thin` marks a rate below its minimum, shown greyed and never ranked. */
export interface Measure {
  value: number | null;
  thin: boolean;
}

export const sampled = (value: number | null, n: number, min: number): Measure => ({
  value,
  thin: n < min,
});
const plain = (value: number | null): Measure => ({ value, thin: false });

export type Kind = "int" | "pct1" | "pct0" | "dec1" | "dec2" | "signed1" | "placement";

/** How far a coach's season went: the furthest stage the season's playoff flags show. */
export type Placement = "champion" | "runner_up" | "final_four" | "playoffs" | "play_in" | "regular";

export const PLACEMENT_LABEL: Record<Placement, string> = {
  champion: "Champion",
  runner_up: "Runner-up",
  final_four: "Final Four",
  playoffs: "Playoffs",
  play_in: "Play-in",
  regular: "Regular season",
};

/** Rank of a placement, higher is further: the sort order of the Placement column. */
const PLACEMENT_RANK: Record<Placement, number> = {
  regular: 0,
  play_in: 1,
  playoffs: 2,
  final_four: 3,
  runner_up: 4,
  champion: 5,
};
const PLACEMENT_BY_RANK = Object.fromEntries(
  Object.entries(PLACEMENT_RANK).map(([placement, rank]) => [rank, placement as Placement]),
) as Record<number, Placement>;

/** The placement of a season: the furthest stage its playoff flags show. A play-in game with no
 *  playoff game is a loss in the play-in. */
export function placementOf(p: CoachPlayoffs): Placement {
  if (p.titles > 0) return "champion";
  if ((p.runner_ups ?? 0) > 0) return "runner_up";
  if (p.final_four > 0) return "final_four";
  if (p.seasons > 0) return "playoffs";
  if ((p.play_ins ?? 0) > 0) return "play_in";
  return "regular";
}

/** Placement is shown for a completed season only: the season in progress has none yet. */
export const placementShown = (season: number, openSeason: number): boolean => season !== openSeason;

interface CoachMetric {
  key: string;
  /** The column head (plain words). */
  head: string;
  /** The tooltip: what the column counts and any minimum sample. */
  about: string;
  kind: Kind;
  read: (r: CoachSeasonRow) => Measure;
}

export type SectionKey = "box" | "advanced";

/** The column sets: each lists its own metrics in table order, and no metric sits in both (the coach
 *  and club identify the row in either). Box score: the record and expectation. Advanced: after timeout,
 *  clutch, challenges and rotation. */
export const SECTIONS: { key: SectionKey; label: string; keys: string[] }[] = [
  {
    key: "box",
    label: "Box score",
    keys: ["games", "wins", "losses", "win_pct", "expected_wins", "wins_above_expectation", "placement"],
  },
  {
    key: "advanced",
    label: "Advanced",
    keys: ["ato", "clutch_pct", "clutch_games", "challenges", "clutch_challenges", "players", "top7"],
  },
];

/** Section keys from before the column sets were renamed, so an old link still opens a set:
 *  "expected" is the box score, "rotation" the advanced set (its columns are now there). */
const LEGACY_SECTIONS = new Map<string, SectionKey>([
  ["expected", "box"],
  ["rotation", "advanced"],
]);

/** Every sortable column. */
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
    about: `Wins as a share of games. Needs ${SEASON_MIN_SAMPLE.games} games to be ranked.`,
    kind: "pct1",
    read: (r) => sampled(r.games ? r.wins / r.games : null, r.games, SEASON_MIN_SAMPLE.games),
  },
  {
    key: "expected_wins",
    head: "Expected wins",
    about: "The sum of each game's pre-game Elo win probability for his side.",
    kind: "dec1",
    read: (r) => plain(r.expected_wins),
  },
  {
    key: "wins_above_expectation",
    head: "Above exp.",
    about: "Wins minus expected wins: positive when the coach won more than the Elo ratings expected.",
    kind: "signed1",
    read: (r) => plain(r.wins_above_expectation),
  },
  {
    key: "placement",
    head: "Placement",
    about: "The furthest stage the season reached: champion, runner-up (lost the final), Final Four, playoffs, play-in (lost there) or regular season. Counted from 2015-16 on, when the box scores name coaches. Not shown for the season in progress.",
    kind: "placement",
    read: (r) => plain(PLACEMENT_RANK[placementOf(r.playoffs)]),
  },
  {
    key: "ato",
    head: "After timeout",
    about: `Points per possession on the first possession after his own timeouts. Needs ${SEASON_MIN_SAMPLE.possessions} possessions.`,
    kind: "dec2",
    read: (r) =>
      r.style
        ? sampled(r.style.ato.ppp, r.style.ato.possessions, SEASON_MIN_SAMPLE.possessions)
        : plain(null),
  },
  {
    key: "clutch_pct",
    head: "Clutch win %",
    about: `Wins in clutch games: within 5 points with 5:00 or less left in the 4th or in overtime. Needs ${SEASON_MIN_SAMPLE.clutch} clutch games.`,
    kind: "pct0",
    read: (r) => {
      if (!r.style) return plain(null);
      const { wins, losses, games } = r.style.clutch;
      const decided = wins + losses;
      return sampled(decided ? wins / decided : null, games, SEASON_MIN_SAMPLE.clutch);
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
    key: "challenges",
    head: "Challenges per game",
    about: `Coach challenges per game, from 2021-22. The data does not show whether they were upheld. Needs ${SEASON_MIN_SAMPLE.games} games.`,
    kind: "dec2",
    read: (r) => {
      const c = r.style?.challenges;
      return c ? sampled(c.per_game, c.games, SEASON_MIN_SAMPLE.games) : plain(null);
    },
  },
  {
    key: "clutch_challenges",
    head: "Clutch challenges",
    about: "Coach challenges in the last 5:00 of the 4th quarter or overtime, in clutch games (see Clutch win %). The data does not show whether they were upheld.",
    kind: "int",
    read: (r) => plain(r.style?.challenges ? r.style.challenges.clutch : null),
  },
  {
    key: "players",
    head: "Players used",
    about: `Players who played a minute, per game. Needs ${SEASON_MIN_SAMPLE.games} games.`,
    kind: "dec1",
    read: (r) =>
      r.style
        ? sampled(r.style.rotation.players_per_game, r.style.rotation.games, SEASON_MIN_SAMPLE.games)
        : plain(null),
  },
  {
    key: "top7",
    head: "Top 7 minutes",
    about: `Share of minutes played by the top seven players by minutes. Needs ${SEASON_MIN_SAMPLE.games} games.`,
    kind: "pct0",
    read: (r) =>
      r.style
        ? sampled(r.style.rotation.top7_share, r.style.rotation.games, SEASON_MIN_SAMPLE.games)
        : plain(null),
  },
];

export const DEFAULT_SECTION: SectionKey = "box";
export const DEFAULT_METRIC = "games";

export const metricOf = (key: string): CoachMetric | undefined =>
  COACH_METRICS.find((m) => m.key === key);

/** The sortable columns a column set shows, in table order. Placement is left out for the season in progress. */
export function columnKeys(section: SectionKey, placement = true): string[] {
  return (SECTIONS.find((s) => s.key === section)?.keys ?? []).filter(
    (key) => placement || key !== "placement",
  );
}

/** The column a set sorts by until the reader picks another: its first column. */
export function firstColumn(section: SectionKey): string {
  return SECTIONS.find((s) => s.key === section)?.keys[0] ?? DEFAULT_METRIC;
}

/** A season row on the list, with its link. */
export interface CoachRow extends CoachSeasonRow {
  href: string;
}

/** One season's coach rows, in the order the season file has them: the page embeds the open season
 *  and the season switch fetches `data/coaches/{season}.json`, which is this slice. */
export function seasonOf(rows: CoachSeasonRow[], season: number): CoachSeasonRow[] {
  return rows.filter((r) => r.season === season);
}

/** The coaches of one season, with links (the list is one season at a time). */
export function seasonRows(rows: CoachSeasonRow[], season: number, base: string): CoachRow[] {
  const root = base.replace(/\/$/, "");
  return seasonOf(rows, season).map((r) => ({ ...r, href: `${root}/coaches/${r.slug}/` }));
}

/** The rows in the order of a metric. A tie keeps the order the rows came in; a missing or thin
 * figure goes last whichever way the sort runs. */
export function sortCoaches<T extends CoachSeasonRow>(rows: T[], key: string, dir: Dir): T[] {
  const read = (metricOf(key) ?? COACH_METRICS[0]).read;
  const sign = dir === "desc" ? -1 : 1;
  const value = (r: T) => {
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

export interface CoachView {
  season: number;
  section: SectionKey;
  metric: string;
  dir: Dir;
}

/** Changing section keeps the sort column when the new section shows it, else the section's first. */
export function switchSection(view: CoachView, section: SectionKey, placement = true): CoachView {
  const keys = columnKeys(section, placement);
  if (keys.includes(view.metric)) return { ...view, section };
  return { ...view, section, metric: firstColumn(section), dir: "desc" };
}

/** Changing season keeps the sort column when the new season shows it, else the section's first. */
export function switchSeason(view: CoachView, season: number, openSeason: number): CoachView {
  const next = { ...view, season };
  if (columnKeys(view.section, placementShown(season, openSeason)).includes(view.metric)) return next;
  return { ...next, metric: firstColumn(view.section), dir: "desc" };
}

/** Unknown or missing values fall back to the defaults: the fallback season, the box score, games, most
 *  first. A season must be one of `seasons`. A column the set does not show falls back to its first. */
export function coachViewFromQuery(search: string, seasons: number[], fallbackSeason: number): CoachView {
  const p = new URLSearchParams(search);
  const asked = Number(p.get("season"));
  const sectionAsked = p.get("section") ?? "";
  const section = SECTIONS.some((s) => s.key === sectionAsked)
    ? (sectionAsked as SectionKey)
    : (LEGACY_SECTIONS.get(sectionAsked) ?? DEFAULT_SECTION);
  const metric = p.get("metric") ?? "";
  const sort = p.get("sort");
  const season = seasons.includes(asked) ? asked : fallbackSeason;
  return {
    season,
    section,
    metric: columnKeys(section, placementShown(season, fallbackSeason)).includes(metric)
      ? metric
      : firstColumn(section),
    dir: sort === "asc" ? "asc" : "desc",
  };
}

/** The view as a query string; defaults are left out. */
export function coachViewToQuery(view: CoachView, fallbackSeason: number): string {
  const p = new URLSearchParams();
  if (view.season !== fallbackSeason) p.set("season", String(view.season));
  if (view.section !== DEFAULT_SECTION) p.set("section", view.section);
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
    case "signed1":
      return signed(v);
    case "placement":
      return PLACEMENT_LABEL[PLACEMENT_BY_RANK[Math.round(v)] ?? "regular"];
  }
}

/** The head row: Coach and Club(s), then one sortable column per shown metric. */
export function coachHeadHtml(view: CoachView, placement = true): string {
  const cols = columnKeys(view.section, placement).map((k) => metricOf(k)!);
  const heads = cols.map((m) => {
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
  return `<tr><th scope="col">Coach</th><th scope="col">Club</th>${heads.join("")}</tr>`;
}

/** The body rows for the rows given (the caller filters and sorts); a thin rate is greyed. */
export function coachRowsHtml(rows: CoachRow[], view: CoachView, placement = true): string {
  const cols = columnKeys(view.section, placement).map((k) => metricOf(k)!);
  return rows
    .map((r) => {
      const cells = cols
        .map((m) => {
          const measure = m.read(r);
          const classes = ["num"];
          if (m.key === view.metric) classes.push("strong");
          if (measure.thin) classes.push("thin");
          return `<td class="${classes.join(" ")}">${formatMeasure(measure, m.kind)}</td>`;
        })
        .join("");
      return (
        `<tr><th scope="row"><a href="${esc(r.href)}">${esc(r.name)}</a></th>` +
        `<td class="club">${esc(r.clubs.join(", ") || "–")}</td>${cells}</tr>`
      );
    })
    .join("");
}

/** The table's caption for screen readers: "Coaches in 2026-27, by win %". */
export function coachCaption(view: CoachView, title: string): string {
  const name = metricOf(view.metric)?.head ?? "Games";
  return `${title}, by ${name.toLowerCase()}`;
}
