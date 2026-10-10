// Gathers the numbers the season-end projection needs from the season exports (lib/season_end.ts
// holds the formula): his minutes, his team's game seconds, pace, games played and left.

import { totalsOf } from "./player";
import { MIN_GAMES, minutesShare, pacePer40, seasonEnd, totalGames, type SeasonEnd } from "./season_end";
import { season, type PlayerSeason, type SeasonTeams } from "./stats";

interface Club {
  gp: number;
  poss: number;
  sec: number;
}

const clubOf = (t: SeasonTeams, code: string): Club | null => {
  const row = t.teams.find((x) => x.code === code);
  const at = (f: string) => t.fields.indexOf(f);
  return row ? { gp: row.totals[at("gp")], poss: row.totals[at("poss")], sec: row.totals[at("game_sec")] } : null;
};

/** His share of team minutes in one season of his. A season with two clubs is read per game. */
function shareOf(row: PlayerSeason | undefined, t: SeasonTeams | null): number | null {
  if (!row || !t) return null;
  const mine = totalsOf(row.fields, row.totals);
  const clubs = row.teams.map((c) => clubOf(t, c)).filter((c): c is Club => c !== null && c.gp > 0);
  if (!clubs.length || !mine.gp) return null;
  if (clubs.length === 1) return minutesShare({ sec: mine.sec, teamSec: clubs[0].sec });
  const perGame = clubs.reduce((a, c) => a + c.sec / c.gp, 0) / clubs.length;
  return minutesShare({ sec: mine.sec / mine.gp, teamSec: perGame });
}

export interface SeasonEndPage {
  figures: SeasonEnd;
  gamesPlayed: number;
  total: number;
}

/** null when any input is missing: no live team, no share (a first-year player with under MIN_GAMES), no pace. */
export async function seasonEndFor(o: {
  live: number;
  /** M6 projected points per 100 possessions. */
  per100: number;
  /** His club by display code when he has no row yet this season. */
  fallbackTeam: string;
  /** His seasons, oldest first. */
  rows: PlayerSeason[];
}): Promise<SeasonEndPage | null> {
  const teamsNow = await season(o.live, "teams");
  const nowRow = o.rows.find((s) => s.season === o.live);
  const prevRow = o.rows.find((s) => s.season === o.live - 1);
  const teamsPrev = prevRow ? await season(o.live - 1, "teams") : null;
  const code = nowRow?.teams[nowRow.teams.length - 1] ?? o.fallbackTeam;
  const team = teamsNow.teams.find((t) => t.code === code);
  const now = clubOf(teamsNow, code);
  if (!team || !now) return null;

  const mine = nowRow ? totalsOf(nowRow.fields, nowRow.totals) : null;
  const share = mine && mine.gp >= MIN_GAMES ? shareOf(nowRow, teamsNow) : shareOf(prevRow, teamsPrev);
  const prev = teamsPrev ? clubOf(teamsPrev, code) : null;
  const source = now.gp >= MIN_GAMES ? now : (prev ?? now);
  const total = totalGames(teamsNow.teams.length);
  const figures =
    share &&
    seasonEnd({
      per100: o.per100,
      share,
      pace: pacePer40(source.poss, source.sec),
      pointsSoFar: mine?.pts ?? 0,
      gamesPlayed: mine?.gp ?? 0,
      teamGamesPlayed: team.w + team.l,
      total,
    });
  return figures ? { figures, gamesPlayed: mine?.gp ?? 0, total } : null;
}
