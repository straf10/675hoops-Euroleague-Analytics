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
const ref = (type: string, r: Ref) => ({ "@type": type, name: r.name, url: r.url });
const league = () => ({
  "@type": "SportsOrganization",
  name: "EuroLeague",
  url: "https://www.euroleaguebasketball.net",
});

interface ClubInput extends Ref {
  /** The players in the club's roster that have a page; omitted when empty. */
  athletes?: Ref[];
  /**
   * Other names of the club: its short name and, for a Greek club, its Greek name. Omitted when none;
   * one name is given as a string, more as a list.
   */
  alternateName?: string | (string | undefined)[];
}

export function sportsTeam(club: ClubInput): JsonLdObject {
  const alt = [club.alternateName].flat().filter((n): n is string => Boolean(n));
  return {
    "@context": CONTEXT,
    "@type": "SportsTeam",
    name: club.name,
    ...(alt.length ? { alternateName: alt.length === 1 ? alt[0] : alt } : {}),
    sport: SPORT,
    url: club.url,
    memberOf: league(),
    ...(club.athletes?.length ? { athlete: club.athletes.map((a) => ref("Person", a)) } : {}),
  };
}

interface PlayerInput extends Ref {
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

interface CoachInput extends Ref {
  /** The club the coach is with now, when the coach is in the latest season and the club has a page. */
  currentClub?: Ref;
}

/**
 * A head coach as a Person. Past clubs are not affiliations (the coach has left them); only the
 * current club is worksFor, and only when it is known.
 */
export function coach(c: CoachInput): JsonLdObject {
  return {
    "@context": CONTEXT,
    "@type": "Person",
    name: c.name,
    url: c.url,
    jobTitle: "Head coach",
    ...(c.currentClub ? { worksFor: ref("SportsTeam", c.currentClub) } : {}),
  };
}

/** The arena a game is played at. The address only when the schedule gives one; never estimated. */
export interface Venue {
  name: string;
  address?: string;
}

export interface GameInput {
  name: string;
  /** The game's page on the site. */
  url: string;
  description: string;
  /** Absolute URL of the social card. */
  image: string;
  /** The short form of the name (the title), when it differs from `name`. */
  alternateName?: string;
  /**
   * ISO 8601 with a time zone (2027-10-01T18:00:00Z) when the tip-off time is known; a bare date
   * (2027-10-01) while it is not. Never a made-up time.
   */
  startDate: string;
  eventStatus: "completed" | "scheduled";
  home: Ref;
  away: Ref;
  location: Venue;
}

const EVENT_STATUS = {
  completed: "https://schema.org/EventCompleted",
  scheduled: "https://schema.org/EventScheduled",
} as const;
const OFFLINE = "https://schema.org/OfflineEventAttendanceMode";

/** The venue as a schema.org Place; the PostalAddress only when there is an address. */
function place(v: Venue): JsonLdObject {
  return {
    "@type": "Place",
    name: v.name,
    ...(v.address ? { address: { "@type": "PostalAddress", streetAddress: v.address } } : {}),
  };
}

/**
 * One EuroLeague game as a SportsEvent. No superEvent: a nested season event would carry no date
 * or place of its own, and Search Console reads it as a second, broken event. No endDate (not in
 * the data) and no offers (the site sells no tickets).
 */
export function sportsEvent(g: GameInput): JsonLdObject {
  return {
    "@context": CONTEXT,
    "@type": "SportsEvent",
    name: g.name,
    ...(g.alternateName ? { alternateName: g.alternateName } : {}),
    url: g.url,
    description: g.description,
    image: g.image,
    sport: SPORT,
    startDate: g.startDate,
    eventStatus: EVENT_STATUS[g.eventStatus],
    eventAttendanceMode: OFFLINE,
    location: place(g.location),
    homeTeam: ref("SportsTeam", g.home),
    awayTeam: ref("SportsTeam", g.away),
    organizer: league(),
  };
}

interface DownloadFile {
  name: string;
  /** Absolute URL of the file. */
  contentUrl: string;
  encodingFormat: string;
  compressionFormat?: string;
}

interface DatasetInput {
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
  /** A licence URL, or a terms-of-use URL when the data is not ours to license. */
  license?: string;
  /** The organization whose data this is, when it is not the site's own. */
  isBasedOn?: Ref;
  /** A credit line for the source, when the data is not the site's own. */
  creditText?: string;
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
    ...(d.isBasedOn ? { isBasedOn: ref("Organization", d.isBasedOn) } : {}),
    ...(d.creditText ? { creditText: d.creditText } : {}),
    distribution: d.distribution.map((f) => ({
      "@type": "DataDownload",
      name: f.name,
      contentUrl: f.contentUrl,
      encodingFormat: f.encodingFormat,
      ...(f.compressionFormat ? { compressionFormat: f.compressionFormat } : {}),
    })),
  };
}

/** One step of a breadcrumb trail: its label and absolute URL. */
export interface Crumb {
  name: string;
  url: string;
}

/** The breadcrumb trail of a page, first step first (the home page is the first step of every trail). */
export function breadcrumbList(trail: Crumb[]): JsonLdObject {
  return {
    "@context": CONTEXT,
    "@type": "BreadcrumbList",
    itemListElement: trail.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.name,
      item: c.url,
    })),
  };
}
