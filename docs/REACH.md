# Reach: growing the audience

The site is 675hoops.com: EuroLeague 2026-27 win predictions, the player and team stats behind
them, and the coaches. This plan covers how people find it (search, feeds, markup) and how the
work reaches them (posts, communities, outreach). It is EuroLeague only. No GBL pitch goes out
until the owner decides on one.

Principles:

- **The record is the pitch.** Predictions are logged before tip-off and the log is append-only
  (`predictions/*.csv`). Posts quote the record as it stands, wins and losses both, and only what
  the forecast record page shows.
- **Nothing is posted by code.** The site and its feeds are read-only. Posting, emailing and
  submitting to services are done by the owner from the owner's accounts.
- **No new tracking.** The site collects no analytics today, and Sentry takes errors only. Any
  audience measurement is decision 10 below.
- **Design.** `docs/DESIGN.md` ("The Quiet Reference"): neutral paper, one typeface, colour only on
  data. Share features add no visual weight.

## What is already in place

Done in the technical SEO work:

- Every indexable page has a unique title and description, a canonical URL, an Open Graph and
  Twitter card, and a BreadcrumbList. Game pages have SportsEvent markup, player pages Person,
  team pages SportsTeam (with the Greek name for the two Greek clubs), coach pages Person with
  `jobTitle` "Head coach" and `worksFor` for the current club only, and the downloads page Dataset.
- Hub titles name the search terms people type: "EuroLeague predictions 2026-27", "EuroLeague
  standings projection", "EuroLeague player stats", "EuroLeague coaches".
- Game titles read "Team A 86–78 Team B: EuroLeague, 16 Oct 2026" once played, and "Team A vs
  Team B: EuroLeague, 16 Oct 2026" before tip-off.
- `sitemap-index.xml` carries `<lastmod>` from the data build date. `robots.txt` points to it.
- A noindex 404 page, and zero broken internal links in the built site.
- An RSS 2.0 feed of the predictions at `/feed.xml`, one item per round, linked from every page's
  `<head>` for feed readers. It lists only calls logged before tip-off.
- Share cards (1200 x 630 PNG): `/cards/round-N-recap.png` (a round's calls and how they did),
  `/cards/games/{id}.png` (an upcoming game), and `/cards/players/{slug}.png` (a player in the
  live season). The posts use these.

## Prioritised plan

Effort is the owner's time unless marked "agent", which means a code change in the repo.

### Top 10, in order

1. **Verify the site in Google Search Console and submit the sitemap.** Owner, one-off, 30 min.
   Verify by DNS TXT record on the domain (the URL-prefix method needs the HTML file, which is
   not in the build). Then submit `https://675hoops.com/sitemap-index.xml`. "Discovered, currently
   not indexed" in the first month is normal for new sites and clears as the domain earns links.
2. **Import the property into Bing Webmaster Tools and submit the sitemap.** Owner, one-off,
   15 min. Bing's import from Search Console takes a minute, and Bing's results feed some
   assistants, so it is cheap reach.
3. **Post the round card once a week on X and Bluesky.** Owner, 20 min per round, weekly during
   the season. Use `/cards/round-N-recap.png` as the image, with the round's game-page links in the
   post. Posts go up the same day the round's predictions do, with the record so far, so a loss is
   visible too. Agent can draft the post text from the round data if asked; the owner publishes.
4. **Post a weekly thread on r/Euroleague.** Owner, 30 min per round. Check the subreddit's
   self-promotion rules first. Post the round's calls as text, with the link to the round's card
   and the running record. Answer questions in the thread. Start with one round to see whether it
   is welcome before making it weekly.
5. **Post a Greek-language note on the Greek clubs' calls.** Owner writes it, 1 h to start, then
   weekly alongside item 4. Olympiacos and Panathinaikos fans follow their clubs' calls first.
   Greek forums and fan groups (the owner picks which ones) take a post about the calls, not a
   link dump. The Greek club names are already in the markup.
6. **Journalist outreach.** Owner, 3 h to build a list of about 20 EuroLeague writers and
   EuroLeague-focused outlets (international and Greek), then 1 h a week. One short email per
   person: what the site predicts, the record so far, the page for that writer's team, and an
   offer of a data check on any game they cover. One follow-up at most.
7. **Podcast pitches.** Owner, 2 h to list about 10 EuroLeague podcasts and their contact routes,
   then 30 min per pitch. Offer a short episode segment (a round's calls, a result that went
   against us) rather than a plug.
8. **Feed discovery and validation.** Owner, 30 min: check `/feed.xml` in the W3C Feed Validator and
   a feed reader, then submit it to one or two feed directories the owner already uses. Agent,
   1 h, if wanted: a row on the Downloads page pointing to the feed. The feed stays EuroLeague only.
9. **Embeddable round widget.** Agent, 1 to 2 days: a read-only `/embed/round-N/` page, sized for
   an iframe, with the round's calls and the record, no tracking, no scripts beyond the page's own,
   and the same colour rules as the site. Owner reviews against `docs/DESIGN.md` before it ships.
   Embeds bring links back without anyone visiting first, so this comes after items 1 to 8.
10. **Decide on audience measurement.** Owner, decision in 30 min; agent, 1 h to add it if chosen.
    Options: no analytics (honest, but the plan cannot be measured beyond Search Console); a
    cookieless, privacy-friendly counter with no personal data (for example Cloudflare Web
    Analytics, since the site already sits on Cloudflare Pages); or a self-hosted log summary.
    Whichever is chosen is described in the About page's privacy wording first.

### Later, not yet scheduled

- Played-game share cards (`/cards/games/{id}.png` exists only for upcoming games). Needs a new
  route and a design review. Skipped for now.
- Player to coach links on player pages. Blocked until the Players page UI work is merged.
- GBL. Needs the owner's go-ahead; it would need Greek-language pages, not only markup.
- Page speed and Lighthouse. Owned by the performance work, not this plan.

## How to tell it works

- Search Console: impressions for the hub titles ("EuroLeague predictions", "EuroLeague player
  stats") and the first game pages that rank for "Team A vs Team B" queries. Tracked monthly.
- Feed: subscribers, if a feed reader count is available, and the number of times the feed is
  fetched in Cloudflare logs (if decision 10 includes logs).
- Social and Reddit: which round posts got replies, not likes. Replies show that people read the
  calls.
- Outreach: replies per email sent. Expect a low rate; one replied journalist is a good month.
