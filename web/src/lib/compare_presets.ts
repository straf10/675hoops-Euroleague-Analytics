// Curated comparisons for Compare's start page: each opens the page with its players loaded.
// A pick is "slug" (career) or "slug:season" (season, by start year: 2022 = 2022-23).
// Every slug and season must exist in the data the build uses. The build skips a preset that does
// not and warns; tests/test_web_compare_presets.py fails on it against the real data.
// Every player preset compares three players (owner, 2026-10-19; the test checks it).
// The first preset is what Compare opens on when the link names no players (defaultPresetQuery).
//
// Dropped from plan §4 after the check against the data (2026-10-18):
//   1 (Dončić is not in the data), 8 (Spanoulis), 9 (Navarro), 11 (Bogdanović).
// Preset 3 says "Fall": Moustapha Fall is used (Olympiacos, 2022-23).
// Season picks use 2022-23 or later: the polygon needs a percentile pool, and the export has pools
// for its site seasons only (2026-10-19, owner: the 2021-22 presets moved to 2022+; the Efes 2021-22
// title backcourt became the Panathinaikos 2023-24 one).
// Preset 16 is dropped: a page has one scope (season or career), and no active player is a fair
// "one-season wonder".

export interface Preset {
  label: string;
  scope: "season" | "career";
  picks: string[];
}

export const PRESETS: Preset[] = [
  { label: "Real Madrid point guards", scope: "career", picks: ["sergio-llull", "facundo-campazzo", "sergio-rodriguez"] },
  { label: "Rim protectors", scope: "season", picks: ["walter-tavares:2022", "mathias-lessort:2023", "moustapha-fall:2022"] },
  { label: "Greek playmakers", scope: "career", picks: ["kostas-sloukas", "nick-calathes", "kostas-papanikolaou"] },
  { label: "Panathinaikos title backcourt", scope: "season", picks: ["kendrick-nunn:2023", "kostas-sloukas:2023", "marius-grigonis:2023"] },
  { label: "Pure scorers", scope: "career", picks: ["mike-james", "shane-larkin", "kevin-punter"] },
  { label: "Stretch fours", scope: "season", picks: ["nikola-mirotic:2022", "sasha-vezenkov:2022", "johannes-voigtmann:2022"] },
  { label: "Winning big men", scope: "career", picks: ["kyle-hines", "walter-tavares", "nikola-milutinov"] },
  { label: "Volume scorers", scope: "season", picks: ["markus-howard:2022", "kevin-punter:2023", "will-clyburn:2022"] },
  { label: "Big forwards", scope: "career", picks: ["tornike-shengelia", "mario-hezonja", "brandon-davies"] },
  { label: "Long-serving wings", scope: "career", picks: ["will-clyburn", "marius-grigonis", "adam-hanga"] },
  { label: "Scoring guards", scope: "season", picks: ["kendrick-nunn:2024", "mike-james:2023", "shane-larkin:2024"] },
];

/** The query string Compare reads for a preset: `?p=a,b,c`, with `scope=career` for a career preset. */
export function presetQuery(p: Preset): string {
  const scope = p.scope === "career" ? "scope=career&" : "";
  return `?${scope}p=${p.picks.join(",")}`;
}

/** The link that opens Compare with the preset loaded. */
export function presetHref(base: string, p: Preset): string {
  return `${base.replace(/\/$/, "")}/compare/${presetQuery(p)}`;
}

/** The query Compare opens with when the link names no players: the first curated preset, so the
 *  page is never empty. Empty when there is no preset to show. */
export function defaultPresetQuery(presets: Preset[]): string {
  return presets.length ? presetQuery(presets[0]) : "";
}

/** Problems with one preset: an unknown slug, or a season the player has no lines for. */
export function presetProblems(p: Preset, seasonsOf: (slug: string) => number[] | null): string[] {
  const out: string[] = [];
  for (const pick of p.picks) {
    const [slug, season] = pick.split(":");
    const seasons = seasonsOf(slug);
    if (!seasons) {
      out.push(`${slug}: no such player`);
      continue;
    }
    if (season !== undefined && !seasons.includes(Number(season))) out.push(`${slug}: no ${season} season`);
  }
  return out;
}

/** The presets the data can show, and a warning line for each one it cannot. */
export function usablePresets(presets: Preset[], seasonsOf: (slug: string) => number[] | null): { ok: Preset[]; warnings: string[] } {
  const ok: Preset[] = [];
  const warnings: string[] = [];
  for (const p of presets) {
    const problems = presetProblems(p, seasonsOf);
    if (problems.length) warnings.push(`Compare preset "${p.label}" skipped: ${problems.join("; ")}`);
    else ok.push(p);
  }
  return { ok, warnings };
}
