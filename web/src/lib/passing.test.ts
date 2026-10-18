// Unit tests for the Passing tab: the roster volumes, the top players, the matrix, the list and
// the matched share. Run with `node --test src/lib/` from web/ (Node 24+ strips the types).

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildMatrix,
  connections,
  matchedShare,
  passingView,
  roster,
  strongPairs,
  topPlayers,
  type AssistClub,
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
