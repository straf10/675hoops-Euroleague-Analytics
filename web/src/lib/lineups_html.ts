// Markup for the Lineups tab: one table of duos or units. Shared by the page and the tab's script.

import { signClass } from "./delta";
import { esc, signed } from "./format";
import type { Line } from "./lineups";

export interface PlayerName {
  name: string;
  slug: string;
}

export const lineupRowsHtml = (list: Line[], names: Record<string, PlayerName>, base: string): string => {
  if (!list.length) return `<tr class="empty"><td colspan="5">No lineups reach the minimum this season.</td></tr>`;
  return list
    .map((l) => {
      const who = l.ids
        .map((id) => {
          const p = names[id];
          return p ? `<a href="${base}/players/${esc(p.slug)}/">${esc(p.name)}</a>` : esc(id);
        })
        .join(", ");
      return `<tr><th scope="row">${who}</th><td class="num">${l.minutes.toFixed(1)}</td><td class="num">${l.poss}</td><td class="num"><span class="${signClass(l.net)}">${signed(l.net)}</span></td><td class="num muted">±${l.ci.toFixed(1)}</td></tr>`;
    })
    .join("");
};
