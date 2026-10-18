// Compare: up to five players (a season each, or whole careers) as a head-to-head grid. Each
// measure is one row; its leader among the compared gets the orange dot. Pure functions shared by
// the build and the browser.

import { careerAchievements, formatRate, REACHED_LABEL, seasonAchievement, seasonTitles, type AchEntry, type StatTitle } from "./achievement";
import { betterOf } from "./better";
import { esc } from "./format";
import { dataTip, tip } from "./tip";
import { jerseySvg } from "./jersey";
import { seasonLabel } from "./leaders";
import { BY_KEY, playerHref, rated, type Measure } from "./players";

export type Scope = "season" | "career";
export type CRate = "game" | "36" | "total";
type Totals = Record<string, number>;

export const MAX = 5;
export const RATES: { key: CRate; label: string }[] = [
  { key: "game", label: "Per game" },
  { key: "36", label: "Per 36" },
  { key: "total", label: "Totals" },
];

/** What Compare fetches per player (data/cards/{slug}.json). */
export interface Card {
  slug: string;
  name: string;
  fields: string[];
  seasons: { season: number; team: string; teams: string[]; dorsal: string; totals: number[] }[];
  career: { team: string; dorsal: string; first: number; last: number; totals: number[] };
  achievements?: AchEntry[] | null; // null: achievements.json not exported yet
  statTitles?: StatTitle[] | null; // null: achievements.json not exported yet
}

export interface Pick {
  slug: string;
  season: number; // 0 = career, or when the scope is career
}

export interface Col {
  card: Card;
  season: number; // 0: career
  team: string;
  dorsal: string;
  t: Totals;
}

export function column(card: Card, scope: Scope, season: number): Col {
  const totalsOf = (values: number[]) => Object.fromEntries(card.fields.map((f, i) => [f, values[i]]));
  if (scope === "career") return { card, season: 0, team: card.career.team, dorsal: card.career.dorsal, t: totalsOf(card.career.totals) };
  const s = card.seasons.find((x) => x.season === season) ?? card.seasons[card.seasons.length - 1];
  return { card, season: s.season, team: s.team, dorsal: s.dorsal, t: totalsOf(s.totals) };
}

const own = (key: string, head: string, name: string, about: string, value: (t: Totals) => number | null, extra: Partial<Measure> = {}): Measure => ({
  key,
  head,
  name,
  about,
  kind: "count",
  digits: 1,
  value,
  ...extra,
});

const EXTRA: Record<string, Measure> = {
  gs: { key: "gs", head: "GS", name: "Games started", about: "Games started", kind: "fixed", digits: 0, value: (t) => t.gs },
  oreb: own("oreb", "OREB", "Offensive rebounds", "Offensive rebounds", (t) => t.oreb),
  dreb: own("dreb", "DREB", "Defensive rebounds", "Defensive rebounds", (t) => t.dreb),
  ast_tov: own("ast_tov", "AST/TO", "Assists per turnover", "Assists per turnover", (t) => (t.tov ? t.ast / t.tov : null), {
    kind: "fixed",
    digits: 2,
  }),
};
const measure = (key: string) => EXTRA[key] ?? BY_KEY[key];

export const GROUPS: { name: string; keys: string[] }[] = [
  { name: "Playing time", keys: ["gp", "gs", "min"] },
  { name: "Scoring", keys: ["pts", "ts", "efg", "fg2_pct", "fg3_pct", "fg3a", "ft_pct", "fta"] },
  { name: "Playmaking", keys: ["ast", "tov", "ast_tov", "usg"] },
  { name: "Rebounding", keys: ["reb", "oreb", "dreb"] },
  { name: "Defense", keys: ["stl", "blk"] },
  { name: "Overall", keys: ["pir", "pm"] },
];

function value(m: Measure, t: Totals, rate: CRate): number | null {
  if (rate === "total") return m.value(t);
  return rated(m, t, rate);
}

function text(m: Measure, v: number | null, rate: CRate): string {
  if (v === null || !Number.isFinite(v)) return "–";
  const digits = m.kind === "count" && rate === "total" ? 0 : m.digits;
  const body = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (v < 0 && Number(Math.abs(v).toFixed(digits)) !== 0) return `−${body}`;
  return m.signed && v > 0 ? `+${body}` : body;
}

const ordinal = (n: number) => `${n}${["th", "st", "nd", "rd"][n % 100 > 10 && n % 100 < 14 ? 0 : n % 10 < 4 ? n % 10 : 0]}`;

export interface Cell {
  text: string;
  place: number; // 0: not placed (no value, under the floor, or a single player)
  lead: boolean;
  floor: boolean;
}

export interface Row {
  key: string;
  head: string;
  name: string;
  about: string;
  cells: Cell[];
}

export interface Grid {
  groups: { name: string; rows: Row[] }[];
  led: number[]; // rows each column leads
  rows: number; // rows with a leader
}

export function grid(cols: Col[], rate: CRate): Grid {
  const led = cols.map(() => 0);
  let decided = 0;
  const groups = GROUPS.map((g) => ({
    name: g.name,
    rows: g.keys.map((key) => {
      const m = measure(key);
      const vals = cols.map((c) => value(m, c.t, rate));
      const floors = cols.map((c, i) => vals[i] === null || (m.qualifies ? !m.qualifies(c.t) : false));
      const sign = betterOf(key) === "lower" ? -1 : 1;
      const placed = vals.map((v, i) => (floors[i] ? null : sign * (v as number)));
      const field = placed.filter((v): v is number => v !== null);
      const cells = cols.map((_, i) => {
        const v = placed[i];
        const place = v === null || field.length < 2 ? 0 : 1 + field.filter((x) => x > v).length;
        return { text: text(m, vals[i], rate), place, lead: place === 1, floor: floors[i] };
      });
      if (cells.some((c) => c.lead)) decided++;
      cells.forEach((c, i) => c.lead && led[i]++);
      return { key, head: m.head, name: m.name, about: m.about, cells };
    }),
  }));
  return { groups, led, rows: decided };
}

const when = (c: Col) =>
  c.season
    ? seasonLabel(c.season)
    : c.card.career.first === c.card.career.last
      ? seasonLabel(c.card.career.first)
      : `${seasonLabel(c.card.career.first)} to ${seasonLabel(c.card.career.last)}`;

/** The column heads: shirt, name, club and season (a select in the season scope), remove. */
export function headHtml(cols: Col[], scope: Scope, base: string, xIcon: string): string {
  const heads = cols.map((c, i) => {
    const pick =
      scope === "season" && c.card.seasons.length > 1
        ? `<span class="select mini"><select data-col="${i}" aria-label="Season for ${esc(c.card.name)}">${[...c.card.seasons]
            .reverse()
            .map((s) => `<option value="${s.season}"${s.season === c.season ? " selected" : ""}>${seasonLabel(s.season)} · ${esc(s.team)}</option>`)
            .join("")}</select></span>`
        : `<span class="when">${when(c)}</span>`;
    return (
      `<th scope="col" class="card">` +
      `<button type="button" class="drop" data-drop="${i}" aria-label="Remove ${esc(c.card.name)}">${xIcon}</button>` +
      jerseySvg({ code: c.team, name: c.card.name, number: c.dorsal, size: 64 }) +
      `<a class="nm" href="${playerHref(base, c.card.slug)}">${esc(c.card.name)}</a>` +
      `<span class="club">${esc(c.team)}${scope === "career" ? " · career" : ""}</span>` +
      pick +
      `</th>`
    );
  });
  return `<tr><td class="corner"></td>${heads.join("")}</tr>`;
}

export function bodyHtml(g: Grid, cols: Col[]): string {
  const n = cols.length;
  const tally =
    n > 1
      ? `<tbody class="tally"><tr><th scope="row">Rows led<small>of ${g.rows}</small></th>${g.led
          .map((k) => {
            const top = k > 0 && k === Math.max(...g.led);
            return `<td class="num${top ? " lead" : ""}"><span class="cell"><span class="v">${top ? `<i class="lead-dot" aria-hidden="true"></i>` : ""}${k}</span><small></small></span></td>`;
          })
          .join("")}</tr></tbody>`
      : "";
  const groups = g.groups
    .map(
      (grp) =>
        `<tbody><tr class="grp"><th scope="colgroup" colspan="${n + 1}">${grp.name}</th></tr>` +
        grp.rows
          .map(
            (r) =>
              `<tr><th scope="row"><span${dataTip(tip`<b>${r.name}</b> ${r.about}`)} tabindex="0">${r.head}</span></th>` +
              r.cells
                .map((c) => {
                  const cls = ["num", c.lead ? "lead" : "", c.floor ? "muted" : ""].filter(Boolean).join(" ");
                  // Fixed slots (value with its dot, place) so figures line up down each column.
                  const dot = c.lead ? `<i class="lead-dot" aria-hidden="true"></i>` : "";
                  const place = `<small>${c.lead ? "<span class=\"sr-only\">leads, </span>" : ""}${c.place ? ordinal(c.place) : ""}</small>`;
                  return `<td class="${cls}"><span class="cell"><span class="v">${dot}${c.text}</span>${place}</span></td>`;
                })
                .join("") +
              `</tr>`,
          )
          .join("") +
        `</tbody>`,
    )
    .join("");
  return tally + groups + achievementBody(cols);
}

/** The Accolades group: the furthest stage and stat titles per season, or the career rows (season 0). */
function achievementBody(cols: Col[]): string {
  if (!cols.length || cols.every((c) => !c.card.achievements)) return "";
  const n = cols.length;
  const row = (head: string, about: string, cells: string[]) =>
    `<tr><th scope="row"><span${dataTip(tip`<b>${head}</b> ${about}`)} tabindex="0">${head}</span></th>` +
    cells.map((t) => `<td class="num"><span class="cell"><span class="v">${t}</span></span></td>`).join("") +
    `</tr>`;
  const career = cols[0].season === 0;
  const rows = cols.map((c) => careerAchievements(c.card.achievements ?? [], c.card.statTitles ?? []));
  const body = career
    ? [
        row("EuroLeague titles", "Seasons his club won the EuroLeague while he played for it.", rows.map((r) => String(r.titles))),
        row("Final appearances", "Seasons his club reached the final, lost or won, while he played for it.", rows.map((r) => String(r.finals))),
        row("Final Fours", "Seasons he reached the Final Four: a semifinal, the third-place game or the final.", rows.map((r) => String(r.finalFours))),
        row("Final Four rate", "Final Fours as a share of his seasons.", rows.map((r) => formatRate(r.finalFourRate))),
        row("Playoffs", "Seasons he reached the playoffs. A Final Four season counts too.", rows.map((r) => String(r.playoffs))),
        row("Playoff rate", "Playoff seasons as a share of his seasons.", rows.map((r) => formatRate(r.playoffRate))),
        row(
          "Stat titles",
          "Seasons he led the EuroLeague in points, rebounds, assists, steals, blocks or PIR per game, among qualified players.",
          rows.map((r) => String(r.statTitles)),
        ),
        row("EuroLeague seasons", "Seasons with at least one game.", rows.map((r) => String(r.seasons))),
        row("Clubs", "EuroLeague clubs he played a game for.", rows.map((r) => String(r.clubs))),
        row("Games played", "EuroLeague games in his career.", cols.map((c) => String(c.t.gp))),
      ]
    : [
        row(
          "Furthest stage",
          "The furthest stage his club reached that season, if he played at least one game for the club.",
          cols.map((c) => {
            const s = seasonAchievement(c.card.achievements ?? [], c.season);
            if (!s) return "–";
            const label = esc(REACHED_LABEL[s.reached]);
            return s.clubs > 1 ? `${label}<small class="club"> with ${esc(s.club)}</small>` : label;
          }),
        ),
        row(
          "Stat titles",
          "The stats he led the EuroLeague in that season, per game, among qualified players.",
          cols.map((c) => {
            const titles = seasonTitles(c.card.statTitles ?? [], c.season);
            return titles.length ? esc(titles.join(", ")) : "–";
          }),
        ),
      ];
  return (
    `<tbody class="ach"><tr class="grp"><th scope="colgroup" colspan="${n + 1}">Accolades ` +
    `<small>Since 2007-08: careers that started earlier are incomplete.</small></th></tr>${body.join("")}</tbody>`
  );
}

export function toQuery(picks: Pick[], scope: Scope, rate: CRate): string {
  const q = new URLSearchParams();
  if (scope !== "season") q.set("scope", scope);
  if (rate !== "game") q.set("rate", rate);
  if (picks.length) q.set("p", picks.map((p) => (scope === "season" && p.season ? `${p.slug}:${p.season}` : p.slug)).join(","));
  const s = q.toString().replace(/%2C/g, ",").replace(/%3A/g, ":");
  return s ? `?${s}` : "";
}

export function fromQuery(search: string): { picks: Pick[]; scope: Scope; rate: CRate } {
  const q = new URLSearchParams(search);
  const scope: Scope = q.get("scope") === "career" ? "career" : "season";
  const rate = (RATES.some((r) => r.key === q.get("rate")) ? q.get("rate") : "game") as CRate;
  const seen = new Set<string>();
  const picks = (q.get("p") ?? "")
    .split(",")
    .map((part) => {
      const [slug, season] = part.trim().toLowerCase().split(":");
      return { slug, season: Number(season) || 0 };
    })
    .filter((p) => /^[a-z0-9-]+$/.test(p.slug) && !seen.has(`${p.slug}:${p.season}`) && seen.add(`${p.slug}:${p.season}`))
    .slice(0, MAX);
  return { picks, scope, rate };
}
