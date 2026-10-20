// Which cards exist, and what each one shows, from the site data (site.json). The routes in
// src/pages/cards/ and the links on the forecasts page both read from here, so they agree.

import raw from "../../data/site.json";
import type { Competition, SiteData } from "../format";
import { gameSvg } from "./game";
import { openRoundSvg, recapSvg } from "./round";
import { openRoundCards, recapCards, roundCardNames, utcStamp } from "./rounds";

export { openRoundCards, recapCards, roundCardNames, type RoundCardName } from "./rounds";

const data = raw as SiteData;

/** The live EuroLeague section: the only competition the cards cover. */
export function euroleague(): Competition | null {
  return data.competitions.find((c) => c.key === "euroleague") ?? null;
}

/** The model's name on the page, for the game card. The published Elo model is MOV-adjusted. */
function modelName(c: Competition): string {
  const key = c.forecasts?.published ?? "";
  if (key === "elo") return "MOV-adjusted Elo";
  return c.forecasts?.models.find((m) => m.key === key)?.label ?? key;
}

/** Game preview cards: one per logged game still to play. */
export function gameCards(c: Competition) {
  return c.upcoming.map((g) => ({ id: g.game_id, game: g, loggedAt: utcStamp(g.predicted_at_utc) }));
}

/** The SVG of a round card by its route name ("round-4" for an open round, "round-4-recap" for a
 * recap), or null when no such card exists. */
export function roundSvg(name: string): string | null {
  const c = euroleague();
  if (!c) return null;
  const open = openRoundCards(c).find((r) => name === `round-${r.round}`);
  if (open) return openRoundSvg(open);
  const recap = recapCards(c).find((r) => name === `round-${r.round}-recap`);
  return recap ? recapSvg(recap) : null;
}

/** The SVG of one game preview by its game id, or null. */
export function gameSvgFor(id: string): string | null {
  const c = euroleague();
  const card = c && gameCards(c).find((x) => x.id === id);
  if (!c || !card) return null;
  const g = card.game;
  return gameSvg({
    home: g.home,
    away: g.away,
    tipoff_utc: g.tipoff_utc,
    round: g.round,
    p_home: g.p_home,
    exp_margin: g.exp_margin,
    loggedAt: card.loggedAt,
    model: modelName(c),
  });
}
