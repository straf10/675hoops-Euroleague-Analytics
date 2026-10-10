// Form on the player page: his last games as bars of points, with the season average as a line.
// Pure strings from a season's game log.

import { esc } from "./format";
import { dataTip, tip } from "./tip";
import type { PlayerSeason } from "./stats";

export interface FormGame {
  date: string;
  opp: string;
  home: boolean;
  won: boolean;
  own: number;
  their: number;
  min: number;
  pts: number;
  reb: number;
  ast: number;
  pir: number;
}

/** The latest `n` games, oldest first. */
export function recentGames(s: PlayerSeason, n = 10): FormGame[] {
  const at = (name: string) => s.logFields.indexOf(name);
  const g = (name: string) => s.gameFields.indexOf(name);
  return s.log.slice(-n).map((line) => {
    const game = s.games[String(line[at("game_id")])];
    const team = String(line[at("team")]);
    const num = (name: string) => Number(line[at(name)]);
    const home = game?.[g("home")] === team;
    const hs = Number(game?.[g("home_score")]);
    const as = Number(game?.[g("away_score")]);
    const own = home ? hs : as;
    const their = home ? as : hs;
    return {
      date: String(game?.[g("date")]),
      opp: String(home ? game?.[g("away")] : game?.[g("home")]),
      home,
      won: own > their,
      own,
      their,
      min: Math.round(num("sec") / 60),
      pts: num("pts"),
      reb: num("oreb") + num("dreb"),
      ast: num("ast"),
      pir: num("pir"),
    };
  });
}

export const mean = (xs: number[]): number => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

/** One bar per game: height by points, the figure above it, a tip with the game, a dashed line at the season average. */
export function trendHtml(games: FormGame[], seasonAvg: number): string {
  const top = Math.max(1, seasonAvg, ...games.map((x) => x.pts));
  const day = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const bars = games
    .map((x) => {
      const body = tip`<b>${x.pts} points</b> ${x.home ? "vs" : "@"} ${x.opp}, ${day(x.date)}<br>${x.won ? "W" : "L"} ${x.own}–${x.their} · ${x.min} min · ${x.reb} reb · ${x.ast} ast`;
      return `<li class="bar" tabindex="0"${dataTip(body)} style="--h:${((100 * x.pts) / top).toFixed(1)}"><span class="v">${x.pts}</span><i></i><span class="o">${esc(x.opp)}</span></li>`;
    })
    .join("");
  return `<ol class="trend" style="--avg:${((100 * seasonAvg) / top).toFixed(1)}">${bars}</ol>`;
}
