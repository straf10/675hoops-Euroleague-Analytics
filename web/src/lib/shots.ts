// One season's shot attempts, packed column-wise (stats export `seasons/{season}/attempts.json`).

export interface Attempts {
  season: number;
  label: string;
  validated: boolean;
  radius: number;
  bits: Record<"made" | "three" | "fastbreak" | "second_chance" | "band" | "period", number>;
  bands: string[];
  teams: [code: string, name: string][];
  /** [id, name, slug, team code] */
  players: [string, string, string, string][];
  x: number[]; // court centimetres
  y: number[];
  flags: number[];
  player: number[];
  team: number[];
  opp: number[];
}
