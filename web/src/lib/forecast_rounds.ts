// The round picker of the forecast record: which games each round holds, the default round, the query
// parameter that names a round, and the table row a game prints as. Pure, so the round logic is tested
// without the page. ForecastRecord.astro renders the default round; the round-picker script prints the
// others from per-round files with gameRowHtml, so the two must stay in step.

import { athensDay, esc, pct, signed } from "./format.ts";
import { dash, groupKey, groupLabel, type FcGame } from "./forecasts.ts";

/** One round (or postseason phase) of one model's calls, its games newest first. */
export interface RoundGroup {
  /** The round's value in the picker, the query string and the per-round file: "7" for a regular-season
   *  round, the phase code otherwise ("PO"). */
  id: string;
  label: string;
  phase: string;
  round: number | null;
  games: FcGame[];
}

/** The model the page leads with: `published`, else the first model listed. */
export function leadModel(
  fc: { published: string | null; models: { key: string }[] } | null | undefined,
): string | undefined {
  return fc ? (fc.published ?? fc.models[0]?.key) : undefined;
}

/** The value naming a group: the round number in the regular season, the phase code otherwise. */
export const roundId = (phase: string, round: number | null) => (phase === "RS" && round !== null ? String(round) : phase);

/** The rounds `model` called, the latest first (by the newest tipoff in each). Games it did not call are left out. */
export function roundGroups(games: FcGame[], model: string): RoundGroup[] {
  const groups = new Map<string, RoundGroup>();
  const newest = new Map<string, string>();
  for (const g of games) {
    if (!g.models[model]) continue;
    const id = roundId(g.phase, g.round);
    const group = groups.get(id);
    if (group) group.games.push(g);
    else {
      const round = g.phase === "RS" ? g.round : null;
      groups.set(id, { id, label: groupLabel(g.phase, round), phase: g.phase, round, games: [g] });
    }
    if ((newest.get(id) ?? "") < g.tipoff_utc) newest.set(id, g.tipoff_utc);
  }
  return [...groups.values()].sort((a, b) => (newest.get(b.id) ?? "").localeCompare(newest.get(a.id) ?? ""));
}

/** The query parameter holding one competition's round; each competition on a page has its own. */
export const roundParam = (compKey: string) => `${compKey}-round`;

/** The round the query asks for. A missing or unknown value falls back to the first group (the latest round). */
export function roundFromQuery<T extends { id: string }>(search: string, param: string, groups: T[]): T | null {
  const asked = new URLSearchParams(search).get(param);
  return groups.find((g) => g.id === asked) ?? groups[0] ?? null;
}

/** The search string with `param` set to `id`; the default round removes it. Other parameters are kept. */
export function roundSearch(search: string, param: string, id: string, defaultId: string | null): string {
  const p = new URLSearchParams(search);
  if (id === defaultId) p.delete(param);
  else p.set(param, id);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** The two icons a verdict pill shows; the page passes its SVG markup. */
export interface RowIcons {
  hit: string;
  miss: string;
}

const verdict = (right: boolean | null, icons: RowIcons) => {
  if (right === null) return `<span class="dash">${dash}</span>`;
  return `<span class="pill ${right ? "hit" : "miss"}"><span class="icon">${right ? icons.hit : icons.miss}</span>${right ? "Right" : "Wrong"}</span>`;
};

/** One game as a table row, the markup ForecastGames prints for its rows: the teams, the score, and the
 *  `model` call with its verdict. A game the model did not call shows a dash. */
export function gameRowHtml(g: FcGame, model: string, icons: RowIcons): string {
  const c = g.models[model];
  const homeWon = g.home_score > g.away_score;
  const round = g.phase === "RS" ? g.round : null;
  const call = c ? `${pct(c.p_home)} <span class="mg">${signed(c.exp_margin)}</span>${verdict(c.right, icons)}` : dash;
  return [
    `<tr data-group="${esc(groupKey(g.phase, round))}">`,
    `<td class="date rd">${esc(groupLabel(g.phase, round).replace("Round ", ""))}</td>`,
    `<td class="date">${esc(athensDay(g.tipoff_utc))}</td>`,
    `<td class="team r${homeWon ? " won" : ""}"><span class="name">${esc(g.home.name)}</span><b>${esc(g.home.code)}</b></td>`,
    `<td class="c score"><span${homeWon ? ' class="won"' : ""}>${g.home_score}</span><span class="dash">-</span><span${homeWon ? "" : ' class="won"'}>${g.away_score}</span></td>`,
    `<td class="team${homeWon ? "" : " won"}"><b>${esc(g.away.code)}</b><span class="name">${esc(g.away.name)}</span></td>`,
    `<td class="call">${call}</td>`,
    "</tr>",
  ].join("");
}
