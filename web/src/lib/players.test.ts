// Unit tests for the Players page's advanced measures (net rating, AST/TOV, AST%, REB%), the rate
// switch and the query string. Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import { BY_KEY, dirOf, fromQuery, rated, toQuery, type View } from "./measures.ts";

const close = (actual: number | null, expected: number, eps = 1e-6) => {
  assert.notEqual(actual, null);
  assert.ok(Math.abs((actual as number) - expected) < eps, `${actual} vs ${expected}`);
};

test("net rating is 100 × plus-minus / possessions", () => {
  close(BY_KEY.net.value({ pm: 30, poss: 200 }), 15);
  close(BY_KEY.net.value({ pm: -10, poss: 100 }), -10);
  assert.equal(BY_KEY.net.value({ pm: 5, poss: 0 }), null);
  assert.equal(BY_KEY.net.signed, true);
});

test("AST/TOV divides assists by turnovers, and is a dash with no turnovers", () => {
  close(BY_KEY.ast_tov.value({ ast: 6, tov: 3 }), 2);
  assert.equal(BY_KEY.ast_tov.value({ ast: 6, tov: 0 }), null);
  assert.equal(BY_KEY.ast_tov.value({ ast: 0, tov: 0 }), null);
  assert.equal(BY_KEY.ast_tov.value({ ast: 0, tov: 2 }), 0);
});

test("AST% uses the Basketball-Reference form with the season's sums", () => {
  // Twenty minutes on court in games of 40: half his team's minutes. His team made 40 field goals
  // while he played; he made 4, so 20 - 4 = 16 teammate field goals on his floor time.
  const t = { ast: 6, fg2m: 3, fg2a: 0, fg3m: 1, fg3a: 0, sec: 1200, game_sec: 2400, tm_fgm: 40 };
  close(BY_KEY.ast_pct.value(t), 37.5);
  // No team field goals left over after his own: no share to measure.
  assert.equal(BY_KEY.ast_pct.value({ ...t, tm_fgm: 0 }), null);
});

test("REB% is 100 × TRB × (team MP / 5) / (MP × (team TRB + opponent TRB))", () => {
  const t = {
    oreb: 2,
    dreb: 6,
    sec: 1200,
    game_sec: 2400,
    tm_oreb: 10,
    tm_dreb: 30,
    opp_oreb: 8,
    opp_dreb: 22,
  };
  close(BY_KEY.reb_pct.value(t), (100 * 8 * 2400) / (1200 * 70));
  assert.equal(BY_KEY.reb_pct.value({ ...t, sec: 0 }), null);
});

test("the rate switch: counts follow it, percentages and fixed values do not", () => {
  const t = { gp: 2, sec: 2400, poss: 160, pts: 20, fg2m: 5, fg2a: 10, fg3m: 0, fg3a: 0, fta: 0, ftm: 0 };
  close(rated(BY_KEY.pts, t, "game"), 10);
  close(rated(BY_KEY.pts, t, "36"), (20 * 2160) / 2400);
  close(rated(BY_KEY.pts, t, "100"), (20 * 100) / 160);
  assert.equal(rated(BY_KEY.fg2_pct, t, "100"), rated(BY_KEY.fg2_pct, t, "game"));
  assert.equal(rated(BY_KEY.net, { ...t, pm: 8 }, "36"), rated(BY_KEY.net, { ...t, pm: 8 }, "game"));
});

test("RAPM ranks only with the board's minimum minutes", () => {
  assert.equal(BY_KEY.rapm.qualifies?.({ rapm_min: 499, rapm_floor: 500 }), false);
  assert.equal(BY_KEY.rapm.qualifies?.({ rapm_min: 500, rapm_floor: 500 }), true);
  assert.equal(BY_KEY.rapm.value({}), null);
});

test("a metric starts from its best end, and the query keeps the rate", () => {
  assert.equal(dirOf("tov"), "asc");
  assert.equal(dirOf("net"), "desc");
  const view: View = {
    season: 2025,
    metric: "net",
    dir: "desc",
    minMin: 10,
    top: 25,
    pos: "",
    set: "advanced",
    rate: "100",
  };
  const query = toQuery(view, 2026);
  assert.match(query, /rate=100/);
  assert.deepEqual(fromQuery(query, [2025, 2026], 2026).rate, "100");
  assert.equal(toQuery({ ...view, rate: "game" }, 2025).includes("rate="), false);
  assert.equal(fromQuery("?rate=12", [2025], 2025).rate, "game");
});
