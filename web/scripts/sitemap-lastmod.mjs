// The sitemap's <lastmod> for each page: the real date its content last changed, from the stats data.
//   game page    the game's date
//   player page  the date of the player's latest game
//   team page    the date of the club's latest game
//   coach page   the date of the club's latest game in the coach's last season there (the coach
//                files carry no per-game dates, so this is the closest the data gives)
//   static pages no lastmod (their content changes with the code, not the data)
// Pure parts (dateIndex, lastmodFor) are tested in sitemap-lastmod.test.mjs; readDates reads the
// stats folder the build reads (web/src/data/stats).

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** Keeps the latest date per key; dates are ISO days (YYYY-MM-DD), so they compare as strings. */
function latest(map, key, date) {
  if (date && (!map.has(key) || date > map.get(key))) map.set(key, date);
}

/**
 * The dates behind every page, from the stats data.
 * data: { seasons: [{ season, games: {id: [date, round, phase, home, away, ...]},
 *                     log_fields, logs: {playerId: [line, ...]} }],
 *         players: [{ id, slug }],
 *         coaches: [{ slug, seasons: [{ season, team }] }] }
 */
export function dateIndex(data) {
  const game = new Map();
  const team = new Map();
  const player = new Map();
  const coach = new Map();
  const teamSeason = new Map();
  const slugOf = new Map(data.players.map((p) => [p.id, p.slug]));
  for (const s of data.seasons) {
    const dates = new Map();
    for (const [id, g] of Object.entries(s.games)) {
      const [date, , , home, away] = g;
      dates.set(id, date);
      game.set(id, date);
      latest(team, String(home).toLowerCase(), date);
      latest(team, String(away).toLowerCase(), date);
      latest(teamSeason, `${s.season}|${home}`, date);
      latest(teamSeason, `${s.season}|${away}`, date);
    }
    const at = s.log_fields.indexOf("game_id");
    for (const [pid, lines] of Object.entries(s.logs ?? {})) {
      const slug = slugOf.get(pid);
      if (!slug) continue;
      for (const line of lines) latest(player, slug, dates.get(String(line[at])));
    }
  }
  for (const c of data.coaches) {
    for (const { season, team: club } of c.seasons ?? []) latest(coach, c.slug, teamSeason.get(`${season}|${club}`));
  }
  return { game, team, player, coach };
}

/** The <lastmod> day for a page URL, or undefined for a page with no data date (static pages). */
export function lastmodFor(url, index) {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  const [kind, key] = parts;
  if (parts.length !== 2) return undefined;
  const map = { games: index.game, players: index.player, teams: index.team, coaches: index.coach }[kind];
  return map?.get(kind === "teams" ? key.toLowerCase() : key);
}

/** Reads the stats folder (season games and logs, players, coaches) into dateIndex's shape. */
export function readDates(statsDir) {
  const seasonsDir = join(statsDir, "seasons");
  const seasons = readdirSync(seasonsDir)
    .filter((y) => existsSync(join(seasonsDir, y, "games.json")))
    .map((y) => {
      const file = JSON.parse(readFileSync(join(seasonsDir, y, "games.json"), "utf8"));
      return { season: Number(y), games: file.games, log_fields: file.log_fields, logs: file.logs };
    });
  const players = JSON.parse(readFileSync(join(statsDir, "players.json"), "utf8")).players;
  const coachesDir = join(statsDir, "coaches");
  const coaches = existsSync(coachesDir)
    ? readdirSync(coachesDir)
        .filter((f) => f.endsWith(".json") && f !== "index.json") // index.json lists the coaches
        .map((f) => {
          const c = JSON.parse(readFileSync(join(coachesDir, f), "utf8"));
          return { slug: c.slug, seasons: c.seasons };
        })
    : [];
  return dateIndex({ seasons, players, coaches });
}
