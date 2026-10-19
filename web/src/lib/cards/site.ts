// Which cards exist, and what each one shows, from the site data (site.json). The routes in
// src/pages/cards/ and the links on the forecasts page both read from here, so they agree.

import raw from "../../data/site.json";
import type { Competition, SiteData } from "../format";
import { gameSvg } from "./game";
import { previewSvg, recapSvg, type PreviewGame, type RecapGame, type RecapInput } from "./round";

const data = raw as SiteData;

/** The live EuroLeague section: the only competition the cards cover. */
export function euroleague(): Competition | null {
  return data.competitions.find((c) => c.key === "euroleague") ?? null;
}

/** "2026-10-21 08:04": a UTC ISO time as the forecast log writes it, to the minute. */
const utcStamp = (iso: string) => iso.slice(0, 16).replace("T", " ");

/** The model's name on the page, for the game card. The published Elo model is MOV-adjusted. */
function modelName(c: Competition): string {
  const key = c.forecasts?.published ?? "";
  if (key === "elo") return "MOV-adjusted Elo";
  return c.forecasts?.models.find((m) => m.key === key)?.label ?? key;
}

interface PreviewCard {
  round: number;
  games: PreviewGame[];
  loggedAt: string;
}

/** The next round with logged forecasts: the lowest round among the games still to play. */
export function previewCard(c: Competition): PreviewCard | null {
  if (!c.upcoming.length) return null;
  const round = Math.min(...c.upcoming.map((g) => g.round));
  const games = c.upcoming.filter((g) => g.round === round).sort((a, b) => a.tipoff_utc.localeCompare(b.tipoff_utc));
  const loggedAt = utcStamp(games.map((g) => g.predicted_at_utc).sort().at(-1)!);
  return { round, games, loggedAt };
}

/** The regular-season rounds that are finished: every scored game of them, none still to play. */
export function recapCards(c: Competition): RecapInput[] {
  const fc = c.forecasts;
  if (!fc) return [];
  const pub = fc.published;
  const open = new Set(c.upcoming.map((g) => g.round));
  const byRound = new Map<number, RecapInput["games"]>();
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

/** Round numbers the site builds a card for: the preview, then each recap. */
export function roundCardNames(c: Competition): { name: string; kind: "preview" | "recap"; round: number }[] {
  const out: { name: string; kind: "preview" | "recap"; round: number }[] = [];
  const preview = previewCard(c);
  if (preview) out.push({ name: `round-${preview.round}`, kind: "preview", round: preview.round });
  for (const r of recapCards(c)) out.push({ name: `round-${r.round}-recap`, kind: "recap", round: r.round });
  return out;
}

/** Game preview cards: one per logged game still to play. */
export function gameCards(c: Competition) {
  return c.upcoming.map((g) => ({ id: g.game_id, game: g, loggedAt: utcStamp(g.predicted_at_utc) }));
}

/** The SVG of a round card by its route name ("round-4", "round-4-recap"), or null. */
export function roundSvg(name: string): string | null {
  const c = euroleague();
  if (!c) return null;
  const preview = previewCard(c);
  if (preview && name === `round-${preview.round}`) return previewSvg(preview.round, preview.games, preview.loggedAt, `EuroLeague ${c.season}`);
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
