// Unit tests for the round cards' data: which rounds are open, their order, how a played game and an
// unplayed one read, and that a finished round is a recap rather than an open card.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { Competition, OpenRoundGame } from "./format.ts";
import { openCall, openRoundCards, openState, recapCards, roundCardNames } from "./cards/rounds.ts";

const team = (code: string) => ({ code, name: `Club ${code}` });

function game(id: string, tipoff: string, over: Partial<OpenRoundGame> = {}): OpenRoundGame {
  return {
    game_id: id,
    tipoff_utc: tipoff,
    predicted_at_utc: "2026-10-20T08:00:00Z",
    home: team("HOM"),
    away: team("AWY"),
    p_home: 0.6,
    exp_margin: 3.2,
    played: false,
    forfeit: false,
    home_score: null,
    away_score: null,
    hit: null,
    ...over,
  };
}

/** A competition with the given open rounds and no forecast record (the recap tests add one). */
function comp(open: Competition["open_rounds"], extra: Partial<Competition> = {}): Competition {
  return { key: "euroleague", season: 2026, open_rounds: open, ...extra } as unknown as Competition;
}

test("open rounds are listed earliest round first, whatever order the data gives", () => {
  const c = comp([
    { round: 10, games: [game("E10_1", "2026-10-22T18:00:00Z")] },
    { round: 9, games: [game("E9_1", "2026-10-20T18:00:00Z")] },
  ]);
  assert.deepEqual(
    openRoundCards(c).map((r) => r.round),
    [9, 10],
  );
});

test("each open round's games are in tip-off order and its loggedAt is the newest forecast", () => {
  const c = comp([
    {
      round: 9,
      games: [
        game("late", "2026-10-21T18:00:00Z", { predicted_at_utc: "2026-10-19T08:30:00Z" }),
        game("early", "2026-10-20T16:00:00Z", { predicted_at_utc: "2026-10-18T09:15:00Z" }),
      ],
    },
  ]);
  const [card] = openRoundCards(c);
  assert.deepEqual(
    card.games.map((g) => g.game_id),
    ["early", "late"],
  );
  assert.equal(card.loggedAt, "2026-10-19 08:30");
  assert.equal(card.seasonName, "EuroLeague 2026");
});

test("a played game shows its final and whether the favourite won; an unplayed one is to play", () => {
  const played = game("P", "2026-10-20T18:00:00Z", {
    played: true,
    home_score: 85,
    away_score: 78,
    p_home: 0.7,
    hit: true,
  });
  const todo = game("U", "2026-10-21T18:00:00Z");
  assert.equal(openState(played), "final");
  assert.equal(openCall(played), true);
  assert.equal(openState(todo), "to_play");
  assert.equal(openCall(todo), null);
});

test("a played upset is a miss, and a coin-toss forecast is not scored", () => {
  const upset = game("X", "2026-10-20T18:00:00Z", { played: true, home_score: 70, away_score: 82, p_home: 0.7, hit: false });
  const toss = game("T", "2026-10-20T18:00:00Z", { played: true, home_score: 70, away_score: 82, p_home: 0.5, hit: false });
  assert.equal(openCall(upset), false);
  assert.equal(openCall(toss), null);
});

test("a forfeit is neither a final nor a call", () => {
  const forfeit = game("F", "2026-10-20T18:00:00Z", { played: false, forfeit: true, home_score: 20, away_score: 0 });
  assert.equal(openState(forfeit), "forfeit");
  assert.equal(openCall(forfeit), null);
});

test("the card names are the open rounds (earliest first), then the recaps", () => {
  const c = comp([
    { round: 9, games: [game("E9_1", "2026-10-20T18:00:00Z")] },
    { round: 10, games: [game("E10_1", "2026-10-22T18:00:00Z")] },
  ]);
  assert.deepEqual(roundCardNames(c), [
    { name: "round-9", kind: "open", round: 9 },
    { name: "round-10", kind: "open", round: 10 },
  ]);
});

test("a finished round is a recap, and an open round is never also a recap", () => {
  const scored = (id: string, round: number, right: boolean) => ({
    game_id: id,
    phase: "RS",
    round,
    tipoff_utc: "2026-10-10T18:00:00Z",
    home: team("HOM"),
    away: team("AWY"),
    home_score: 80,
    away_score: 75,
    models: { elo: { p_home: 0.6, right } },
  });
  const c = comp([{ round: 10, games: [game("E10_1", "2026-10-22T18:00:00Z")] }], {
    forecasts: {
      published: "elo",
      games: [scored("E9_1", 9, true), scored("E10_0", 10, false)],
      season: [{ model: "elo", right: 1, picks: 2, brier: 0.2, log_loss: 0.6 }],
    },
    scorecard: { b0: { brier: 0.25, log_loss: 0.69 } },
  } as unknown as Partial<Competition>);
  const recaps = recapCards(c);
  assert.deepEqual(
    recaps.map((r) => r.round),
    [9],
  );
  assert.deepEqual(
    roundCardNames(c).map((r) => r.name),
    ["round-10", "round-9-recap"],
  );
});
