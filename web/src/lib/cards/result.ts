// Result card (1200 x 630): one played EuroLeague game. The final score, the pre-game Elo forecast
// and whether the favourite won. Same layout grid as the game preview (game.ts).

import type { Result } from "../format";
import { athensDay, signed } from "../format";
import { INK, INK_SOFT, MUTED, RULE, canvas, footer, line, logo, pcts, split, text } from "./draw";

const W = 1200;
const H = 630;
const X0 = 64;
const X1 = 1136;

export function resultSvg(g: Result, model: string): string {
  const b: string[] = [];
  b.push(logo(X0, 34));
  b.push(text(X1, 60, `Final, ${athensDay(g.tipoff_utc)}`, { size: 20, fill: MUTED, anchor: "end" }));

  b.push(text(X0, 214, g.away.code, { size: 88, weight: 620, track: -0.03 }));
  b.push(text(X0, 252, g.away.name, { size: 26, fill: INK_SOFT }));
  b.push(text(X0, 282, "Away", { size: 20, fill: MUTED }));
  b.push(text(X1, 214, g.home.code, { size: 88, weight: 620, track: -0.03, anchor: "end" }));
  b.push(text(X1, 252, g.home.name, { size: 26, fill: INK_SOFT, anchor: "end" }));
  b.push(text(X1, 282, "Home", { size: 20, fill: MUTED, anchor: "end" }));

  b.push(text(600, 214, `${g.away_score}–${g.home_score}`, { size: 88, weight: 620, anchor: "middle" }));
  b.push(text(600, 244, `EuroLeague round ${g.round}`, { size: 20, fill: MUTED, anchor: "middle" }));

  // The split bar: the pre-game home win chance, away gray on the left, home orange on the right.
  b.push(split(X0, 312, X1 - X0, 34, g.p_home, 3, 6));
  const [awayPct, homePct] = pcts(g.p_home);
  const homeFav = g.p_home >= 0.5;
  b.push(text(X0, 396, `${awayPct}%`, { size: 48, weight: homeFav ? 400 : 620, fill: homeFav ? MUTED : INK }));
  b.push(text(X0, 422, "win chance", { size: 20, fill: MUTED }));
  b.push(text(X1, 396, `${homePct}%`, { size: 48, weight: homeFav ? 620 : 400, fill: homeFav ? INK : MUTED, anchor: "end" }));
  b.push(text(X1, 422, "win chance", { size: 20, fill: MUTED, anchor: "end" }));

  b.push(line(X0, 446, X1, 446, RULE, 1.5));
  b.push(text(X0, 476, `Final margin, ${g.home.code}`, { size: 20, fill: MUTED }));
  b.push(text(X0, 526, signed(g.home_score - g.away_score, 0), { size: 52, weight: 620 }));
  b.push(text(X0, 556, `Elo expected margin ${signed(g.exp_margin)}, home side`, { size: 20, fill: INK_SOFT }));

  // A coin toss (p_home of exactly 0.5) has no favourite to score.
  const fav = homeFav ? g.home.code : g.away.code;
  const favPct = homeFav ? homePct : awayPct;
  const verdict = g.p_home === 0.5 ? "Not scored" : g.hit ? "Favourite won" : "Favourite lost";
  b.push(text(420, 476, "Forecast", { size: 20, fill: MUTED }));
  b.push(text(420, 526, verdict, { size: 36, weight: 620 }));
  b.push(text(420, 556, `${fav} at ${favPct}% before tip-off`, { size: 20, fill: INK_SOFT }));

  b.push(text(X1, 476, "Model", { size: 20, fill: MUTED, anchor: "end" }));
  b.push(text(X1, 526, model, { size: 36, weight: 620, anchor: "end" }));
  b.push(text(X1, 556, "Pre-registered, logged before tip-off", { size: 20, fill: INK_SOFT, anchor: "end" }));
  b.push(footer(X0, X1, 614));
  return canvas(W, H, b.join(""));
}
