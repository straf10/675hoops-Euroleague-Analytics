// Positions as the site groups them. The EuroLeague people listing gives every player one of
// Guard, Forward or Center per season; the exporter writes it as "G" | "F" | "C" on each season
// row (`pos`, absent when the player has no listing at all). The site shows Guard / Wing / Big.

export type SourcePos = "G" | "F" | "C";
export type Position = "Guard" | "Wing" | "Big";

export const POSITIONS: Position[] = ["Guard", "Wing", "Big"];

const BY_SOURCE: Record<SourcePos, Position> = { G: "Guard", F: "Wing", C: "Big" };

/** Guard / Wing / Big for a season row's `pos`, or null when the player has no listing. */
export const position = (pos: string | null | undefined): Position | null =>
  pos != null && pos in BY_SOURCE ? BY_SOURCE[pos as SourcePos] : null;
