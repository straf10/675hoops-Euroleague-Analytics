// Game preview (1200 x 630): one logged game before tip-off. Win chance and the Elo margin only.
// Layout follows the approved demo (game-preview.html), without its interval line: the site does
// not publish a margin interval, so none is drawn.

import { athensDay, athensTime, signed } from "../format";
import { INK, INK_SOFT, MUTED, RULE, canvas, footer, line, logo, pcts, split, text } from "./draw";
import type { Side } from "./round";

interface GameCardInput {
  home: Side;
  away: Side;
  tipoff_utc: string;
  round: number;
  p_home: number;
  exp_margin: number;
  /** "2026-10-21 08:04" (UTC) when the forecast was logged. */
  loggedAt: string;
  /** The model's name as the forecast page gives it. */
  model: string;
}

const W = 1200;
const H = 630;
const X0 = 64;
const X1 = 1136;

export function gameSvg(g: GameCardInput): string {
  const b: string[] = [];
  b.push(logo(X0, 34));
  b.push(text(X1, 60, `Logged ${g.loggedAt} UTC, before tip-off`, { size: 20, fill: MUTED, anchor: "end" }));

  b.push(text(X0, 214, g.away.code, { size: 88, weight: 620, track: -0.03 }));
  b.push(text(X0, 252, g.away.name, { size: 26, fill: INK_SOFT }));
  b.push(text(X0, 282, "Away", { size: 20, fill: MUTED }));
  b.push(text(X1, 214, g.home.code, { size: 88, weight: 620, track: -0.03, anchor: "end" }));
  b.push(text(X1, 252, g.home.name, { size: 26, fill: INK_SOFT, anchor: "end" }));
  b.push(text(X1, 282, "Home", { size: 20, fill: MUTED, anchor: "end" }));

  const when = `${athensDay(g.tipoff_utc)}, ${athensTime(g.tipoff_utc)} Athens time`;
  b.push(text(600, 214, when, { size: 22, fill: INK_SOFT, anchor: "middle" }));
  b.push(text(600, 244, `EuroLeague round ${g.round}`, { size: 20, fill: MUTED, anchor: "middle" }));

  // The split bar: away gray on the left, home orange on the right, at the home win chance.
  b.push(split(X0, 312, X1 - X0, 34, g.p_home, 3, 6));
  const [awayPct, homePct] = pcts(g.p_home);
  const homeFav = g.p_home >= 0.5;
  b.push(text(X0, 396, `${awayPct}%`, { size: 48, weight: homeFav ? 400 : 620, fill: homeFav ? MUTED : INK }));
  b.push(text(X0, 422, "win chance", { size: 20, fill: MUTED }));
  b.push(text(X1, 396, `${homePct}%`, { size: 48, weight: homeFav ? 620 : 400, fill: homeFav ? INK : MUTED, anchor: "end" }));
  b.push(text(X1, 422, "win chance", { size: 20, fill: MUTED, anchor: "end" }));

  b.push(line(X0, 446, X1, 446, RULE, 1.5));
  b.push(text(X0, 476, `Elo margin, ${g.home.code}`, { size: 20, fill: MUTED }));
  b.push(text(X0, 526, signed(g.exp_margin), { size: 52, weight: 620 }));
  b.push(text(X0, 556, "Expected margin, home side", { size: 20, fill: INK_SOFT }));
  b.push(text(420, 476, "Model", { size: 20, fill: MUTED }));
  b.push(text(420, 526, g.model, { size: 36, weight: 620 }));
  b.push(text(420, 556, "Pre-registered, scored after the game", { size: 20, fill: INK_SOFT }));
  b.push(footer(X0, X1, 614));
  return canvas(W, H, b.join(""));
}
