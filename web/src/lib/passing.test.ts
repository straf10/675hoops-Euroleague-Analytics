// Unit tests for the Passing tab: the roster volumes, the top players, the matrix, the list and
// the matched share. Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  EDGE_MAX,
  EDGE_MIN,
  VIEW,
  buildMatrix,
  connections,
  edgeOpacity,
  edgeTitle,
  edgeWidth,
  labels,
  matchedShare,
  network,
  passingView,
  roster,
  strongPairs,
  topPlayers,
  vertex,
  type AssistClub,
  type PairRow,
  type Person,
} from "./passing.ts";

const person = (id: string, assists: number, made: number): Person => ({
  id,
  name: `Player ${id}`,
  slug: id.toLowerCase(),
  assists,
  made,
});

const club: AssistClub = {
  as_rows: 20,
  linked: 18,
  box: 20,
  pairs: [
    ["A", "B", 4, 9],
    ["A", "C", 2, 4],
    ["B", "A", 2, 4],
    ["C", "A", 1, 2], // below the threshold
    ["B", "C", 3, 6],
  ],
  passers: [
    ["A", 9, 6, 13],
    ["B", 5, 5, 10],
  ],
};

test("roster volumes read assists and both made field-goal columns by name", () => {
  const fields = ["gp", "ast", "fg2m", "fg3m"];
  const people = roster(
    [{ id: "A", name: "Ann", slug: "ann", totals: [10, 7, 3, 2] }],
    fields,
  );
  assert.deepEqual(people, [{ id: "A", name: "Ann", slug: "ann", assists: 7, made: 5 }]);
});

test("roster volumes are zero when a field is absent", () => {
  const people = roster([{ id: "A", name: "Ann", slug: "ann", totals: [10] }], ["gp"]);
  assert.equal(people[0].assists, 0);
  assert.equal(people[0].made, 0);
});

test("the top players rank by assists plus made field goals, eight at most", () => {
  const people = [person("A", 1, 1), person("B", 5, 0), person("C", 0, 0), person("D", 0, 4)];
  assert.deepEqual(
    topPlayers(people).map((p) => p.id),
    ["B", "D", "A"],
  );
  const many = Array.from({ length: 12 }, (_, i) => person(`P${i}`, i + 1, 0));
  assert.equal(topPlayers(many).length, 8);
});

test("pairs below the threshold are not strong, and the strong ones sort by assists", () => {
  assert.deepEqual(strongPairs(club), [
    ["A", "B", 4, 9],
    ["B", "C", 3, 6],
    ["A", "C", 2, 4],
    ["B", "A", 2, 4],
  ]);
});

test("the matrix puts assists in row = passer, column = scorer, and leaves the rest empty", () => {
  const players = [person("A", 6, 0), person("B", 3, 6), person("C", 0, 3)];
  const m = buildMatrix(strongPairs(club), players);
  assert.equal(m.cells[0][1]?.assists, 4); // A -> B
  assert.equal(m.cells[0][1]?.points, 9);
  assert.equal(m.cells[1][0]?.assists, 2); // B -> A
  assert.equal(m.cells[0][0], null); // the diagonal
  assert.equal(m.cells[2][0], null); // C -> A is below the threshold
  assert.equal(m.cells[0][1]?.shade, 1); // the largest cell is fully shaded
  assert.equal(m.cells[1][0]?.shade, 0.5);
});

test("the matrix skips pairs with a player outside the top list", () => {
  const m = buildMatrix(strongPairs(club), [person("A", 6, 0), person("B", 3, 6)]);
  const total = m.cells.flat().filter((c) => c !== null).length;
  assert.equal(total, 2); // A -> B and B -> A only
});

test("connections are the text list: passer, scorer, assists and points, named", () => {
  const names = new Map([
    ["A", "Ann"],
    ["B", "Ben"],
  ]);
  assert.deepEqual(connections(club, names, 2), [
    { passer: "Ann", scorer: "Ben", assists: 4, points: 9 },
    { passer: "Ben", scorer: "C", assists: 3, points: 6 },
  ]);
});

test("the matched share is linked over box-score assists, null without box assists", () => {
  assert.equal(matchedShare(club), 0.9);
  assert.equal(matchedShare({ ...club, box: 0 }), null);
});

test("the view is null without the club's assist file", () => {
  assert.equal(passingView(2024, undefined, []), null);
});

test("the view carries the caveat numbers and the matrix players", () => {
  const people = [person("A", 6, 0), person("B", 3, 6)];
  const view = passingView(2024, club, people);
  assert.ok(view);
  assert.equal(view.season, 2024);
  assert.equal(view.matched, 0.9);
  assert.equal(view.asRows, 20);
  assert.equal(view.matrix.players.length, 2);
  assert.equal(view.connections[0].passer, "Player A");
});

// ---- The network ----

const net = (pairs: PairRow[]): AssistClub => ({ ...club, pairs, passers: [] });
const names = new Map([
  ["A", "Ann Ash"],
  ["B", "Ben Birch"],
  ["C", "Cy Cole"],
  ["D", "Dee Dunn"],
]);

test("vertices sit on a circle, the first at the top, clockwise", () => {
  const v = (i: number, n: number) => vertex(i, n);
  const top = v(0, 4);
  assert.equal(top.x, VIEW.cx);
  assert.equal(top.y, VIEW.cy - VIEW.r);
  assert.equal(v(1, 4).x, VIEW.cx + VIEW.r);
  assert.equal(v(2, 4).y, VIEW.cy + VIEW.r);
  for (const n of [3, 5, 8]) {
    for (let i = 0; i < n; i++) {
      const p = vertex(i, n);
      const radius = Math.hypot(p.x - VIEW.cx, p.y - VIEW.cy);
      assert.ok(Math.abs(radius - VIEW.r) < 0.5, `n=${n} i=${i} radius ${radius}`);
      assert.ok(p.x > 0 && p.x < VIEW.w && p.y > 0 && p.y < VIEW.h);
    }
  }
});

test("labels anchor away from the polygon and stay inside the viewBox", () => {
  assert.equal(vertex(0, 4).anchor, "middle");
  assert.equal(vertex(1, 4).anchor, "start"); // right side: the text runs right
  assert.equal(vertex(3, 4).anchor, "end"); // left side: the text runs left
  for (const n of [3, 4, 8]) {
    for (let i = 0; i < n; i++) {
      const p = vertex(i, n);
      assert.ok(p.ly > 0 && p.ly < VIEW.h, `label y ${p.ly} for n=${n} i=${i}`);
      if (p.anchor === "start") assert.ok(p.lx + 110 < VIEW.w, "room for a long surname on the right");
      if (p.anchor === "end") assert.ok(p.lx - 110 > 0, "room for a long surname on the left");
    }
  }
});

test("line width is linear in the count: one assist is 1px, the team's largest pair 9px", () => {
  assert.equal(EDGE_MIN, 1);
  assert.equal(EDGE_MAX, 9);
  assert.equal(edgeWidth(1, 9), 1);
  assert.equal(edgeWidth(9, 9), 9);
  assert.equal(edgeWidth(5, 9), 5); // halfway between one and nine is five
  assert.equal(edgeWidth(3, 9), 3);
  assert.equal(edgeWidth(40, 9), 9); // capped at the largest
  assert.equal(edgeWidth(1, 1), EDGE_MIN); // no spread: every pair is one assist
  assert.equal(edgeWidth(3, 0), EDGE_MIN);
});

test("opacity is linear too: 0.25 for one assist, 1 for the team's largest pair", () => {
  assert.equal(edgeOpacity(1, 9), 0.25);
  assert.equal(edgeOpacity(9, 9), 1);
  assert.equal(edgeOpacity(5, 9), 0.63); // 0.625, rounded to two places
  assert.equal(edgeOpacity(1, 1), 0.25);
});

test("a network with more than 20 pairs does not draw the single-assist pairs and says how many", () => {
  const ids = Array.from({ length: 8 }, (_, i) => `P${i}`);
  const many = new Map(ids.map((id, i) => [id, `Player ${i}`]));
  const pairs: PairRow[] = [];
  let singles = 0;
  for (let i = 0; i < 8; i++) {
    for (let j = i + 1; j < 8; j++) {
      const one = (i + j) % 3 === 0;
      if (one) singles++;
      pairs.push([ids[i], ids[j], one ? 1 : 2 + ((i * j) % 4), 0]);
    }
  }
  const n = network(net(pairs), many);
  assert.equal(n.players.length, 8);
  assert.equal(n.edges.length, 28 - singles);
  assert.equal(n.hiddenPairs, singles);
  assert.ok(n.edges.every((e) => e.total > 1));
});

test("with 20 pairs or fewer the single-assist pairs are drawn, thinnest and faintest", () => {
  const n = network(net([["A", "B", 1, 2], ["B", "C", 4, 8], ["C", "A", 2, 4]]), names);
  assert.equal(n.hiddenPairs, 0);
  assert.equal(n.edges.length, 3);
  const weakest = n.edges[0];
  assert.equal(weakest.total, 1);
  assert.equal(weakest.width, EDGE_MIN);
  assert.equal(weakest.opacity, 0.25);
  assert.equal(n.edges[n.edges.length - 1].opacity, 1);
});

test("a pair's two directions combine into one line, with both counts kept", () => {
  const n = network(net([["A", "B", 4, 9], ["B", "A", 2, 4]]), names);
  assert.equal(n.players.length, 2);
  assert.equal(n.edges.length, 1);
  const [e] = n.edges;
  assert.equal(n.players[e.a].id, "A");
  assert.equal(n.players[e.b].id, "B");
  assert.equal(e.ab, 4);
  assert.equal(e.ba, 2);
  assert.equal(e.total, 6);
  assert.equal(e.width, EDGE_MAX); // 6 is the largest pair, so it is the thickest
  assert.equal(edgeTitle(e, n.players), "Ann Ash to Ben Birch: 4 assists, Ben Birch to Ann Ash: 2 assists");
});

test("a single assist draws a line, and the tooltip says 1 assist", () => {
  const n = network(net([["A", "B", 1, 2]]), names);
  assert.equal(n.edges.length, 1);
  assert.equal(n.edges[0].width, EDGE_MIN);
  assert.equal(edgeTitle(n.edges[0], n.players), "Ann Ash to Ben Birch: 1 assist, Ben Birch to Ann Ash: 0 assists");
});

test("self-links are never drawn or listed", () => {
  const c = net([["A", "A", 5, 10], ["A", "B", 2, 4]]);
  assert.deepEqual(strongPairs(c), [["A", "B", 2, 4]]);
  const n = network(c, names);
  assert.equal(n.edges.length, 1);
  assert.equal(n.players.find((p) => p.id === "A")?.given, 2);
});

test("the polygon takes the top players by assists involvement and drops the rest", () => {
  const c = net([
    ["A", "B", 5, 10],
    ["C", "B", 1, 2],
    ["D", "A", 1, 2],
  ]);
  const n = network(c, names, 2);
  assert.deepEqual(n.players.map((p) => p.id), ["A", "B"]);
  assert.equal(n.edges.length, 1); // C and D are off the polygon, so their lines are not drawn
});

test("thicker lines come last, so they paint on top", () => {
  const c = net([
    ["A", "B", 9, 18],
    ["B", "C", 1, 2],
    ["C", "D", 3, 6],
  ]);
  const n = network(c, names);
  const totals = n.edges.map((e) => e.total);
  assert.deepEqual(totals, [...totals].sort((x, y) => x - y));
  assert.equal(n.edges[n.edges.length - 1].width, EDGE_MAX);
});

test("labels are surnames, with the initial where two drawn players share one", () => {
  assert.deepEqual(labels(["Ann Ash", "Ben Birch"]), ["Ash", "Birch"]);
  assert.deepEqual(labels(["Wade Baldwin IV", "Ann Baldwin"]), ["W. Baldwin", "A. Baldwin"]);
  assert.deepEqual(labels(["Madonna"]), ["Madonna"]);
});

test("a club with no pairs has an empty network", () => {
  const empty = network(net([]), names);
  assert.deepEqual(empty, { players: [], edges: [], hiddenPairs: 0 });
});

test("the view carries the network", () => {
  const view = passingView(2024, club, [person("A", 6, 0), person("B", 3, 6)]);
  assert.ok(view);
  assert.equal(view.network.players.length, 3);
  assert.equal(view.network.edges.length, 3);
});
