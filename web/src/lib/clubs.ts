// The teams index table: its head and rows, shared by the build (the open season) and the season
// switch and metric sort in the page's script (the others). Pure, so both draw the same markup.

import { signClass } from "./delta";
import { esc, signed } from "./format";
import { dataTip, tip } from "./tip";
import { columnKeys, metricOf, type Dir, type IndexRow } from "./ranking";
import { elo } from "./strength";

/** The head: rank, club, W–L (not sortable), then one sortable column per metric in columnKeys. */
export const clubHeadHtml = (metric: string, dir: Dir): string => {
  const cols = columnKeys(metric).map((key) => {
    const m = metricOf(key)!;
    const on = key === metric;
    const sort = on ? (dir === "desc" ? "descending" : "ascending") : "none";
    return (
      `<th scope="col" class="num${on ? " on" : ""}" aria-sort="${sort}">` +
      `<button type="button" data-sort="${key}"${dataTip(tip`<b>${m.name}</b><br>${m.about}`)}>${m.head}</button></th>`
    );
  });
  const wl = dataTip(tip`<b>W–L</b><br>Wins and losses`);
  return (
    `<tr><th scope="col" class="num">#</th><th scope="col">Club</th>` +
    `<th scope="col" class="num"><span${wl} tabindex="0">W–L</span></th>${cols.join("")}</tr>`
  );
};

/** One figure as the table shows it: one decimal, Net signed and carrying the Sign Colour Rule class. */
const cell = (key: string, v: number): string => {
  if (!Number.isFinite(v)) return "–";
  if (key === "net") return `<span class="${signClass(v)}">${signed(v)}</span>`;
  if (key === "returning") return `${Math.round(v)}%`;
  if (key.startsWith("sos_")) return elo(v);
  return v.toFixed(1);
};

/** A season's rows in the order given (the caller sorts); links carry the season unless it is the one the page opens on. */
export const clubRowsHtml = (base: string, season: number | undefined, rows: IndexRow[], metric: string): string => {
  const keys = columnKeys(metric);
  return rows
    .map((r, i) => {
      const href = `${base.replace(/\/$/, "")}/teams/${r.code.toLowerCase()}/${season ? `?season=${season}` : ""}`;
      const figures = keys
        .map((key) => `<td class="num${key === metric ? " strong" : ""}">${cell(key, r.f[key])}</td>`)
        .join("");
      return (
        `<tr><td class="num muted">${i + 1}</td><th scope="row"><a href="${href}"><span class="code">${esc(r.code)}</span>${esc(r.name)}</a></th>` +
        `<td class="num">${r.w}–${r.l}</td>${figures}</tr>`
      );
    })
    .join("");
};
