// The overview's HTML: one card per board, built the same way at build time (the first paint) and in
// the browser after a season or scope switch. The board logic is in leaders.ts.

import { esc } from "./format";
import { jerseySvg } from "./jersey";
import { fullListHref, type Board, type BoardRank } from "./leaders";
import { playerHref } from "./players";

const rankRow = (r: BoardRank, rank: number, base: string) =>
  `<li><span class="rk">${rank}</span><span class="nm"><a href="${playerHref(base, r.e.slug)}">${esc(r.e.name)}</a><small>${esc(r.e.team)}</small></span><span class="val">${r.text}</span></li>`;

/** One board card. `season` is the season on show (0 for a career); the Players link needs it. */
function boardHtml(b: Board, base: string, season: number, career: boolean): string {
  const { leader, next, qualified, spec } = b;
  const href = fullListHref(base, spec, season, career);
  const top = leader
    ? `<div class="lead">` +
      `<a class="shirt-link" href="${playerHref(base, leader.e.slug)}" tabindex="-1" aria-hidden="true">${jerseySvg({ code: leader.e.team, name: leader.e.name, number: leader.e.dorsal, size: 40 })}</a>` +
      `<span class="who"><a href="${playerHref(base, leader.e.slug)}">${esc(leader.e.name)}</a><small>${esc(leader.e.team)}</small></span>` +
      `<span class="val">${leader.text}</span>` +
      `</div>`
    : `<p class="none">No one qualifies yet.</p>`;
  const rest = next.length ? `<ol class="rest">${next.map((r, i) => rankRow(r, i + 2, base)).join("")}</ol>` : "";
  const foot =
    `<footer><span>Of ${qualified} qualified</span>` + (href ? `<a class="ink-link" href="${esc(href)}">Full list →</a>` : "") + `</footer>`;
  return `<section class="board"><h2>${esc(spec.title)}</h2>${top}${rest}${foot}</section>`;
}

export const boardsHtml = (boards: Board[], base: string, season: number, career: boolean): string =>
  boards.map((b) => boardHtml(b, base, season, career)).join("");
