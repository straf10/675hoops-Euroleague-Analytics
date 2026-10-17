// Types and formatters of the season forecast record (site.json `forecasts`, built by
// eurohoops.eval.forecasts). Numbers arrive final; this only words them.

import type { Team } from "./format";

export interface FcMetrics {
  n: number;
  picks: number;
  right: number;
  right_pct: number | null;
  log_loss: number | null;
  brier: number | null;
  margin_mae: number | null;
  within: { "5": number | null; "10": number | null };
  totals_mae: number | null;
}

export interface FcGame {
  game_id: string;
  round: number;
  phase: string;
  tipoff_utc: string;
  home: Team;
  away: Team;
  home_score: number;
  away_score: number;
  /** Only the models that logged this game before tip-off. `right` is null where p_home is 0.5. */
  models: Record<string, { p_home: number; exp_margin: number; right: boolean | null }>;
}

/** Hit rate, Brier score and log loss of a set of calls (lower Brier and log loss are better). */
export interface Headline {
  n: number;
  picks: number;
  right: number;
  right_pct: number | null;
  brier: number | null;
  log_loss: number | null;
}

/** One round (or postseason phase) of the published model, and the model's record over every round
 * up to and including this one. */
export interface AccuracyRound {
  phase: string;
  round: number | null;
  games: number;
  model: Headline;
  to_date: { model: Headline; games: number };
}

export interface Forecasts {
  /** Key of the model the page leads with (config.SITE_FORECAST_MODEL). */
  published: string | null;
  accuracy: AccuracyRound[];
  models: { key: string; label: string; first_round: number | null }[];
  season: ({ model: string } & FcMetrics)[];
  shared: { n: number; rows: ({ model: string } & FcMetrics)[] };
  rounds: { phase: string; round: number | null; games: number; models: Record<string, FcMetrics> }[];
  games: FcGame[];
  trend?: Trend[];
  headline: RoundHeadline | null;
  calibration: Calibration;
}

/** The latest completed round (or phase) of the published model, against the home-win baseline. */
export interface RoundHeadline {
  phase: string;
  round: number | null;
  games: number;
  /** Games whose side with P above 0.5 won; a game at exactly 0.5 is not called. */
  called: number;
  brier: number | null;
  baseline_brier: number | null;
  biggest_miss: { winner: Team; loser: Team; p_winner: number };
}

/** One bin of the reliability plot: predicted home-win chance against the observed rate. */
export interface CalibrationBin {
  lo: number;
  hi: number;
  n: number;
  predicted: number;
  observed: number;
  /** Wilson 95% interval of the observed rate. */
  low: number;
  high: number;
}

export interface Calibration {
  games: number;
  bins: CalibrationBin[];
}

const PHASES: Record<string, string> = {
  RS: "Regular season",
  PI: "Play-in",
  PO: "Playoffs",
  FF: "Final Four",
};

export const phaseName = (phase: string) => PHASES[phase] ?? phase;

/** "Round 3" for the regular season, the phase's name for a postseason group. */
export const groupLabel = (phase: string, round: number | null) =>
  phase === "RS" && round !== null ? `Round ${round}` : phaseName(phase);

/** The value of the games filter for a round or phase group. */
export const groupKey = (phase: string, round: number | null) => (round === null ? phase : `${phase}-${round}`);

export const dash = "–";
export const share = (x: number | null) => (x === null ? dash : `${Math.round(x * 100)}%`);
export const rightOf = (m: FcMetrics) =>
  m.picks === 0 ? dash : `${m.right} of ${m.picks} (${share(m.right_pct)})`;

/** "Round 3" -> "R3" for chart ticks; a postseason phase keeps a short name. */
export const shortGroup = (phase: string, round: number | null) =>
  phase === "RS" && round !== null ? `R${round}` : phase;

export const score3 = (x: number | null) => (x === null ? dash : x.toFixed(3));

/** "18 of 28 games, 64%" style: the picks right out of the picks made. */
export const rightText = (m: Pick<Headline, "right" | "picks" | "right_pct">) =>
  m.picks === 0 ? dash : `${m.right} of ${m.picks}`;

export interface ChartSpec {
  w: number;
  h: number;
  /** Plot area edges. */
  l: number;
  r: number;
  t: number;
  b: number;
}

export interface BrierChart {
  spec: ChartSpec;
  ticks: { y: number; label: string }[];
  xs: { x: number; label: string }[];
  /** Path data per series, null when it has fewer than two points. */
  model: { d: string | null; pts: { x: number; y: number; v: number }[] };
  /** End label of the model's line. */
  ends: { y: number; text: string }[];
  coin: number | null;
}

const STEPS = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1];

/** Brier score to date, by round, on a non-zero y scale. */
export function brierChart(acc: AccuracyRound[], spec: ChartSpec): BrierChart {
  const vals = acc.map((a) => a.to_date.model.brier).filter((v): v is number => v !== null);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  const pad = Math.max((hi - lo) * 0.25, 0.01);
  lo -= pad;
  hi += pad;
  const step = STEPS.find((s) => (hi - lo) / s <= 5) ?? 0.1;
  const first = Math.ceil(lo / step - 1e-9) * step;
  const values: number[] = [];
  for (let v = first; v <= hi + 1e-9; v += step) values.push(Number(v.toFixed(4)));
  const digits = step < 0.01 ? 3 : 2;
  const { l, r, t, b, w, h } = spec;
  const y = (v: number) => t + (1 - (v - lo) / (hi - lo)) * (h - t - b);
  const n = acc.length;
  const x = (i: number) => (n === 1 ? (l + w - r) / 2 : l + (i / (n - 1)) * (w - r - l));
  const line = () => {
    const pts = acc
      .map((a, i) => ({ x: x(i), v: a.to_date.model.brier }))
      .filter((p): p is { x: number; v: number } => p.v !== null)
      .map((p) => ({ x: p.x, y: y(p.v), v: p.v }));
    const d = pts.length > 1 ? pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join("") : null;
    return { d, pts };
  };
  const model = line();
  const last = model.pts.at(-1);
  const ends = last ? [{ y: last.y, text: last.v.toFixed(3) }] : [];
  return {
    spec,
    ticks: values.map((v) => ({ y: y(v), label: v.toFixed(digits) })),
    xs: acc.map((a, i) => ({ x: x(i), label: shortGroup(a.phase, a.round) })),
    model,
    ends,
    coin: lo < 0.25 && hi > 0.25 ? y(0.25) : null,
  };
}

/** One game of the running win-chance edge: the model against the baseline, summed so far. */
export interface TrendPoint {
  n: number;
  label: string;
  baseline: number;
}

/** The record's running win-chance edge (eval/forecasts.py ``_trend``). */
export interface Trend {
  n: number;
  label: string;
  logloss: { baseline: number };
}

/** The one-line headline above the latest round: called, Brier against the baseline, the biggest miss. */
export function headlineText(h: RoundHeadline, groupName: string): string {
  const { winner, loser, p_winner } = h.biggest_miss;
  const brier = h.brier === null ? dash : score3(h.brier);
  const base = h.baseline_brier === null ? dash : score3(h.baseline_brier);
  return `${groupName}: ${h.called} of ${h.games} called, Brier ${brier} vs home-win baseline ${base}; biggest miss: ${winner.code} beat ${loser.code} at ${share(p_winner)}.`;
}

export interface CalibrationPoint extends CalibrationBin {
  x: number;
  y: number;
  yLow: number;
  yHigh: number;
}

/** The reliability plot's points: x = predicted, y = observed, on the plot area of `spec`. */
export function calibrationPlot(cal: Calibration, spec: ChartSpec): CalibrationPoint[] {
  const { l, r, t, b, w, h } = spec;
  const pw = w - l - r;
  const ph = h - t - b;
  return cal.bins.map((bin) => ({
    ...bin,
    x: l + bin.predicted * pw,
    y: t + (1 - bin.observed) * ph,
    yLow: t + (1 - bin.high) * ph,
    yHigh: t + (1 - bin.low) * ph,
  }));
}
