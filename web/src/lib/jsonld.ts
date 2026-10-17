// schema.org builders for the site's pages. Pure: plain data in, plain objects out (no Astro
// imports). Pages pass absolute URLs, built from Astro.site the way Base.astro builds its canonical.
// Only the top-level object carries @context; nested references are bare {@type, name, url}.

export type JsonLdObject = Record<string, unknown>;

/** A reference to another entity by name and absolute URL. */
export interface Ref {
  name: string;
  url: string;
}

const CONTEXT = "https://schema.org";
const SPORT = "Basketball";
const SCHEDULED = "https://schema.org/EventScheduled";
const ref = (type: string, r: Ref) => ({ "@type": type, name: r.name, url: r.url });
const league = () => ({ "@type": "SportsOrganization", name: "EuroLeague" });

export interface ClubInput extends Ref {
  /** The players in the club's roster that have a page; omitted when empty. */
  athletes?: Ref[];
}

export function sportsTeam(club: ClubInput): JsonLdObject {
  return {
    "@context": CONTEXT,
    "@type": "SportsTeam",
    name: club.name,
    sport: SPORT,
    url: club.url,
    memberOf: league(),
    ...(club.athletes?.length ? { athlete: club.athletes.map((a) => ref("Person", a)) } : {}),
  };
}

export interface PlayerInput extends Ref {
  /** The clubs the player belongs to now. */
  affiliation?: Ref[];
  /** Only when the page has them; never estimated. */
  heightCm?: number;
  birthDate?: string;
  nationality?: string;
}

export function person(p: PlayerInput): JsonLdObject {
  return {
    "@context": CONTEXT,
    "@type": "Person",
    name: p.name,
    url: p.url,
    ...(p.affiliation?.length ? { affiliation: p.affiliation.map((t) => ref("SportsTeam", t)) } : {}),
    ...(p.heightCm !== undefined
      ? { height: { "@type": "QuantitativeValue", value: p.heightCm, unitCode: "CMT" } }
      : {}),
    ...(p.birthDate ? { birthDate: p.birthDate } : {}),
    ...(p.nationality ? { nationality: { "@type": "Country", name: p.nationality } } : {}),
  };
}

export interface GameInput {
  name: string;
  /** The game's page on the site, when it has one. */
  url?: string;
  /** ISO 8601 with timezone, e.g. 2027-10-01T18:00:00Z. */
  startDate: string;
  home: Ref;
  away: Ref;
  /** The competition's season label, e.g. "2027-28". */
  season?: string;
  /** Venue name, only when known. */
  location?: string;
}

export function sportsEvent(g: GameInput): JsonLdObject {
  return {
    "@context": CONTEXT,
    "@type": "SportsEvent",
    name: g.name,
    ...(g.url ? { url: g.url } : {}),
    sport: SPORT,
    startDate: g.startDate,
    eventStatus: SCHEDULED,
    homeTeam: ref("SportsTeam", g.home),
    awayTeam: ref("SportsTeam", g.away),
    organizer: league(),
    ...(g.season ? { superEvent: { "@type": "SportsEvent", name: `EuroLeague ${g.season}` } } : {}),
    ...(g.location ? { location: { "@type": "Place", name: g.location } } : {}),
  };
}

export interface DownloadFile {
  name: string;
  /** Absolute URL of the file. */
  contentUrl: string;
  encodingFormat: string;
  compressionFormat?: string;
}

export interface DatasetInput {
  name: string;
  description: string;
  /** Absolute URL of the page that describes the dataset. */
  url: string;
  /** Absolute URL of the site, for the creator. */
  siteUrl: string;
  /** ISO date (YYYY-MM-DD), when the files were built. */
  dateModified?: string;
  /** ISO 8601 interval, e.g. "2026/2027". */
  temporalCoverage?: string;
  distribution: DownloadFile[];
  /** Only when the repository grants a license; the default is none. */
  license?: string;
}

export function dataset(d: DatasetInput): JsonLdObject {
  return {
    "@context": CONTEXT,
    "@type": "Dataset",
    name: d.name,
    description: d.description,
    url: d.url,
    creator: { "@type": "Organization", name: "6.75 Analytics", url: d.siteUrl },
    isAccessibleForFree: true,
    ...(d.dateModified ? { dateModified: d.dateModified } : {}),
    ...(d.temporalCoverage ? { temporalCoverage: d.temporalCoverage } : {}),
    ...(d.license ? { license: d.license } : {}),
    distribution: d.distribution.map((f) => ({
      "@type": "DataDownload",
      name: f.name,
      contentUrl: f.contentUrl,
      encodingFormat: f.encodingFormat,
      ...(f.compressionFormat ? { compressionFormat: f.compressionFormat } : {}),
    })),
  };
}
