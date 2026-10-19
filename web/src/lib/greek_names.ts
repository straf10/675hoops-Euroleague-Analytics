// Greek names of the Greek EuroLeague clubs, keyed by the team code the stats use (PAO is the code
// the site's club list carries for Panathinaikos; PAN is its EuroLeague API source code, listed too
// so either lookup works). Only the two Greek EuroLeague clubs; the site is EuroLeague only.
// Used as schema.org alternateName on the team page.
export const GREEK_CLUB_NAMES: Record<string, string> = {
  OLY: "Ολυμπιακός",
  PAO: "Παναθηναϊκός",
  PAN: "Παναθηναϊκός",
};
