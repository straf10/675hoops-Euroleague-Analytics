// Round cards (1080 x 1350): the preview of the next round with logged forecasts, and the recap of
// each finished round. Layout follows the approved demo (round-card.html, round-card-recap.html).

import { athensTime, signed } from "../format";
import {
  AXIS,
  BLUE,
  GRAY,
  INK,
  INK_SOFT,
  MUTED,
  ORANGE,
  RULE,
  RULE_STRONG,
  canvas,
  footer,
  line,
  logo,
  pcts,
  rect,
  split,
  text,
  width,
} from "./draw";

export interface Side {
  code: string;
  name: string;
}

/** One logged game of the next round (site.json competitions[].upcoming). */
export interface PreviewGame {
  tipoff_utc: string;
  home: Side;
  away: Side;
  p_home: number;
  exp_margin: number;
}

/** One scored game of a finished round (site.json competitions[].forecasts.games, published model). */
export interface RecapGame {
  tipoff_utc: string;
  home: Side;
  away: Side;
  home_score: number;
  away_score: number;
  p_home: number;
  /** Whether the call was right; null where p_home is 0.5. */
  right: boolean | null;
}

/** The published model's record over the season to date (site.json forecasts.season). */
export interface SeasonLine {
  right: number;
  picks: number;
  brier: number | null;
  log_loss: number | null;
}

/** The home-win baseline over the season to date (site.json scorecard.b0). */
export interface Baseline {
  brier: number | null;
  log_loss: number | null;
}

const X0 = 72;
const X1 = 1008;
const W = 1080;
const H = 1350;

/** Brier score: the mean squared gap between the home-win chance and the result. */
export function brier(games: { p: number; home_won: boolean }[]): number {
  return games.reduce((s, g) => s + (g.p - (g.home_won ? 1 : 0)) ** 2, 0) / games.length;
}

/** Log loss: the mean negative log of the probability given to what happened. */
export function logLoss(games: { p: number; home_won: boolean }[]): number {
  return -games.reduce((s, g) => s + Math.log(g.home_won ? g.p : 1 - g.p), 0) / games.length;
}

const sign3 = (x: number | null) => (x === null ? "–" : x.toFixed(3));

/** Tip-off clock in Athens, as the site shows it. */
const clock = (iso: string) => athensTime(iso);

export function previewSvg(round: number, games: PreviewGame[], loggedAt: string): string {
  const b: string[] = [];
  b.push(logo(X0, 40));
  b.push(text(X1, 66, "EuroLeague 2026-27", { size: 22, fill: MUTED, anchor: "end" }));
  b.push(text(X0, 196, `Round ${round}`, { size: 104, weight: 620, track: -0.035 }));
  b.push(text(X0, 246, `Home win chance and expected margin, all ${games.length} games.`, { size: 26, fill: INK_SOFT }));
  b.push(text(X0, 286, `Logged ${loggedAt} UTC, before tip-off.`, { size: 20, fill: MUTED }));
  b.push(line(X0, 318, X1, 318, RULE_STRONG, 1.5));
  legend(b, 352);

  const head = 412;
  b.push(text(X0, head, "Tip-off", { size: 18, fill: MUTED }));
  b.push(text(150, head, "Away", { size: 18, fill: MUTED }));
  b.push(text(477, head, "Home win chance", { size: 18, fill: MUTED, anchor: "middle" }));
  b.push(text(698, head, "Home", { size: 18, fill: MUTED }));
  b.push(text(X1, head, "Exp. margin", { size: 18, fill: MUTED, anchor: "end" }));

  const top0 = 438;
  const pitch = Math.min(82, Math.floor((1110 - top0) / Math.max(games.length, 1)));
  games.forEach((g, i) => {
    const top = top0 + i * pitch;
    const cy = top + 30;
    const [awayPct, homePct] = pcts(g.p_home);
    const homeFav = g.p_home >= 0.5;
    b.push(text(X0, cy + 8, clock(g.tipoff_utc), { size: 24, fill: INK_SOFT }));
    b.push(text(150, cy + 8, g.away.code, { size: 26, weight: 600 }));
    b.push(text(262, cy + 8, `${awayPct}%`, { size: 24, weight: homeFav ? 400 : 600, fill: homeFav ? MUTED : INK, anchor: "end" }));
    b.push(split(282, cy - 7, 330, 14, g.p_home));
    b.push(text(632, cy + 8, `${homePct}%`, { size: 24, weight: homeFav ? 600 : 400, fill: homeFav ? INK : MUTED }));
    b.push(text(698, cy + 8, g.home.code, { size: 26, weight: 600 }));
    b.push(text(X1, cy + 8, signed(g.exp_margin), { size: 26, weight: 600, anchor: "end" }));
    if (i < games.length - 1) b.push(line(X0, top + pitch - 8, X1, top + pitch - 8, RULE, 1));
  });
  b.push(footer(X0, X1, 1326));
  return canvas(W, H, b.join(""));
}

function legend(b: string[], y: number) {
  b.push(rect(X0, y, 16, 16, GRAY, 4));
  b.push(text(X0 + 24, y + 14, "Away win", { size: 20, fill: INK_SOFT }));
  b.push(rect(X0 + 152, y, 16, 16, ORANGE, 4));
  b.push(text(X0 + 176, y + 14, "Home win", { size: 20, fill: INK_SOFT }));
  b.push(line(X0 + 300, y - 4, X0 + 300, y + 20, AXIS, 1.5));
  b.push(text(X0 + 314, y + 14, "50%", { size: 20, fill: INK_SOFT }));
}

export interface RecapInput {
  round: number;
  games: RecapGame[];
  /** The published model's season to date, and the home-win baseline's. */
  season: SeasonLine;
  baseline: Baseline;
  seasonName: string;
}

export function recapSvg(r: RecapInput): string {
  const b: string[] = [];
  const games = r.games;
  const n = games.length;
  const hits = games.filter((g) => g.right === true).length;
  const scored = games.map((g) => ({ p: g.p_home, home_won: g.home_score > g.away_score }));
  const roundBrier = brier(scored);
  const roundLl = logLoss(scored);

  b.push(logo(X0, 40));
  b.push(text(X1, 66, r.seasonName, { size: 22, fill: MUTED, anchor: "end" }));
  b.push(text(X0, 196, `Round ${r.round}`, { size: 104, weight: 620, track: -0.035 }));
  b.push(text(X0, 246, "Result and scoring, game by game.", { size: 26, fill: INK_SOFT }));
  b.push(text(X0, 286, "Every call logged before tip-off. Scored after the final buzzer.", { size: 20, fill: MUTED }));
  b.push(line(X0, 318, X1, 318, RULE_STRONG, 1.5));
  legend(b, 352);

  const head = 412;
  b.push(text(X0, head, "Tip-off", { size: 18, fill: MUTED }));
  b.push(text(150, head, "Away", { size: 18, fill: MUTED }));
  b.push(text(477, head, "Home win chance", { size: 18, fill: MUTED, anchor: "middle" }));
  b.push(text(698, head, "Home", { size: 18, fill: MUTED }));
  b.push(text(776, head, "Final", { size: 18, fill: MUTED }));
  b.push(text(X1, head, "Call", { size: 18, fill: MUTED, anchor: "end" }));

  const top0 = 438;
  const pitch = Math.min(66, Math.floor((1098 - top0) / Math.max(n, 1)));
  games.forEach((g, i) => {
    const top = top0 + i * pitch;
    const cy = top + 26;
    const [awayPct, homePct] = pcts(g.p_home);
    const homeFav = g.p_home >= 0.5;
    const awayWon = g.away_score > g.home_score;
    b.push(text(X0, cy + 8, clock(g.tipoff_utc), { size: 24, fill: INK_SOFT }));
    b.push(text(150, cy + 8, g.away.code, { size: 26, weight: 600 }));
    b.push(text(262, cy + 8, `${awayPct}%`, { size: 24, weight: homeFav ? 400 : 600, fill: homeFav ? MUTED : INK, anchor: "end" }));
    b.push(split(282, cy - 7, 330, 14, g.p_home));
    b.push(text(632, cy + 8, `${homePct}%`, { size: 24, weight: homeFav ? 600 : 400, fill: homeFav ? INK : MUTED }));
    b.push(text(698, cy + 8, g.home.code, { size: 26, weight: 600 }));
    // Final score, away first; the winner in ink.
    const as = String(g.away_score);
    const hs = String(g.home_score);
    const dash = " – ";
    let x = 776;
    b.push(text(x, cy + 8, as, { size: 26, weight: awayWon ? 600 : 400, fill: awayWon ? INK : MUTED }));
    x += width(as, 26);
    b.push(text(x, cy + 8, dash, { size: 26, fill: MUTED }));
    x += width(dash, 26);
    b.push(text(x, cy + 8, hs, { size: 26, weight: awayWon ? 400 : 600, fill: awayWon ? MUTED : INK }));
    b.push(chip(X1, cy, g.right));
    if (i < n - 1) b.push(line(X0, top + pitch - 8, X1, top + pitch - 8, RULE, 1));
  });

  const sy = 1118;
  b.push(line(X0, sy, X1, sy, RULE_STRONG, 1.5));
  const cols: [number, string, string, string][] = [
    [X0, "Right this round", `${hits} of ${n}`, `Season to date ${r.season.right} of ${r.season.picks}`],
    [390, "Brier score, lower is better", roundBrier.toFixed(3), `Season to date ${sign3(r.season.brier)}`],
    [708, "Log loss, lower is better", roundLl.toFixed(3), `Season to date ${sign3(r.season.log_loss)}`],
  ];
  for (const [x, label, val, sub] of cols) {
    b.push(text(x, sy + 38, label, { size: 20, fill: MUTED }));
    b.push(text(x, sy + 90, val, { size: 50, weight: 600, track: -0.02 }));
    b.push(text(x, sy + 120, sub, { size: 20, fill: INK_SOFT }));
  }
  b.push(
    text(X0, 1284, `Home-win baseline, season to date: Brier ${sign3(r.baseline.brier)}, log loss ${sign3(r.baseline.log_loss)}.`, {
      size: 22,
      fill: INK_SOFT,
    }),
  );
  b.push(footer(X0, X1, 1334));
  return canvas(W, H, b.join(""));
}

/** The call's outcome as a pill: a check and "Hit" in orange, a cross and "Miss" in blue, or
 * "Not scored" in muted ink where the call was a coin toss. */
function chip(right: number, cy: number, outcome: boolean | null): string {
  if (outcome === null) {
    const label = "Not scored";
    const w = 36 + width(label, 22, 0) + 16;
    return rect(right - w, cy - 17, w, 34, RULE, 17) + text(right - w + 18, cy + 7, label, { size: 22, weight: 500, fill: MUTED });
  }
  const label = outcome ? "Hit" : "Miss";
  const w = 36 + width(label, 22) + 16;
  const x = right - w;
  const wash = outcome ? ORANGE : BLUE;
  const icon = outcome
    ? `<path d="M${x + 14},${cy + 1} L${x + 19},${cy + 6} L${x + 28},${cy - 4}" fill="none" stroke="${ORANGE}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>`
    : `<path d="M${x + 14},${cy - 4} L${x + 24},${cy + 6} M${x + 24},${cy - 4} L${x + 14},${cy + 6}" fill="none" stroke="${BLUE}" stroke-width="2.6" stroke-linecap="round"/>`;
  return rect(x, cy - 17, w, 34, wash, 17, 0.1) + icon + text(x + 36, cy + 7, label, { size: 22, weight: 500, fill: INK });
}
