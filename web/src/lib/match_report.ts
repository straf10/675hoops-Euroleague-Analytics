// The match report: one JSON per finished game (docs/match_report.md, section 2) and the pure HTML
// renderers that turn it into the dropdown under a row on the home page. Every text value passes
// through esc(); a block whose data is null renders as "". No runtime imports beyond format.ts, so
// Node can run the tests directly.

import { esc } from "./format.ts";

export type Format = "signed1" | "num0" | "num1" | "num2" | "pct0" | "pct1";
/** Which side a higher (or lower) figure is good for; null for a style measure with no better side. */
export type Better = "high" | "low" | null;

export interface ReportTeam {
  code: string;
  name: string;
}

export interface ReportModel {
  available: boolean;
  reason: string | null;
  home_rating: number | null;
  away_rating: number | null;
  hca: number | null;
  neutral: boolean | null;
  diff: number | null;
  margin_scale: number | null;
  p_home: number | null;
  exp_margin: number | null;
  model_version: string | null;
  predicted_at_utc: string | null;
  source: string | null;
}

export interface OtherModel {
  key: string;
  label: string;
  p_home: number | null;
  exp_margin: number | null;
}

export interface FormGame {
  date: string;
  opp: string;
  venue: "H" | "A" | "N";
  for: number;
  against: number;
  won: boolean;
}

export interface MeetingLine {
  date: string;
  season: number;
  home: string;
  away: string;
  home_score: number;
  away_score: number;
}

export interface H2H {
  since: number;
  games: number;
  home_wins: number;
  away_wins: number;
  last: MeetingLine[];
}

export interface StatRow {
  key: string;
  label: string;
  home: number | null;
  away: number | null;
  better: Better;
  format: Format;
}

export interface TeamStats {
  games: { home: number; away: number };
  rows: StatRow[];
}

export interface PlayerLine {
  name: string;
  slug: string | null;
  gp: number;
  min: number | null;
  pts: number | null;
  reb: number | null;
  ast: number | null;
  pir: number | null;
}

export interface Injury {
  player: string;
  status: string;
  return: string | null;
  comment: string | null;
}

export interface Injuries {
  snapshot_utc: string;
  home: Injury[];
  away: Injury[];
}

export interface Rec {
  wins: number;
  losses: number;
}

export interface Coach {
  name: string;
  slug: string | null;
  season: Rec | null;
  career: Rec | null;
}

export interface StyleRow {
  key: string;
  label: string;
  home: number | null;
  away: number | null;
  format: Format;
}

export interface Coaches {
  home: Coach | null;
  away: Coach | null;
  h2h: { games: number; home_wins: number; away_wins: number } | null;
  style: StyleRow[] | null;
}

export interface MatchReport {
  game_id: string;
  competition: string;
  season: number;
  round: number;
  phase: string;
  tipoff_utc: string;
  home: ReportTeam;
  away: ReportTeam;
  result: { home: number; away: number } | null;
  model: ReportModel;
  other_models: OtherModel[];
  form: { home: FormGame[]; away: FormGame[] } | null;
  h2h: H2H | null;
  team_stats: TeamStats | null;
  players: { home: PlayerLine[]; away: PlayerLine[] } | null;
  injuries: Injuries | null;
  coaches: Coaches | null;
}

// ---- Number and date text (en-US digits, the page's one style) ----

const formatters = new Map<number, Intl.NumberFormat>();
const numberFormat = (digits: number): Intl.NumberFormat => {
  let f = formatters.get(digits);
  if (!f) {
    f = new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    formatters.set(digits, f);
  }
  return f;
};

const isNum = (v: number | null | undefined): v is number => v !== null && v !== undefined && Number.isFinite(v);

/** 1612.4 -> "1,612" (digits 0); thousands separators, fixed decimals. */
export function num(v: number | null | undefined, digits = 0): string {
  return isNum(v) ? numberFormat(digits).format(v) : "–";
}

/** Signed for the eye: +114, −2.3 (a true minus), and no sign at zero after rounding. */
export function signedNum(v: number | null | undefined, digits = 0): string {
  if (!isNum(v)) return "–";
  const rounded = Number(v.toFixed(digits));
  const s = numberFormat(digits).format(Math.abs(rounded));
  return rounded > 0 ? `+${s}` : rounded < 0 ? `−${s}` : s;
}

/** A probability as a whole or one-decimal percent: 0.6573 -> "66%", 0.552 -> "55.2%". */
export function pctText(p: number, digits = 0): string {
  return `${numberFormat(digits).format(p * 100)}%`;
}

/** The value of one stat row in its own format; "–" when missing. */
export function formatValue(v: number | null | undefined, f: Format): string {
  if (!isNum(v)) return "–";
  switch (f) {
    case "signed1":
      return signedNum(v, 1);
    case "num0":
      return num(v, 0);
    case "num1":
      return num(v, 1);
    case "num2":
      return num(v, 2);
    case "pct0":
      return pctText(v, 0);
    case "pct1":
      return pctText(v, 1);
  }
}

const dateFmt = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "numeric", month: "short", year: "numeric" });
const stampFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** "2026-04-10" -> "10 Apr 2026". */
export const dateText = (iso: string): string => dateFmt.format(new Date(iso));
/** "2026-10-20T09:30:00Z" -> "20 Oct 2026, 09:30 UTC". */
export const stampText = (iso: string): string => `${stampFmt.format(new Date(iso))} UTC`;

/** "Since 2007" season label: 2007 -> "2007-08". */
const seasonLabel = (s: number): string => `${s}-${String((s + 1) % 100).padStart(2, "0")}`;

// ---- Shared markup ----

const block = (title: string, inner: string): string =>
  `<div class="mr-block"><h5 class="mr-title">${esc(title)}</h5>${inner}</div>`;

/** One line of the model's equation or a plain two-column list: operator, term, value. */
const row = (op: string, term: string, value: string, cls = ""): string =>
  `<li${cls ? ` class="${cls}"` : ""}><span class="op">${esc(op)}</span><span class="term">${esc(term)}</span><span class="v">${esc(value)}</span></li>`;

/** The favourite and its chance, then the expected margin for that side: "PAO 66% · by 4.1". */
function callText(p: number, expMargin: number | null, home: ReportTeam, away: ReportTeam): string {
  const homeFav = p >= 0.5;
  const fav = homeFav ? home : away;
  const favP = homeFav ? p : 1 - p;
  return `${fav.code} ${pctText(favP)}${isNum(expMargin) ? ` · by ${num(Math.abs(expMargin), 1)}` : ""}`;
}

/** Which side the better figure belongs to; null when neither is better or a value is missing. */
function bestSide(better: Better, h: number | null, a: number | null): "home" | "away" | null {
  if (better === null || !isNum(h) || !isNum(a) || h === a) return null;
  const homeWins = better === "high" ? h > a : h < a;
  return homeWins ? "home" : "away";
}

// ---- Blocks: section 1 ("What the model used") ----

/** The model's equation for the game and the other models' views. Shows the reason when no snapshot exists. */
export function renderModel(r: MatchReport): string {
  const m = r.model;
  const { home, away } = r;
  const ready =
    m.available &&
    isNum(m.home_rating) &&
    isNum(m.away_rating) &&
    isNum(m.hca) &&
    isNum(m.diff) &&
    isNum(m.p_home) &&
    isNum(m.exp_margin);

  let body: string;
  if (ready) {
    const p = m.p_home as number;
    const homeCourt = m.neutral ? row("", "Home court", "neutral court") : row("+", "Home court", num(m.hca, 0));
    body = `<ul class="eq">
      ${row("", `${home.code} rating`, num(m.home_rating, 0))}
      ${homeCourt}
      ${row("−", `${away.code} rating`, num(m.away_rating, 0))}
      ${row("=", "Rating gap", signedNum(m.diff, 0), "sum")}
      ${row("→", callText(p, m.exp_margin, home, away), "", "call")}
    </ul>`;
    const notes = [
      isNum(m.margin_scale) ? `Expected margin is the gap divided by ${num(m.margin_scale, 2)}.` : null,
      m.model_version && m.predicted_at_utc
        ? `Logged ${stampText(m.predicted_at_utc)} by model ${m.model_version}.`
        : null,
    ].filter((s): s is string => s !== null);
    body += notes.map((n) => `<p class="mr-note">${esc(n)}</p>`).join("");
  } else {
    body = `<p class="mr-note">${esc(m.reason ?? "The model's inputs were not recorded for this game.")}</p>`;
  }

  const others =
    r.other_models.length > 0
      ? `<div class="mr-others"><p class="mr-sub">Other models</p><ul class="eq">${r.other_models
          .map((o) =>
            row("", o.label, isNum(o.p_home) ? callText(o.p_home, o.exp_margin, home, away) : "–"),
          )
          .join("")}</ul></div>`
      : "";

  return block("Why this pick", body + others);
}

// ---- Blocks: section 2 ("Context the model does not use") ----

/** Two sides of one stat per row, away first (left) and home last (right); the better side in ink 600. */
export function renderTeamStats(r: MatchReport): string {
  const ts = r.team_stats;
  if (!ts) return "";
  const rows = ts.rows
    .map((s) => {
      const best = bestSide(s.better, s.home, s.away);
      return `<tr><td class="num${best === "away" ? " best" : ""}">${esc(formatValue(s.away, s.format))}</td><th scope="row" class="lab">${esc(s.label)}</th><td class="num${best === "home" ? " best" : ""}">${esc(formatValue(s.home, s.format))}</td></tr>`;
    })
    .join("");
  const inner = `<p class="mr-note">Games before tip-off: ${esc(r.away.code)} ${ts.games.away}, ${esc(r.home.code)} ${ts.games.home}.</p>
    <div class="mr-scroll"><table class="mr-table mr-compare">
      <thead><tr><th scope="col" class="num">${esc(r.away.code)}</th><th scope="col" class="lab">Measure</th><th scope="col" class="num">${esc(r.home.code)}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  return block("Team stats", inner);
}

const venueWord = (v: FormGame["venue"]): string => (v === "H" ? "vs" : v === "A" ? "at" : "v");

/** Last five games per side, newest first, as W/L marks with the score in the title. Away column first. */
export function renderForm(r: MatchReport): string {
  const f = r.form;
  if (!f) return "";
  const col = (team: ReportTeam, games: FormGame[]): string => {
    const marks = games
      .map((g) => {
        const res = g.won ? "W" : "L";
        const title = `${dateText(g.date)}: ${g.won ? "won" : "lost"} ${g.for}–${g.against} ${venueWord(g.venue)} ${g.opp}`;
        return `<li class="mark ${g.won ? "won" : "lost"}" title="${esc(title)}"><span class="res">${res}</span><span class="opp">${esc(`${venueWord(g.venue)} ${g.opp}`)}</span><span class="sc">${num(g.for)}–${num(g.against)}</span></li>`;
      })
      .join("");
    return `<div class="mr-col"><h6>${esc(team.code)}</h6>${
      games.length > 0 ? `<ol class="marks">${marks}</ol>` : `<p class="mr-note">No games before tip-off.</p>`
    }</div>`;
  };
  return block("Form, last five games", `<div class="mr-pair">${col(r.away, f.away)}${col(r.home, f.home)}</div>`);
}

/** Head to head since 2007-08: away side first in the summary, then the last meetings newest first. */
export function renderH2h(r: MatchReport): string {
  const h = r.h2h;
  if (!h) return "";
  if (h.games === 0) {
    return block("Head to head", `<p class="mr-note">No EuroLeague meetings since ${seasonLabel(h.since)}.</p>`);
  }
  const summary = `<p class="mr-sum">${esc(r.away.code)} ${h.away_wins} wins, ${esc(r.home.code)} ${h.home_wins} wins in ${h.games} meetings since ${seasonLabel(h.since)}.</p>`;
  const last =
    h.last.length > 0
      ? `<ol class="meetings">${h.last
          .map((m) => {
            // The score reads home first, as the game's score is written; the winner's side is in ink 600.
            const homeWon = m.home_score > m.away_score;
            return `<li><span class="d">${dateText(m.date)}</span><span class="t"><span class="${homeWon ? "win" : "lose"}">${esc(`${m.home} ${num(m.home_score)}`)}</span>–<span class="${homeWon ? "lose" : "win"}">${esc(`${num(m.away_score)} ${m.away}`)}</span></span></li>`;
          })
          .join("")}</ol>`
      : "";
  return block("Head to head", summary + last);
}

const playerCol = (team: ReportTeam, players: PlayerLine[], base: string): string => {
  if (players.length === 0) {
    return `<div class="mr-col"><h6>${esc(team.code)}</h6><p class="mr-note">No players with two games yet.</p></div>`;
  }
  const rows = players
    .map((p) => {
      const name = p.slug ? `<a href="${esc(base)}/players/${esc(p.slug)}/">${esc(p.name)}</a>` : esc(p.name);
      return `<tr><th scope="row">${name}</th><td class="num">${num(p.min, 1)}</td><td class="num">${num(p.pts, 1)}</td><td class="num">${num(p.reb, 1)}</td><td class="num">${num(p.ast, 1)}</td><td class="num">${num(p.pir, 1)}</td></tr>`;
    })
    .join("");
  return `<div class="mr-col"><h6>${esc(team.code)}</h6><div class="mr-scroll"><table class="mr-table">
    <thead><tr><th scope="col">Player</th><th scope="col" class="num">Min</th><th scope="col" class="num">Pts</th><th scope="col" class="num">Reb</th><th scope="col" class="num">Ast</th><th scope="col" class="num">PIR</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div></div>`;
};

/** The top players by minutes on each side, as of tip-off. Away column first. */
export function renderPlayers(r: MatchReport, base = ""): string {
  const p = r.players;
  if (!p) return "";
  return block("Top players", `<div class="mr-pair">${playerCol(r.away, p.away, base)}${playerCol(r.home, p.home, base)}</div>`);
}

/** The latest injury snapshot at or before tip-off. One block per player: name, status line, comment. Away first. */
export function renderInjuries(r: MatchReport): string {
  const inj = r.injuries;
  if (!inj) return "";
  const col = (team: ReportTeam, list: Injury[]): string => {
    const items = list
      .map((i) => {
        const status = [i.status, i.return ? `return ${i.return}` : null].filter(Boolean).join(" · ");
        return `<li><span class="name">${esc(i.player)}</span>${status ? `<span class="status">${esc(status)}</span>` : ""}${
          i.comment ? `<span class="note">${esc(i.comment)}</span>` : ""
        }</li>`;
      })
      .join("");
    return `<div class="mr-col"><h6>${esc(team.code)}</h6>${
      list.length > 0 ? `<ul class="inj">${items}</ul>` : `<p class="mr-note">No injuries recorded.</p>`
    }</div>`;
  };
  const note = `<p class="mr-note">Injury report as of ${esc(stampText(inj.snapshot_utc))}.</p>`;
  return block("Injuries", `${note}<div class="mr-pair">${col(r.away, inj.away)}${col(r.home, inj.home)}</div>`);
}

/** Each side's coach with season and career records, the coaches' head to head (when they have met), and style rows. Away first. */
export function renderCoaches(r: MatchReport, base = ""): string {
  const c = r.coaches;
  if (!c) return "";
  const record = (label: string, rec: Rec | null): string =>
    rec ? `<p class="rec"><span class="mr-muted">${esc(label)}</span> <span class="num">${rec.wins}–${rec.losses}</span></p>` : "";
  const col = (team: ReportTeam, coach: Coach | null): string => {
    if (!coach) return `<div class="mr-col"><h6>${esc(team.code)}</h6><p class="mr-note">Not recorded.</p></div>`;
    const name = coach.slug ? `<a href="${esc(base)}/coaches/${esc(coach.slug)}/">${esc(coach.name)}</a>` : esc(coach.name);
    return `<div class="mr-col"><h6>${esc(team.code)}</h6><p class="coach">${name}</p>${record("This season", coach.season)}${record("Career", coach.career)}</div>`;
  };
  const meet =
    c.h2h && c.h2h.games > 0
      ? `<p class="mr-sum">Coaches met ${c.h2h.games} times: ${esc(c.away?.name ?? r.away.code)} ${c.h2h.away_wins} wins, ${esc(c.home?.name ?? r.home.code)} ${c.h2h.home_wins} wins.</p>`
      : "";
  const style =
    c.style && c.style.length > 0
      ? `<div class="mr-scroll"><table class="mr-table mr-compare">
        <thead><tr><th scope="col" class="num">${esc(r.away.code)}</th><th scope="col" class="lab">Style, this season</th><th scope="col" class="num">${esc(r.home.code)}</th></tr></thead>
        <tbody>${c.style
          .map(
            (s) =>
              `<tr><td class="num">${esc(formatValue(s.away, s.format))}</td><th scope="row" class="lab">${esc(s.label)}</th><td class="num">${esc(formatValue(s.home, s.format))}</td></tr>`,
          )
          .join("")}</tbody>
      </table></div>`
      : "";
  return block("Coaches", `<div class="mr-pair">${col(r.away, c.away)}${col(r.home, c.home)}</div>${meet}${style}`);
}

/** The whole report: the model section, then the context section (only blocks with data). */
export function renderReport(r: MatchReport, base = ""): string {
  const context = [
    renderTeamStats(r),
    renderForm(r),
    renderH2h(r),
    renderPlayers(r, base),
    renderInjuries(r),
    renderCoaches(r, base),
  ].filter((s) => s !== "");
  return `<div class="mr">
    <section class="mr-sec"><h4 class="mr-h">What the model used</h4>${renderModel(r)}</section>
    ${context.length > 0 ? `<section class="mr-sec"><h4 class="mr-h">Context the model does not use</h4>${context.join("")}</section>` : ""}
  </div>`;
}

