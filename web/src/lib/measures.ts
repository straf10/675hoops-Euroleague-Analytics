// Measures, views and the query string for the Players page: the pure definitions, with no
// browser-only imports, so Node can test them (see players.test.ts). lib/players.ts re-exports them.

// The .ts extensions let Node run this file directly (the tests); the build accepts them too.
import { betterOf } from "./better.ts";
import { LEGACY_POSITION, POSITIONS, type Position } from "./position.ts";

export type Rate = "game" | "36" | "100";
export type ColumnSet = "box" | "shooting" | "advanced";

export interface View {
  season: number;
  metric: string; // the measure the players are ranked on
  dir: "desc" | "asc";
  minMin: number; // minutes per game, at least
  top: number; // players shown; 0 = all
  pos: Position | ""; // "" = every position
  set: ColumnSet; // which columns the table shows
  rate: Rate; // counts per game, per 36 minutes or per 100 possessions
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
  /** Enough attempts or minutes to rank on this measure. */
  qualifies?: (t: Totals) => boolean;
  signed?: boolean;
}

/** One player's RAPM on the season's board (points per 100 possessions) and his minutes on it. */
export interface RapmRow {
  total: number;
  minutes: number;
}

/** The RAPM board for one finished season. Only seasons with a board offer the RAPM measure. */
export interface RapmData {
  season: number;
  label: string;
  /** The board's minimum minutes: players below it are not ranked. */
  minimum: number;
  /** Stats player id -> his row. */
  players: Record<string, RapmRow>;
}

/** The board as the build reads it (web/src/lib/m6.ts's RapmBoard, by its shape). */
export function rapmData(
  board: {
    season: number;
    minimum_minutes: number;
    players: { person_id: string; total: number; minutes: number }[];
  },
  label: string,
): RapmData {
  return {
    season: board.season,
    label,
    minimum: board.minimum_minutes,
    players: Object.fromEntries(
      board.players.map((p) => [p.person_id.replace(/^P:/, ""), { total: p.total, minutes: p.minutes }]),
    ),
  };
}

const fga = (t: Totals) => t.fg2a + t.fg3a;
const fgm = (t: Totals) => t.fg2m + t.fg3m;
const ratio = (num: number, den: number) => (den > 0 ? (100 * num) / den : null);

/** Minutes a game that a percentage needs before it ranks: ten. */
const TEN_A_GAME = (t: Totals) => t.sec >= 600 * t.gp;

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
  // Advanced: each formula reads the season totals (see the glossary for the words).
  {
    key: "net",
    head: "Net",
    name: "Net rating",
    about: "Points scored minus points allowed per 100 possessions on court: 100 × (+/-) / possessions",
    kind: "fixed",
    digits: 1,
    signed: true,
    value: (t) => (t.poss > 0 ? (100 * t.pm) / t.poss : null),
    // Fifteen possessions a game is about eight minutes on court.
    qualifies: (t) => t.poss >= 15 * t.gp,
  },
  {
    key: "ast_tov",
    head: "AST/TOV",
    name: "Assists per turnover",
    about: "Assists divided by turnovers. Shown as a dash with no turnovers.",
    kind: "fixed",
    digits: 2,
    value: (t) => (t.tov > 0 ? t.ast / t.tov : null),
    qualifies: (t) => t.tov >= t.gp,
  },
  {
    key: "ast_pct",
    head: "AST%",
    name: "Assist %",
    about: "Share of his team's field goals he assisted while on court",
    kind: "pct",
    digits: 1,
    // Basketball-Reference: 100 × AST / ((MP / (team MP / 5)) × team FGM − FGM). With the season's
    // sums, team MP / 5 is the summed game length (game_sec) and MP is the summed minutes (sec).
    value: (t) => {
      const teamShare = t.game_sec > 0 ? (t.sec / t.game_sec) * t.tm_fgm - fgm(t) : 0;
      return teamShare > 0 ? (100 * t.ast) / teamShare : null;
    },
    qualifies: TEN_A_GAME,
  },
  {
    key: "reb_pct",
    head: "REB%",
    name: "Rebound %",
    about: "Share of the rebounds available while he was on court that he grabbed",
    kind: "pct",
    digits: 1,
    // Basketball-Reference: 100 × TRB × (team MP / 5) / (MP × (team TRB + opponent TRB)).
    value: (t) => {
      const available = t.tm_oreb + t.tm_dreb + t.opp_oreb + t.opp_dreb;
      return t.sec > 0 && available > 0 ? (100 * (t.oreb + t.dreb) * t.game_sec) / (t.sec * available) : null;
    },
    qualifies: TEN_A_GAME,
  },
  {
    key: "rapm",
    head: "RAPM",
    name: "RAPM",
    about: "Points per 100 possessions a player adds, offence and defence together, against an average player. Finished seasons only.",
    kind: "fixed",
    digits: 1,
    value: (t) => t.rapm ?? null,
    qualifies: (t) => (t.rapm_min ?? 0) >= (t.rapm_floor ?? Infinity),
  },
];

export const BY_KEY = Object.fromEntries(MEASURES.map((m) => [m.key, m]));

export const SETS: Record<ColumnSet, string[]> = {
  box: ["gp", "min", "pts", "reb", "ast", "stl", "blk", "tov", "pir", "pm"],
  shooting: ["fga", "fg_pct", "fg2_pct", "fg3a", "fg3_pct", "fta", "ft_pct", "efg", "ts", "usg"],
  advanced: ["net", "ast_tov", "ast_pct", "reb_pct", "rapm"],
};

/** On a phone each set sheds into two groups (GROUPS.players in lib/cols.ts, same order). The
 *  Players page's CSS hides the other columns by their place in SETS: keep the three in step. The
 *  advanced set has no phone groups: it shows all its columns. */
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
  ...POSITIONS.map((p) => ({ key: p, label: p })),
];
/** The rate segment: counts per game, per 36 minutes or per 100 possessions. */
export const RATE_CHOICES: { key: Rate; label: string; name: string }[] = [
  { key: "game", label: "Per game", name: "per game" },
  { key: "36", label: "Per 36", name: "per 36 minutes" },
  { key: "100", label: "Per 100", name: "per 100 possessions" },
];

export const DEFAULT_VIEW: Omit<View, "season"> = {
  metric: "pts",
  dir: "desc",
  minMin: 10,
  top: 25,
  pos: "",
  set: "box",
  rate: "game",
};

/** The column set a measure is shown in. */
export const setOf = (key: string): ColumnSet =>
  SETS.box.includes(key) ? "box" : SETS.shooting.includes(key) ? "shooting" : "advanced";

/** The start direction of a measure: its best end first (fewest turnovers, the highest of the rest). */
export const dirOf = (key: string): "desc" | "asc" => (betterOf(key) === "lower" ? "asc" : "desc");

/** The columns the table shows: RAPM only when the season has a board. */
export const columnsOf = (view: View, rapm: boolean): string[] => SETS[view.set].filter((k) => rapm || k !== "rapm");

/** The Metric select's groups, in column order. */
export const METRIC_GROUPS: { label: string; keys: string[] }[] = [
  { label: "Box score", keys: SETS.box },
  { label: "Shooting", keys: SETS.shooting },
  { label: "Advanced", keys: SETS.advanced },
];

export function rated(m: Measure, t: Totals, rate: Rate): number | null {
  const raw = m.value(t);
  if (raw === null || m.kind !== "count") return raw;
  if (rate === "game") return t.gp ? raw / t.gp : null;
  if (rate === "36") return t.sec ? (raw * 2160) / t.sec : null;
  return t.poss ? (raw * 100) / t.poss : null;
}

export function format(m: Measure, v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "–";
  const text = Math.abs(v).toFixed(m.digits);
  if (m.signed && v > 0) return `+${text}`;
  if (v < 0 && Number(text) !== 0) return `−${text}`;
  return text;
}

export function measureTitle(view: View): string {
  const m = BY_KEY[view.metric] ?? BY_KEY.pts;
  if (m.kind !== "count") return m.key === "min" ? "Minutes per game" : m.name;
  const rate = RATE_CHOICES.find((r) => r.key === view.rate) ?? RATE_CHOICES[0];
  return `${m.name} ${rate.name}`;
}

/** View <-> query string: only values that differ from the defaults are written. Parameters from
 *  older versions of the page (sort, window, team, q, minMin) are ignored. */
export function toQuery(view: View, defaultSeason: number): string {
  const p = new URLSearchParams();
  if (view.season !== defaultSeason) p.set("season", String(view.season));
  if (view.metric !== DEFAULT_VIEW.metric) p.set("metric", view.metric);
  if (view.dir !== dirOf(view.metric)) p.set("dir", view.dir);
  if (view.minMin !== DEFAULT_VIEW.minMin) p.set("min", String(view.minMin));
  if (view.top !== DEFAULT_VIEW.top) p.set("top", String(view.top));
  if (view.pos) p.set("pos", view.pos);
  if (view.rate !== DEFAULT_VIEW.rate) p.set("rate", view.rate);
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
    dir: pick("dir", ["desc", "asc"] as const, dirOf(metric)),
    minMin,
    top: TOPS.includes(top) ? top : DEFAULT_VIEW.top,
    // Old `?pos=Wing` / `?pos=Big` links map to Forward / Centre.
    pos:
      LEGACY_POSITION.get(p.get("pos") ?? "") ??
      pick("pos", ["Guard", "Forward", "Centre"] as const, DEFAULT_VIEW.pos as Position | ""),
    set: pick("set", ["box", "shooting", "advanced"] as const, setOf(metric)),
    rate: pick("rate", ["game", "36", "100"] as const, DEFAULT_VIEW.rate),
  };
}
