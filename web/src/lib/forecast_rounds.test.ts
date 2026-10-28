import assert from "node:assert/strict";
import { test } from "node:test";

import type { FcGame } from "./forecasts.ts";
import {
  gameRowHtml,
  leadModel,
  roundFromQuery,
  roundGroups,
  roundId,
  roundParam,
  roundSearch,
} from "./forecast_rounds.ts";

const team = (code: string, name = code) => ({ code, name, id: code }) as FcGame["home"];

const game = (
  id: string,
  phase: string,
  round: number,
  tipoff: string,
  models: FcGame["models"],
  scores: [number, number] = [80, 70],
): FcGame => ({
  game_id: id,
  round,
  phase,
  tipoff_utc: tipoff,
  home: team("PAN", "Panathinaikos"),
  away: team("OLY", "Olympiacos"),
  home_score: scores[0],
  away_score: scores[1],
  models,
});

const call = (p: number, right: boolean | null) => ({ p_home: p, exp_margin: 3.2, right });

// Newest first, as publish.py writes them.
const games: FcGame[] = [
  game("g9", "PO", 1, "2026-05-10T18:00:00Z", { ours: call(0.6, true), other: call(0.4, false) }),
  game("g8", "RS", 7, "2026-04-02T18:00:00Z", { ours: call(0.7, false), other: call(0.7, false) }),
  game("g7", "RS", 7, "2026-04-01T18:00:00Z", { ours: call(0.55, true), other: call(0.5, null) }),
  game("g6", "RS", 6, "2026-03-26T18:00:00Z", { ours: call(0.3, true) }),
  game("g5", "RS", 5, "2026-03-19T18:00:00Z", { other: call(0.8, true) }),
];

test("roundId names regular-season rounds by number and postseason phases by code", () => {
  assert.equal(roundId("RS", 7), "7");
  assert.equal(roundId("PO", 1), "PO");
});

test("roundGroups groups the games a model called, latest round first", () => {
  const groups = roundGroups(games, "ours");
  assert.deepEqual(
    groups.map((g) => [g.id, g.label, g.games.map((x) => x.game_id)]),
    [
      ["PO", "Playoffs", ["g9"]],
      ["7", "Round 7", ["g8", "g7"]],
      ["6", "Round 6", ["g6"]],
    ],
  );
});

test("roundGroups leaves out games the model did not call", () => {
  const groups = roundGroups(games, "other");
  assert.deepEqual(
    groups.map((g) => g.id),
    ["PO", "7", "5"],
  );
  assert.equal(groups[1].games.length, 2);
});

test("roundGroups orders by the newest tipoff in each round, whatever the input order", () => {
  const shuffled = [games[3], games[4], games[2], games[0], games[1]];
  assert.deepEqual(
    roundGroups(shuffled, "ours").map((g) => g.id),
    ["PO", "7", "6"],
  );
});

test("roundGroups is empty when nobody called a game", () => {
  assert.deepEqual(roundGroups(games, "nobody"), []);
  assert.deepEqual(roundGroups([], "ours"), []);
});

test("the default round is the latest one with logged forecasts", () => {
  const groups = roundGroups(games, "ours");
  assert.equal(roundFromQuery("", roundParam("euroleague"), groups)?.id, "PO");
});

test("a valid query picks its round; unknown or missing values fall back to the latest", () => {
  const groups = roundGroups(games, "ours");
  const param = roundParam("euroleague");
  assert.equal(roundFromQuery("?euroleague-round=6", param, groups)?.id, "6");
  assert.equal(roundFromQuery("?euroleague-round=99", param, groups)?.id, "PO");
  assert.equal(roundFromQuery("?euroleague-round=", param, groups)?.id, "PO");
  assert.equal(roundFromQuery("?euroleague-round=7&x=1", param, groups)?.id, "7");
  assert.equal(roundFromQuery("?round=6", param, groups)?.id, "PO");
  assert.equal(roundFromQuery("?other-round=6", param, groups)?.id, "PO");
});

test("roundFromQuery is null when there are no rounds", () => {
  assert.equal(roundFromQuery("?euroleague-round=7", roundParam("euroleague"), []), null);
});

test("roundSearch sets the round, drops it at the default, and keeps other parameters", () => {
  const param = roundParam("euroleague");
  assert.equal(roundSearch("", param, "6", "PO"), "?euroleague-round=6");
  assert.equal(roundSearch("?other-round=3", param, "6", "PO"), "?other-round=3&euroleague-round=6");
  assert.equal(roundSearch("?euroleague-round=6", param, "PO", "PO"), "");
  assert.equal(roundSearch("?other-round=3&euroleague-round=6", param, "PO", "PO"), "?other-round=3");
});

test("leadModel is the published model, else the first listed", () => {
  assert.equal(leadModel({ published: "ours", models: [{ key: "other" }, { key: "ours" }] }), "ours");
  assert.equal(leadModel({ published: null, models: [{ key: "other" }] }), "other");
  assert.equal(leadModel({ published: null, models: [] }), undefined);
  assert.equal(leadModel(null), undefined);
});

const icons = { hit: "<svg>yes</svg>", miss: "<svg>no</svg>" };

test("a game row prints the call, its verdict and the score side that won", () => {
  const html = gameRowHtml(games[1], "ours", icons);
  assert.match(html, /^<tr data-group="RS-7">/);
  assert.match(html, /<td class="call">70% <span class="mg">\+3\.2<\/span><span class="pill miss"><span class="icon"><svg>no<\/svg><\/span>Wrong<\/span><\/td>/);
  assert.match(html, /<td class="team r won">/);
  assert.match(html, /<span class="won">80<\/span><span class="dash">-<\/span><span>70<\/span>/);
  assert.match(html, /<td class="team"><b>OLY<\/b>/);
});

test("an open game with no verdict shows the call only; a game the model skipped shows a dash", () => {
  const withoutVerdict = gameRowHtml(games[2], "other", icons);
  assert.match(withoutVerdict, /<td class="call">50% <span class="mg">\+3\.2<\/span><span class="dash">–<\/span><\/td>/);
  const skipped = gameRowHtml(games[4], "ours", icons);
  assert.match(skipped, /<td class="call">–<\/td>/);
});

test("team names are escaped in a row", () => {
  const g = { ...games[3], home: team("PAN", "<img src=x>") };
  assert.ok(gameRowHtml(g, "ours", icons).includes("&lt;img src=x&gt;"));
});
