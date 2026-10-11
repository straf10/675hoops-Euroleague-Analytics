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

/** One round (or postseason phase) of the published model against the bookmakers, on the games
 * both called, and the same pair over every round up to and including this one. */
export interface AccuracyRound {
  phase: string;
  round: number | null;
  games: number;
  model: Headline;
  market: Headline;
  to_date: { model: Headline; market: Headline; games: number };
}

export interface Forecasts {
  /** Key of the model the page leads with (config.SITE_FORECAST_MODEL). */
  published: string | null;
  /** The bookmakers' closing line scored on every finished game with one; null without odds. */
  market: { label: string; season: Headline } | null;
  accuracy: AccuracyRound[];
  models: { key: string; label: string; first_round: number | null }[];
  season: ({ model: string } & FcMetrics)[];
  shared: { n: number; rows: ({ model: string } & FcMetrics)[] };
  rounds: { phase: string; round: number | null; games: number; models: Record<string, FcMetrics> }[];
  games: FcGame[];
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
  market: { d: string | null; pts: { x: number; y: number; v: number }[] };
  /** End labels, pushed apart so they never overlap. */
  ends: { y: number; text: string; series: "model" | "market" }[];
  coin: number | null;
}

const STEPS = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1];

/** Brier score to date, by round: both series on one shared, non-zero y scale. */
export function brierChart(acc: AccuracyRound[], spec: ChartSpec): BrierChart {
  const vals = acc.flatMap((a) => [a.to_date.model.brier, a.to_date.market.brier]).filter((v): v is number => v !== null);
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
  const line = (pick: "model" | "market") => {
    const pts = acc
      .map((a, i) => ({ x: x(i), v: a.to_date[pick].brier }))
      .filter((p): p is { x: number; v: number } => p.v !== null)
      .map((p) => ({ x: p.x, y: y(p.v), v: p.v }));
    const d = pts.length > 1 ? pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join("") : null;
    return { d, pts };
  };
  const model = line("model");
  const market = line("market");
  const ends = [
    { series: "model" as const, pt: model.pts.at(-1) },
    { series: "market" as const, pt: market.pts.at(-1) },
  ]
    .filter((e): e is { series: "model" | "market"; pt: { x: number; y: number; v: number } } => !!e.pt)
    .map((e) => ({ y: e.pt.y, text: e.pt.v.toFixed(3), series: e.series }))
    .sort((p, q) => p.y - q.y);
  if (ends.length === 2 && ends[1].y - ends[0].y < 15) {
    const mid = (ends[0].y + ends[1].y) / 2;
    ends[0].y = mid - 7.5;
    ends[1].y = mid + 7.5;
  }
  return {
    spec,
    ticks: values.map((v) => ({ y: y(v), label: v.toFixed(digits) })),
    xs: acc.map((a, i) => ({ x: x(i), label: shortGroup(a.phase, a.round) })),
    model,
    market,
    ends,
    coin: lo < 0.25 && hi > 0.25 ? y(0.25) : null,
  };
}
