// Positions as the site groups them. The EuroLeague people listing gives every player one of
// Guard, Forward or Center per season; the exporter writes it as "G" | "F" | "C" on each season
// row (`pos`, absent when the player has no listing at all). The site shows Guard / Forward / Centre.

export type SourcePos = "G" | "F" | "C";
export type Position = "Guard" | "Forward" | "Centre";

export const POSITIONS: Position[] = ["Guard", "Forward", "Centre"];

const BY_SOURCE: Record<SourcePos, Position> = { G: "Guard", F: "Forward", C: "Centre" };

/** Old display names, so links made before the rename (`?pos=Wing`, `?pos=Big`) still resolve. */
export const LEGACY_POSITION = new Map<string, Position>([
  ["Wing", "Forward"],
  ["Big", "Centre"],
]);

/** Guard / Forward / Centre for a season row's `pos`, or null when the player has no listing. */
export const position = (pos: string | null | undefined): Position | null =>
  pos != null && pos in BY_SOURCE ? BY_SOURCE[pos as SourcePos] : null;
