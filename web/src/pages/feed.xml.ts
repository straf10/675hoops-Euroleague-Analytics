// RSS 2.0 feed of the EuroLeague predictions: one item per round, listing the headline model's
// calls for that round's games. Read-only, from the built site data. Only calls logged before
// tip-off go in (a late row is shown apart on the site and never counted, so it is not here).
import type { APIRoute } from "astro";
import raw from "../data/site.json";
import type { SiteData, Result, UpcomingGame } from "../lib/format";
import { dayLabel, percent } from "../lib/gametitle";

const athensDay = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Athens" });

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

interface Call {
  round: number;
  predicted_at_utc: string;
  line: string;
}

export const GET: APIRoute = ({ site }) => {
  const origin = (site ?? new URL("https://675hoops.com")).href.replace(/\/$/, "");
  const comp = (raw as SiteData).competitions.find((c) => c.key === "euroleague");
  const calls: Call[] = [];
  for (const g of (comp?.upcoming ?? []) as UpcomingGame[]) {
    const day = dayLabel(athensDay.format(new Date(g.tipoff_utc)));
    calls.push({
      round: g.round,
      predicted_at_utc: g.predicted_at_utc,
      line: `${g.home.name} vs ${g.away.name}, ${day}: ${g.home.name} ${percent(g.p_home)} to win.`,
    });
  }
  for (const r of (comp?.results ?? []) as Result[]) {
    if (r.late) continue;
    const day = dayLabel(athensDay.format(new Date(r.tipoff_utc)));
    const verdict = r.hit ? "called right" : "called wrong";
    calls.push({
      round: r.round,
      predicted_at_utc: r.predicted_at_utc,
      line: `${r.home.name} ${r.home_score}–${r.away_score} ${r.away.name}, ${day}: we gave ${r.home.name} ${percent(r.p_home)}, ${verdict}.`,
    });
  }
  const season = comp?.season ?? "";
  const rounds = [...new Set(calls.map((c) => c.round))].sort((a, b) => b - a);
  const items = rounds.map((round) => {
    const mine = calls.filter((c) => c.round === round);
    const latest = mine.map((c) => c.predicted_at_utc).sort().at(-1) ?? "";
    const list = mine.map((c) => `<li>${esc(c.line)}</li>`).join("");
    return [
      "<item>",
      `<title>${esc(`EuroLeague ${season}, round ${round} predictions`)}</title>`,
      `<link>${esc(`${origin}/`)}</link>`,
      `<guid isPermaLink="false">${esc(`euroleague-${season}-round-${round}`)}</guid>`,
      `<pubDate>${new Date(latest).toUTCString()}</pubDate>`,
      `<description>${esc(`<ul>${list}</ul>`)}</description>`,
      "</item>",
    ].join("");
  });
  const built = new Date((raw as SiteData & { generated_at_utc?: string }).generated_at_utc ?? 0).toUTCString();
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>` +
    `<rss version="2.0"><channel>` +
    `<title>${esc(`6.75 Analytics: EuroLeague ${season} predictions`)}</title>` +
    `<link>${esc(`${origin}/`)}</link>` +
    `<description>${esc("Win predictions for each EuroLeague round, logged before tip-off and never edited.")}</description>` +
    `<language>en</language>` +
    `<lastBuildDate>${built}</lastBuildDate>` +
    items.join("") +
    `</channel></rss>`;
  return new Response(xml, { headers: { "Content-Type": "application/rss+xml; charset=utf-8" } });
};
