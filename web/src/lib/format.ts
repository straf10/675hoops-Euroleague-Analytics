import type { Forecasts } from "./forecasts";
import type { MatchdayRound } from "./matchday";

export interface Team {
  /** The display code (publish.DISPLAY_CODES). */
  code: string;
  /** The source code the API's team routes take; absent in data built before it was added. */
  source_code?: string;
  name: string;
  /** The short club name (publish.SHORT_NAMES); absent in data built before short names. */
  short?: string;
}

interface Game {
  game_id: string;
  round: number;
  tipoff_utc: string;
  predicted_at_utc: string;
  home: Team;
  away: Team;
  p_home: number;
  exp_margin: number;
}

/** Upcoming games only: the arena (null when the schedule has none) and whether the time is set. */
export interface UpcomingGame extends Game {
  venue: string | null;
  venue_address: string | null;
  tipoff_time_confirmed: boolean;
}

export interface Result extends Game {
  home_score: number;
  away_score: number;
  hit: boolean;
  provable: boolean;
  /** Logged at or after tip-off: shown apart, never counted. */
  late: boolean;
}

/** One equal-width bin of predicted P(home): its games, mean prediction and home win rate. */
interface Bin {
  low: number;
  high: number;
  n: number;
  mean_p: number | null;
  observed: number | null;
}

export interface Metrics {
  n: number;
  log_loss: number | null;
  brier: number | null;
  accuracy: number | null;
  margin_mae: number | null;
  ece: number | null;
  margin_crps: number | null;
  reliability: Bin[];
}

/** Mean log loss over the latest `window` scored games, ending at game `n`. */
export interface RollingPoint {
  game_id: string;
  tipoff_utc: string;
  n: number;
  elo: number;
  b0: number;
}

/** One game of an open round: its latest forecast before tip-off, and its result once played. */
export interface OpenRoundGame {
  game_id: string;
  tipoff_utc: string;
  predicted_at_utc: string;
  home: Team;
  away: Team;
  p_home: number;
  exp_margin: number;
  played: boolean;
  forfeit: boolean;
  home_score: number | null;
  away_score: number | null;
  /** Whether the favourite won; null until the game is played. */
  hit: boolean | null;
}

export interface OpenRound {
  round: number;
  games: OpenRoundGame[];
}

export interface Rating extends Team {
  rating: number;
  change: number;
}

export interface Competition {
  key: string;
  title: string;
  season: string;
  logged: number;
  next_tipoff_utc: string | null;
  /** No game ahead has a confirmed time: show the date only. */
  next_tipoff_time_tbc: boolean;
  upcoming: UpcomingGame[];
  /** Regular-season rounds with a logged forecast and a game still to finish, in round order. */
  open_rounds: OpenRound[];
  results: Result[];
  /** Every round of the live season, in round order (the home page's matchday). */
  matchday: { rounds: MatchdayRound[] };
  scorecard: {
    elo: Metrics;
    b0: Metrics;
    not_provable: number;
    late: number;
    rolling: { window: number; series: RollingPoint[] };
    m1: { n: number; log_loss: number | null; elo_log_loss: number | null } | null;
  };
  backtest: {
    tuning_seasons: number[];
    test_seasons: number[];
    params: { k: number; hca: number; reversion: number };
    test: { elo: Metrics; b0: Metrics };
    log_loss_diff: { mean: number; ci95: [number, number] } | null;
  };
  ratings: Rating[];
  forecasts: Forecasts | null;
}

export interface SiteData {
  generated_at_utc: string;
  competitions: Competition[];
  /** Headline data counts, EuroLeague only (`marts.data_volume`): actions from the play-by-play cache. */
  data_volume: { games: number; seasons: number; shots_with_coordinates?: number; actions?: number };
  /** EuroLeague titles, all-time since `since`: titles by display code (clubs with one or more). */
  el_titles: {
    since: number;
    data_from: string;
    titles: Record<string, number>;
    /** Pre-2007 title winners with no code in our data (listed by name only). */
    uncoded?: { club: string; titles: number }[];
  };
}

/** Text -> HTML text or attribute value. */
export const esc = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] ?? c);

const ATHENS = "Europe/Athens";
const day = new Intl.DateTimeFormat("en-GB", {
  timeZone: ATHENS,
  weekday: "short",
  day: "numeric",
  month: "short",
});
const time = new Intl.DateTimeFormat("en-GB", {
  timeZone: ATHENS,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export const athensDay = (iso: string) => day.format(new Date(iso));
export const athensTime = (iso: string) => time.format(new Date(iso));

/** A share as whole percents, capped: "<1%" below one, ">99%" from 99.5 (Math.round would show 100%). */
export const pct = (p: number) => (p > 0 && p < 0.005 ? "<1%" : p >= 0.995 && p < 1 ? ">99%" : `${Math.round(p * 100)}%`);

/** Both sides of a pair as whole percents. The away side is 100 minus the home figure, so the two total 100. */
export function pctPair(p: number): [string, string] {
  const home = pct(p);
  return [home, /^\d+%$/.test(home) ? `${100 - Number.parseInt(home, 10)}%` : pct(1 - p)];
}

/** The favourite and its win chance, as the model called it. */
export function call(g: Game): { team: Team; p: number } {
  return g.p_home >= 0.5 ? { team: g.home, p: g.p_home } : { team: g.away, p: 1 - g.p_home };
}

export const signed = (x: number, digits = 1) =>
  `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(digits)}`;

/** A measure's value as a table cell: "-" without a value, a sign where the measure has one. */
export function text(m: { kind: string; digits: number; signed?: boolean }, v: number | null, total: boolean): string {
  if (v === null || !Number.isFinite(v)) return "-";
  const digits = m.kind === "count" && total ? 0 : m.digits;
  const body = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (v < 0 && Number(Math.abs(v).toFixed(digits)) !== 0) return `−${body}`;
  return m.signed && v > 0 ? `+${body}` : body;
}

const seasonLabel = (s: number) => `${s}-${String((s + 1) % 100).padStart(2, "0")}`;

