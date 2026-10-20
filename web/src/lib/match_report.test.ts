// Unit tests for the match report renderers, against lib/fixtures/match_report.json.
// Run with `node --test src/lib/match_report.test.ts` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  formatValue,
  num,
  pctText,
  renderCoaches,
  renderForm,
  renderH2h,
  renderInjuries,
  renderModel,
  renderPlayers,
  renderReport,
  renderTeamStats,
  signedNum,
  type MatchReport,
} from "./match_report.ts";

const load = (): MatchReport =>
  JSON.parse(readFileSync(new URL("./fixtures/match_report.json", import.meta.url), "utf8")) as MatchReport;

const TITLES = ["Why this pick", "Team stats", "Form, last five games", "Head to head", "Top players", "Injuries", "Coaches"];

test("every block renders from the fixture, with both sections", () => {
  const html = renderReport(load(), "");
  assert.match(html, /What the model used/);
  assert.match(html, /Context the model does not use/);
  for (const t of TITLES) assert.ok(html.includes(t), `missing block: ${t}`);
});

test("null blocks are omitted, and the context section goes with the last of them", () => {
  const r = load();
  const stripped: MatchReport = {
    ...r,
    team_stats: null,
    form: null,
    h2h: null,
    players: null,
    injuries: null,
    coaches: null,
  };
  const html = renderReport(stripped, "");
  for (const t of TITLES.slice(1)) assert.ok(!html.includes(t), `block should be hidden: ${t}`);
  assert.ok(html.includes("Why this pick"));
  assert.ok(!html.includes("Context the model does not use"));
  assert.equal(renderTeamStats(stripped), "");
  assert.equal(renderForm(stripped), "");
  assert.equal(renderInjuries(stripped), "");
  assert.equal(renderCoaches(stripped, ""), "");
});

test("the model call shows the rating equation, the chance and the margin", () => {
  const html = renderModel(load());
  assert.match(html, />PAO rating</);
  assert.match(html, /1,612/);
  assert.match(html, /Home court/);
  assert.match(html, />90</);
  assert.match(html, /FBT rating/);
  assert.match(html, /1,588/);
  assert.match(html, /\+114/);
  assert.match(html, /PAO 66% · by 4\.1/);
});

test("a game on neutral court says so instead of a home-court figure", () => {
  const r = load();
  const html = renderModel({ ...r, model: { ...r.model, neutral: true, hca: 0 } });
  assert.match(html, /neutral court/);
  assert.ok(!html.includes(">+<"));
});

test("an unavailable model shows its reason and no equation", () => {
  const r = load();
  const html = renderModel({
    ...r,
    model: { ...r.model, available: false, reason: "Inputs were not recorded for this game.", p_home: null, exp_margin: null },
  });
  assert.match(html, /Inputs were not recorded for this game\./);
  assert.ok(!html.includes("Rating gap"));
  assert.ok(html.includes("Why this pick"));
});

test("a model that favours the away side names that side", () => {
  const r = load();
  const html = renderModel({ ...r, model: { ...r.model, p_home: 0.3427, exp_margin: -4.07, diff: -114.4 } });
  assert.match(html, /FBT 66% · by 4\.1/);
  assert.match(html, /−114/);
});

test("numbers format as percent, signed gap and thousands separator", () => {
  assert.equal(pctText(0.6573), "66%");
  assert.equal(pctText(0.552, 1), "55.2%");
  assert.equal(signedNum(114.4, 0), "+114");
  assert.equal(signedNum(-2.34, 1), "−2.3");
  assert.equal(signedNum(0.04, 1), "0.0");
  assert.equal(num(1612.4, 0), "1,612");
  assert.equal(formatValue(6.1, "signed1"), "+6.1");
  assert.equal(formatValue(null, "num1"), "–");
  assert.equal(formatValue(1.05, "num2"), "1.05");
});

test("team stats mark only the better side, by the row's direction", () => {
  const html = renderTeamStats(load());
  // Offensive rating: home 118.2 beats 115.0 (high is better).
  assert.match(html, /<td class="num best">118\.2<\/td>/);
  assert.ok(!/<td class="num best">115\.0<\/td>/.test(html));
  // Defensive rating: 111.6 beats 112.1 (low is better).
  assert.match(html, /<td class="num best">111\.6<\/td>/);
  // Pace has no better side: nothing is marked.
  assert.ok(!/best">71\.2/.test(html) && !/best">69\.8/.test(html));
});

test("form lists newest first with the score in the title", () => {
  const html = renderForm(load());
  const first = html.indexOf("BAR");
  const second = html.indexOf("MAD");
  assert.ok(first > 0 && second > first, "BAR (newest) comes before MAD");
  assert.match(html, /title="16 Oct 2026: won 81–77 at BAR"/);
  assert.match(html, /No games before tip-off\./);
});

test("player names link to the player page when there is a slug", () => {
  const html = renderPlayers(load(), "/base");
  assert.match(html, /<a href="\/base\/players\/kendrick-nunn\/">Kendrick Nunn<\/a>/);
  assert.ok(html.includes("Tomas Satoransky"));
  assert.ok(!html.includes("/players/undefined"));
});

test("injuries show the snapshot date, one block per player, and the empty side says so", () => {
  const html = renderInjuries(load());
  assert.match(html, /Injury report as of 20 Oct 2026, 09:30 UTC/);
  assert.match(
    html,
    /<li><span class="name">Juancho Hernangomez<\/span><span class="status">Out · return Round 9<\/span><span class="note">Ankle<\/span><\/li>/,
  );
  assert.ok(!html.includes("<table"), "injuries are not a table");
  assert.match(html, /No injuries recorded\./);
});

// ---- Orientation: away first (left), home last (right), in every two-sided block ----

test("two-sided blocks put the away side on the left", () => {
  const r = load();
  // Team stats: the away value, then the label, then the home value. Offensive rating: home 118.2 is the better one.
  assert.match(
    renderTeamStats(r),
    /<td class="num">115\.0<\/td><th scope="row" class="lab">Offensive rating<\/th><td class="num best">118\.2<\/td>/,
  );
  // Form: the away column (no games in the fixture) comes before the home column.
  const form = renderForm(r);
  assert.ok(form.indexOf("No games before tip-off.") < form.indexOf("BAR"));
  // Injuries: away (no injuries) before home (Juancho).
  const inj = renderInjuries(r);
  assert.ok(inj.indexOf("No injuries recorded.") < inj.indexOf("Juancho"));
  // Players: away (Nick Calathes) before home (Kendrick Nunn).
  const players = renderPlayers(r, "");
  assert.ok(players.indexOf("Nick Calathes") < players.indexOf("Kendrick Nunn"));
  // Coaches: the away coach (Jasikevicius) before the home coach (Ataman).
  const coaches = renderCoaches(r, "");
  assert.ok(coaches.indexOf("Sarunas Jasikevicius") < coaches.indexOf("Ergin Ataman"));
  // Summary lines name the away side first too.
  assert.match(renderH2h(r), /FBT 14 wins, PAO 17 wins in 31 meetings since 2007-08\./);
  assert.match(renderCoaches(r, ""), /Coaches met 14 times: Sarunas Jasikevicius 8 wins, Ergin Ataman 6 wins\./);
});

test("the head-to-head meeting line carries the score in home-away order, the winner in ink 600", () => {
  const html = renderH2h(load());
  // 2026-04-10: PAO 79 - 84 FBT, away won: the away side is the winner span.
  assert.match(
    html,
    /<span class="d">10 Apr 2026<\/span><span class="t"><span class="lose">PAO 79<\/span>–<span class="win">84 FBT<\/span><\/span>/,
  );
  assert.match(html, /<ol class="meetings">/);
});

test("a head to head with no meetings says so and lists none", () => {
  const r = load();
  const html = renderH2h({ ...r, h2h: { since: 2007, games: 0, home_wins: 0, away_wins: 0, last: [] } });
  assert.match(html, /No EuroLeague meetings since 2007-08\./);
  assert.ok(!html.includes('<ol class="meetings">'));
});

test("a coaches' head to head of zero hides the meeting line", () => {
  const r = load();
  const html = renderCoaches(
    { ...r, coaches: { ...r.coaches!, h2h: { games: 0, home_wins: 0, away_wins: 0 } } },
    "",
  );
  assert.ok(!html.includes("Coaches met"));
});

test("a null home coach shows Not recorded on the home side", () => {
  const r = load();
  const html = renderCoaches({ ...r, coaches: { ...r.coaches!, home: null } }, "");
  assert.match(html, /<p class="mr-note">Not recorded\.<\/p>/);
  assert.ok(html.includes("Sarunas Jasikevicius"));
});

// ---- A real report from the pipeline (copied as a fixture) ----

const real = (): MatchReport =>
  JSON.parse(readFileSync(new URL("./fixtures/match_report_real.json", import.meta.url), "utf8")) as MatchReport;

test("the real E2026_69 report renders every block with its real shape", () => {
  const r = real();
  const html = renderReport(r, "");
  for (const t of TITLES) assert.ok(html.includes(t), `missing block: ${t}`);
  // Injury comments are long text and render in their own line.
  assert.match(html, /<span class="note">Not included in official Euroleague roster<\/span>/);
  // Coaches: the real records, away first, and the zero head to head is not printed.
  assert.match(html, /Xavier Albert/);
  assert.match(html, /Maxime Lefevre/);
  assert.ok(html.indexOf("Xavier Albert") < html.indexOf("Maxime Lefevre"));
  assert.ok(!html.includes("Coaches met"));
  // Head to head: two meetings, no zero-game line.
  assert.match(html, /2 meetings since 2007-08/);
});

test("coaches link to the coach page and show both records", () => {
  const html = renderCoaches(load(), "");
  assert.match(html, /<a href="\/coaches\/ergin-ataman\/">Ergin Ataman<\/a>/);
  assert.match(html, /This season/);
  assert.match(html, /4–2/);
  assert.match(html, /310–190/);
  assert.match(html, /Coaches met 14 times/);
  assert.match(html, /Timeouts per game/);
});

test("text from the data is escaped everywhere", () => {
  const r = load();
  const evil = `<img src=x onerror="alert(1)">`;
  const html = renderReport(
    {
      ...r,
      home: { code: "PAO", name: evil },
      model: { ...r.model, available: false, reason: `<b>bad</b> & "quoted"` },
      players: { home: [{ ...r.players!.home[0], name: evil, slug: null }], away: [] },
      form: { home: [{ ...r.form!.home[0], opp: evil }], away: [] },
    },
    "",
  );
  assert.ok(!html.includes("<img"), "raw img tag must not survive");
  assert.ok(!html.includes("<b>bad</b>"));
  assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  assert.match(html, /&lt;b&gt;bad&lt;\/b&gt; &amp; &quot;quoted&quot;/);
});

test("other models render one line each", () => {
  const html = renderModel(load());
  assert.match(html, /Possession model/);
  assert.match(html, /Elo \+ roster/);
  assert.match(html, /PAO 64% · by 3\.9/);
});
