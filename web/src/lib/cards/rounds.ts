// Which round cards exist and what each shows, from site.json. No drawing or font imports here, so
// this module runs under node --test; the SVG layouts live in round.ts.
//
// A round is open while it has a logged forecast and a game still to finish (site.json
// competitions[].open_rounds). Each open round gets its own card, earliest round first. When every
// game of a round is finished it leaves open_rounds and becomes a recap.

import type { Competition, OpenRound, OpenRoundGame } from "../format";
import type { RecapGame, RecapInput, OpenRoundInput } from "./round";

/** "2026-10-21 08:04": a UTC ISO time as the forecast log writes it, to the minute. */
export const utcStamp = (iso: string) => iso.slice(0, 16).replace("T", " ");

/** How an open round's game reads on its card. A played game shows its final score and its call;
 * an unplayed one shows the forecast only; a forfeit shows no score and no call. */
export type OpenState = "final" | "forfeit" | "to_play";

export function openState(g: OpenRoundGame): OpenState {
  if (g.forfeit) return "forfeit";
  return g.played ? "final" : "to_play";
}

/** The favourite's call on a played game: true when the favourite won, null when the forecast was a
 * coin toss (p_home of exactly 0.5) or the game is not a final. Matches the recap's "Not scored". */
export function openCall(g: OpenRoundGame): boolean | null {
  if (openState(g) !== "final" || g.p_home === 0.5) return null;
  return g.hit;
}

/** The open rounds, earliest round first. Each round's games are in tip-off order and loggedAt is
 * the newest forecast in the round. */
export function openRoundCards(c: Competition): OpenRoundInput[] {
  return c.open_rounds
    .map((r: OpenRound) => {
      const games = [...r.games].sort((a, b) => a.tipoff_utc.localeCompare(b.tipoff_utc));
      const newest = games.map((g) => g.predicted_at_utc).sort().at(-1) ?? games[0]?.tipoff_utc ?? "";
      return {
        round: r.round,
        games,
        loggedAt: utcStamp(newest),
        seasonName: `EuroLeague ${c.season}`,
      };
    })
    .sort((a, b) => a.round - b.round);
}

/** The regular-season rounds that are finished: every scored game of them, none still to play. */
export function recapCards(c: Competition): RecapInput[] {
  const fc = c.forecasts;
  if (!fc) return [];
  const pub = fc.published;
  const open = new Set(c.open_rounds.map((r) => r.round));
  const byRound = new Map<number, RecapGame[]>();
  for (const g of fc.games) {
    const m = g.models[pub ?? ""];
    if (g.phase !== "RS" || !m || open.has(g.round)) continue;
    const list: RecapGame[] = byRound.get(g.round) ?? [];
    list.push({
      tipoff_utc: g.tipoff_utc,
      home: g.home,
      away: g.away,
      home_score: g.home_score,
      away_score: g.away_score,
      p_home: m.p_home,
      right: m.right,
    });
    byRound.set(g.round, list);
  }
  const seasonRow = fc.season.find((s) => s.model === pub);
  const b0 = c.scorecard.b0;
  return [...byRound.entries()]
    .sort(([a], [b]) => a - b)
    .map(([round, games]) => ({
      round,
      games: games.sort((a, b) => a.tipoff_utc.localeCompare(b.tipoff_utc)),
      season: {
        right: seasonRow?.right ?? 0,
        picks: seasonRow?.picks ?? 0,
        brier: seasonRow?.brier ?? null,
        log_loss: seasonRow?.log_loss ?? null,
      },
      baseline: { brier: b0.brier, log_loss: b0.log_loss },
      seasonName: `EuroLeague ${c.season}`,
    }));
}

/** The card names of a competition: one per open round ("round-4"), then one per recap
 * ("round-3-recap"). */
export interface RoundCardName {
  name: string;
  kind: "open" | "recap";
  round: number;
}

export function roundCardNames(c: Competition): RoundCardName[] {
  const out: RoundCardName[] = openRoundCards(c).map((r) => ({ name: `round-${r.round}`, kind: "open", round: r.round }));
  for (const r of recapCards(c)) out.push({ name: `round-${r.round}-recap`, kind: "recap", round: r.round });
  return out;
}
