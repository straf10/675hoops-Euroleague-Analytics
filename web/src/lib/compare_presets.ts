// Curated comparisons for Compare's start page: each opens the page with its players loaded.
// A pick is "slug" (career) or "slug:season" (season, by start year: 2022 = 2022-23).
// Every slug and season must exist in the data the build uses. The build skips a preset that does
// not and warns; tests/test_web_compare_presets.py fails on it against the real data.
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
  { label: "Real Madrid point guards", scope: "career", picks: ["sergio-llull", "facundo-campazzo"] },
  { label: "Rim protectors", scope: "season", picks: ["walter-tavares:2022", "mathias-lessort:2023", "moustapha-fall:2022"] },
  { label: "Greek playmakers", scope: "career", picks: ["kostas-sloukas", "nick-calathes"] },
  { label: "Panathinaikos title backcourt", scope: "season", picks: ["kendrick-nunn:2023", "kostas-sloukas:2023"] },
  { label: "Pure scorers", scope: "career", picks: ["mike-james", "shane-larkin"] },
  { label: "Stretch fours", scope: "season", picks: ["nikola-mirotic:2022", "sasha-vezenkov:2022"] },
  { label: "Winning big men", scope: "career", picks: ["kyle-hines", "walter-tavares"] },
  { label: "Volume scorers", scope: "season", picks: ["markus-howard:2022", "kevin-punter:2023"] },
  { label: "Big forwards", scope: "career", picks: ["tornike-shengelia", "mario-hezonja"] },
  { label: "Long-serving wings", scope: "career", picks: ["will-clyburn", "marius-grigonis"] },
  { label: "Scoring guards", scope: "season", picks: ["kendrick-nunn:2024", "mike-james:2023"] },
];

/** The link that opens Compare with the preset loaded (the query string Compare reads). */
export function presetHref(base: string, p: Preset): string {
  const root = base.replace(/\/$/, "");
  const scope = p.scope === "career" ? "scope=career&" : "";
  const picks = p.picks.join(",");
  return `${root}/compare/?${scope}p=${picks}`;
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
