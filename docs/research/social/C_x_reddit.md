# Agent C: X (Twitter) and Reddit research

Started 2026-11-03. Read-only on code. Sources listed per row. Access note: x.com and reddit.com direct fetches are blocked for this agent (reddit.com/old.reddit.com return "unable to fetch"; redlib mirror returned 403). Data comes from search snippets, Hive Index, redship, and third-party writeups.

## Scoreboard

| iter | lead | new data points | cumulative | accounts profiled (cum) | notes |
|---|---|---|---|---|---|
| 1 | r/Euroleague size and activity (Hive Index) | 4 | 4 | 0 | ~41K members; +24%/yr; ~31 flaired posts/mo; no posting rules listed |
| 2 | r/NBA [OC] comment-sentiment post; r/nbadiscussion size | 5 | 9 | 0 | 2,608 pts, 985 comments; methodology in body; r/nbadiscussion ~1.2M members |
| 3 | X EuroLeague stats (blocked, 402); The Margin calibration page | 4 | 13 | 1 (@themarginsports) | Public misses and failed models on-page |
| 4 | Preseason projections (Opta, ESPN, Sportradar); retract Utah State 69.4% | 3 | 16 | 1 | 69.4% claim removed: fetched page has no accuracy figures |
| 5 | r/Euroleague chart posts; Giasemidis shot-data errors | 3 | 19 | 1 | r/Euroleague ~38K (GummySearch) vs ~41K (Hive); shot labels unreliable |
| 6 | EuroLeague efficiency-landscape writers (Vujovic, Hudl, EL stats reviews) | 4 | 23 | 1 | Medium 403; snippet-based |
| 7 | Reddit self-promo norms (redship guide) | 4 | 27 | 1 | 10% guideline; removal triggers; enforcement ladder |
| 8 | [OC] norms (r/dataisbeautiful mirror rules) | 3 | 30 | 1 | Source and tool named in first comment; mirror, dated |
| 9 | X engagement by format (Ordinal fetch; Socialinsider) | 5 | 35 | 1 | Image 0.79 > text 0.68 > video 0.54%; 100-200 chars best |
| 10 | X analyst profile (Whitehead, @crumpledjumper); thread example | 4 | 39 | 2 (+@crumpledjumper) | Social Blade 403; gated profiles noted |
| 11 | EuroLeague platform footprint (women's X 45,916; league 47.1M, 1.49B video views) | 5 | 44 | 3 (+@EuroLeagueWomen) | Men's X handle not obtained |
| 12 | Greek subreddit (none found); The Model; Neil Paine Elo | 4 | 48 | 3 (+2 sites) | The Model numbers unverified (placeholders) |
| 13 | @notbpod tracker profile | 5 | 53 | 4 (+@notbpod) | 35.7K followers; ~5.1 posts/day; 1.90% ER |
| 14 | @UnderdogNBA tracker profile; gated EuroLeague/CTG/Analyst | 5 | 58 | 5 (+@UnderdogNBA) | 48 posts/day; 14 of top 20 image posts |
| 15 | Enjoy Basketball newsletter (X and Reddit growth) | 4 | 62 | 5 | Date conflict (2025 page, "12 months") |
| 16 | r/nba snapshot 2026-04-15; only [OC] LVP post | 4 | 66 | 5 | LVP [OC] 4,613 pts with box-score method |
| 17 | Reddit best-time vendor study (redditapis) | 4 | 70 | 5 | Vendor with API sales; ET medians |
| 18 | Upvote.net r/all study (vendor with stake) | 5 | 75 | 5 | Size dominates; link posts highest median; question titles -16% |
| 19 | r/nbadiscussion rule posture (mod posts) | 4 | 79 | 5 | In-season no hot takes; off-season OC allowed |
| 20 | X link-post reach (OpenTweet 60 accounts) | 4 | 83 | 5 | Median ratio 1.05; conflicting beehiiv claim unverified |
| 21 | X hashtag effect (blog only) | 2 | 85 | 5 | BELOW BAR (gain 2 < median 4); weak sourcing |
| 22 | r/nba weekly Friday self-promo thread rules | 5 | 90 | 5 | Paywall/sign-up links barred; activity requirement |
| 23 | r/dataisbeautiful removal reasons (Olson 2016) | 3 | 93 | 5 | BELOW BAR (gain 3 < median 4); data is 2013-2016 |
| 24 | ESPN BPI retrospective (2015); BPI active 2026; 538 closed | 4 | 97 | 5 (+2 orgs) | No full track record anywhere; Silver Bulletin gap |
| 25 | Vujovic named series (titles and dates) | 4 | 101 | 5 | Snippet-based titles; no 2026-27 posts found |
| 26 | Paobcgr game-stats graphics lead | 1 | 102 | 5 (146K claim unverified) | BELOW BAR; LunarCrush gated, dried up |
| 27 | EuroLeague copyright and video scale (2.27B vs 1.49B) | 4 | 106 | 5 | No fan content policy found; conflict of scopes |
| 28 | Reddit 10% guideline status; subreddit caps | 3 | 109 | 5 | BELOW BAR (gain 3 < median 4); official Reddit page blocked |
| 29 | r/dataisbeautiful 2026 snapshot (methodology vs score) | 4 | 113 | 5 | Top [OC] posts had no methodology line |
| 30 | X best times and thread split (OpenTweet, Sprout) | 4 | 117 | 5 (+OpenTweet not an account) | Vendor timing; threads 4-7 tweets reportedly +35% |

Accounts profiled with figures (X handles): @themarginsports, @crumpledjumper, @EuroLeagueWomen, @notbpod, @UnderdogNBA. Reddit communities: r/Euroleague, r/nba, r/nbadiscussion, r/dataisbeautiful. Gated or blocked and not counted: @euroleague, @cleaningtheglass, @theanalyst, @Paobcgr (unverified), @noahchestnut (thread only).

Bar note: iterations 21, 23, 26 and 28 fell below the median gain (4). Those leads were weak or blocked; reported as-is rather than padded.

## Iteration log

### Iter 1: r/Euroleague size and activity
- Members about 41K (approx), +8K in past year, +24.2%/yr. Source: https://thehiveindex.com/communities/r-euroleague/ (read 2026-11-03, synced 10/27/2026)
- Monthly new members peaked at 1K (May 2026), low 419 (Aug 2026), 777 (Sep 2026). Same source.
- Flair counts past month: 17 EuroLeague, 14 EuroCup (about 31 flaired posts). Same source.
- Most-listed threads are match threads (e.g. "POST MATCH THREAD") and "Homes of the EuroLeague Teams". Same source.
- Rules: Hive Index says no posting rules are stated (it does not replicate the sidebar). Direct rules page not reachable (old.reddit.com and www.reddit.com blocked, redlib mirror 403). Sidebar still needs manual check.
- Site-wide self-promo norm: 10% self-promo guideline (9:1 contribution ratio) per redship: https://redship.io/blog/reddit-self-promotion-rules (read 2026-11-03). Subreddit rules are stricter, never looser (same source).

### Iter 2: r/NBA and r/nbadiscussion OC data posts
- Post "[OC] I analyzed 1.57 million r/NBA comments to find out who this sub hates most" by u/B1ackmamba99: 2,608 points, 985 comments, posted about late May/June 2025 (sentinel snapshot dated 2026-02-17). Methodology in post: Arctic Shift API, 6.9M comments (Oct 2024-Jun 2025), 1.57M mentioning 111 players, LLM classification with ~96% accuracy on 500 hand-labeled comments, links to Streamlit dashboard and GitHub. Source: https://reddit.sentinel-team.org/posts/1r6kzp5/snapshots/2026-02-17T20%3A51%3A28.553312Z (read 2026-11-03). Note: an earlier search attributed it to u/gridironk with 2,382 pts; the sentinel page is the more direct source and is used here.
- r/nbadiscussion: about 1.2M members, +26k/yr (2.1%); flair counts: Team Discussion 3, Statistical Analysis 2 in sample. Source: https://gummysearch.com/r/nbadiscussion (read 2026-11-03; time window not stated).
- Low-engagement analytics example: "Quantifying NBA 'shot-making'" on r/nbadiscussion with a Methodology section had 17 upvotes at snapshot. Source: search snippet only (WebSearch, 2026-11-03). Shows methodology alone does not guarantee votes.
- Mod FAQ states high-quality discussion requires extra effort; low-effort posts draw more votes. Source: search snippet of r/nbadiscussion mod posts (2026-11-03).

### Iter 3: EuroLeague X stats accounts (attempt) and NBA forecast accounts
- x.com/EuroLeague fetch returned HTTP 402; X is blocked for WebFetch. Searches for EuroLeague stats/analyst X handles returned no handles or follower counts. No X data from this lead. Not counted as data.
- Forecast-record transparency, The Margin (X: @themarginsports, run by McConnell Digital): public calibration page with 1,220 held-out NBA live-totals games (average miss fell 18.2 to 11.2 pts), 80% bands covering 81.1% of NFL/college games, a NBA moneyline bucket at 90%+ that won about 2 in 3 (admitted overconfident), and a retired MLB model "pulled" after backwards testing. Source: https://themargin-89y.pages.dev/calibration/ (read 2026-11-03). Shows losses and failed models on-page.
- Greek analyst lead: Christos Marmarinos (ex-Olympiacos staff, NewStats.eu per ACG bio) - unverified as an X or stats-graphics account. Sources: https://theinstitute.gr/fellows/christos-marmarinos/ (snippet, 2026-11-03). Not profiled further.

### Iter 4: Preseason forecast publishing (Opta, ESPN, Sportradar) and a retracted claim
- Retraction: an earlier search snippet said Utah State "NBA Model Health" reports 69.4% straight-up accuracy for 2025-26. The fetched page (https://macfax.usu.edu/nba/model-health, read 2026-11-03) contains NO accuracy figures, so the 69.4% figure is discarded.
- Opta's supercomputer publishes 2026-27 team projections on a NBA Predictions page, updated through the season; dated Oct 14 per search snippet. Source: https://theanalyst.com/?p=264152 (snippet, 2026-11-03). No accuracy tracking shown in snippet.
- Sportradar AI simulation: 50,000 simulations, picked OKC to repeat (preseason). Source: https://soloazar.com/en/category/sportsbook/sportradars-ai-simulation-predicts-oklahoma-city-thunder-to-repeat-as-2026-nba-champions (snippet, 2026-11-03). Preseason-only, no record shown.
- ESPN publishes "2025-26 season win projections all 30 teams" as a list article. Source: https://africa.espn.com/nba/story/_/id/46521096/nba-2025-2026-season-win-projections-all-30-teams (snippet, 2026-11-03).


### Iter 5: r/Euroleague chart posts and official shot-data caveat
- r/Euroleague size per GummySearch: about 38k members; most common flairs are :el: and :ec: (EuroLeague/EuroCup). Page updated 2026-06-21. Source: https://gummysearch.com/r/Euroleague/ (snippet, 2026-11-03). Conflicts with Hive Index ~41K (2026-10-27); report a range of 38-41K.
- Chart post found in mirror index: "Efficiency Landscape in Euroleague as of Round 26" (r/Euroleague, mirror at axebps-redlib.hf.space, date unclear, OC status not verified). Fetch failed (mirror loading page). Source: https://axebps-redlib.hf.space/r/Euroleague/comments/1ikop9x/efficiency_landscape_in_euroleague_as_of_round_26 (snippet 2026-11-03). Treat as unverified.
- Data-quality caveat: Giasemidis (blog, 2022-11-06) found EuroLeague official shot data labels mismatched with locations (3PT shots in paint, 2PT beyond arc), systematic in every season since 2010; cause unknown. Source: https://giasemidis.github.io/2022/11/06/euroleague-shots-data-errors.html (read 2026-11-03). Implication for us: validate shot-type labels before publishing shot-based graphics.

### Iter 6: Euroleague efficiency-landscape writers (Medium, Hudl Instat, EuroLeague stats reviews)
- Vujovic "EuroLeague PlusMinus" Medium series (2025/26): net-rating and "Efficiency Landscape" chart, round-by-round recaps, home vs away splits. Source: search snippet, https://medium.com/@vujke (2026-11-03). Fetch returned 403; cadence and follower count not verified.
- Hudl Instat 2025/26 EuroLeague review: usage-vs-efficiency charts, offensive and defensive ratings per 100 possessions; "beyond the arc" Europe piece. Sources: https://www.hudl.com/blog/euroleague-2025-26-review-hudl-instat and https://www.hudl.com/blog/beyond-the-arc-what-actually-wins-in-europe (snippets, 2026-11-03).
- EuroLeague's own "stats review" series (powered by Sportradar) on offensive efficiency, e.g. "offensive efficiency continues to rise" in 2025-26 opening rounds. Source: https://www.euroleaguebasketball.net/euroleague/news/stats-review-offensive-efficiency-in-the-euroleague-continues-to-rise (snippet; fetch 429). Shows the league itself posts efficiency charts as a recurring feature.
- Format evidence (2 sources agree): efficiency or net-rating "landscape" charts with round recaps are the standard EuroLeague analytics format (Vujovic, EuroLeague stats reviews, Hudl).

### Iter 7: Reddit self-promotion norms (redship guide, read 2026-11-03)
- Guide "The complete guide to Reddit self-promotion rules in 2026" (published 2026-03-15, updated 2026-07-02): 90/10 benchmark, attributed to Reddiquette; some subs reportedly enforce closer to 99/1. Source: https://redship.io/blog/reddit-self-promotion-rules-2026
- Removal triggers listed: promotional language ("the best solution"), accounts whose history is only product links, the same content cross-posted to several subs, and many links in a short window (shadow-ban risk). Same source.
- Enforcement ladder (removal, sub shadow ban, sitewide shadow ban, sub ban, account suspension), with the note that sitewide shadow bans are rarely appealable. Same source. Practical rule for us: never post the same chart in several subs in one day; keep a participation history.

### Iter 8: [OC] norms from r/dataisbeautiful (mirror of the sub rules)
- [OC] requires the self-made visualization, the data source and the software tool named in the first top-level comment; vague sources ("Wikipedia") rejected; a remix must be substantially changed. Source: mirror search snippets for https://rl.klein.ruhr/r/dataisbeautiful/wiki/index and /wiki/rules/rule2 (2026-11-03). Mirror is unofficial and the wiki snapshot may be old; the 2014 mod post also states this rule. Treat as a template for a methodology comment, not verbatim sidebar text.
- Fetch attempts: rl.klein.ruhr (DNS fail), pol1.lr.ggtyler.dev (ECONNRESET), lr.in.psf.lt r/nbadiscussion in-season rules (TLS error). No direct r/nba or r/nbadiscussion rules text obtained; r/nba OC/flair text not verified.


### Iter 9: X engagement benchmarks by format (conflicting sources)
- Ordinal study (tryordinal.com, fetched 2026-11-03; posts Jan 2024-May 2026, sample size not stated): image posts ~0.79% (avg 18,334 impressions), text-only ~0.68% (avg 35,975 impressions), video ~0.54% (lowest). Threads are the highest format but the page text omits the figure. Engagement = (likes+replies+reposts+quotes)/impressions. Posts of 100-200 characters had highest engagement. Source: https://www.tryordinal.com/blog/twitter-x-engagement-data-study. Note: a search snippet of the same study listed threads 1.89%, image 0.99%, video 0.53%; those snippet numbers do not match the fetched page and are NOT used.
- Socialinsider 2026 benchmarks (fetched 2026-11-03): X engagement by followers 0.15% (2024), 0.12% (2025), 0.10% (Q3 2026); 70 posts/month for the average X account in 2025 (up from 50 in 2024). No format split. Source: https://www.socialinsider.io/social-media-benchmarks. Page date range is internally inconsistent (notes 2025 values labelled 2026).
- Cross-source read: video is not the advantage on X in either study (video lowest in Ordinal). Threads are highest per Ordinal's ranking, but the number is unverified. Confidence: medium (2 sources, one fetched).

### Iter 10: X analyst profile (Todd Whitehead) and thread example; Social Blade blocked
- Social Blade (socialblade.com/twitter/user/cleaningtheglass) returned 403. Cleaning the Glass X follower count not obtained. Ben Falk's NBA stats site is a paid subscription model (search snippets, 2026-11-03).
- Thread example: @noahchestnut (Noah Chestnut) 11-tweet thread on Cleaning the Glass as a subscription model, with several embedded stats screenshots; only view count shown (12,399); likes not visible. Source: https://threadreaderapp.com/thread/1063488415541288962.html (read 2026-11-03; no date on page).
- Todd Whitehead, X handle @crumpledjumper, described as a basketball data-viz creator ("data visualization king of basketball Twitter"). Interview dated 2022-11-22: simple, feed-readable visuals; hand-built physical charts (3-D Steph Curry 3PT shot chart from 2,974 trays; "40 Years of Draft Fits" fabric-and-button chart); borrows FiveThirtyEight's consistent headline and subheading format; no follower or per-post engagement figures. Source: https://nightingaledvs.com/meet-the-data-visualization-king-of-basketball-twitter-todd-whitehead/ (read 2026-11-03). Copyright note: original data graphics, no league footage.

## Synthesis so far (after iteration 10)

Baseline, with confidence and support. Sources are the iter-numbered entries above.

- **Posts per day (X):** Socialinsider reports an average of 70 posts/month for X accounts in 2025 (about 2-3/day), supported by one source only (iter 9). Confidence: low. Our rule of thumb of 1-2/day for a stats account is an estimate, not sourced.
- **Video vs image:** Ordinal (fetched, iter 9) ranks image 0.79% > text 0.68% > video 0.54% on impression-based engagement. Confidence: medium (one fetched study, sample size not stated). Implication: a static data graphic is the stronger default on X than video.
- **Threads:** Ordinal says threads are the highest format, but the figure is not in the fetched text. Posteverywhere claims 0.18-0.25% for threads vs 0.12% single tweets, source unclear (iter 9). Confidence: low.
- **Caption/post length:** Ordinal says 100-200 characters had the highest engagement (iter 9). Confidence: medium (one source).
- **Top topics:** match threads and efficiency or net-rating "landscape" charts on Reddit (iter 5, 6). Confidence: medium (2 sources).
- **Voice/tone:** data-first and methodology-led (The Margin, iter 3; the r/NBA sentiment post, iter 2); humour appears in top comments but not in the posts themselves (iter 2). Confidence: low.
- **Animation styles, hooks, hashtags, best times:** no sourced evidence yet. Gap, to address in iterations 11-20.
- **Forecast-record display:** The Margin shows misses, overconfident buckets and a pulled model on its page (iter 3). Confidence: medium (one source, fetched).
- **Reddit:** r/Euroleague ~38-41K members, ~31 flaired posts per month (iter 1, 5). Methodology comments are the norm for [OC] (iter 8, mirror-based).

### Iter 11: EuroLeague platform footprint (league-level X data)
- Men's EuroLeague main X handle and follower count NOT obtained (x.com 402; Social Blade 403). Search gives no verified figure.
- EuroLeague Women's X account (twitter.com/EuroLeagueWomen, from FIBA release): 45,916 followers, of a combined ~1.01M across Facebook 497,410, Instagram 188,442, TikTok 178,606, YouTube 77,800, X 45,916, Threads 21,276. Undated page. Source: https://www.fiba.basketball/en/events/euroleague-women-25-26/news/euroleague-women-surpasses-1-million-followers-on-social-media (read 2026-11-03). X is the smallest of the large platforms in that women's set, so X is a small channel for the league.
- Men's league, 2025-26 regular season (Eurohoops, 2026-05-08): 47.1M followers across the league and clubs; 1.49 billion video views on league-owned platforms (+1,067% vs 2021-22); 3B+ impressions. Platform split not given. Source: https://www.eurohoops.net/en/euroleague/1965635/2025-26-euroleague-regular-season-breaks-all-historic-records/ (read 2026-11-03). Implication: video is the league's main reach driver across platforms (video views dominate), though X's share is not broken out.
- Copyright: league footage/video is the league's own; we must not reuse it (see Rule 7).


### Iter 12: Greek Reddit communities (negative result) and NBA forecast-record sites
- Search for r/GreekBasketball or r/GreekBasket returned nothing; no such subreddit confirmed (search 2026-11-03). Basketball-wide r/Basketball covers EuroLeague among leagues (gummysearch.com/r/Basketball, snippet). Gap: no Greek subreddit found; Greek talk likely lives in r/Euroleague and r/Basketball or Greek-language forums (unverified).
- The Model (the-model.vercel.app/nba), read 2026-11-03: claims 1,106 NBA 2025-26 games tracked, "every miss published"; shown rates moneyline 65.1%, ATS 59.8%, overall 62.5%. The headline counters show 0.0 (placeholder/loading problem). No methodology summary, no log-loss or Brier. Treat the rates as UNVERIFIED until the receipts table is checked. Shows the "publish every miss" claim without a published method.
- Neil Paine Elo forecast (Substack, June 14, 2026; paid): Monte Carlo playoff/title odds, team ratings in prose plus Flourish chart; no last-season Elo accuracy reported. Source: https://neilpaine.substack.com/p/2025-26-nba-elo-forecast-and-player (read 2026-11-03). Paid newsletter, not an X feed.


### Iter 13: X NBA analytics account with a tracker profile (@notbpod, Numbers On The Board)
- Profile: Numbers On The Board, X @notbpod. Fetched from socialpruf.com (read 2026-11-03; window 2025-11-03 to 2026-11-03): 35.7K followers; 1.87K posts in 12 months = about 5.1 posts/day (about 36/week, my calculation); average engagement rate 1.90% (definition not stated); 638K likes (about 341 per post), 11.4K comments, 34.1M impressions. Source: https://socialpruf.com/x/notbpod
- Conflict: a search snippet from the same site gave 31.6K followers and 1.83%. The fetched page is the later figure and is used here.
- Format mix and best posts NOT shown on the tracker. Gap: need post-level examples for this account. Its content type (graphics vs opinion) is unverified.
- Tier lesson: a 35.7K-follower NBA stats account posting about 5 times a day is the reference cadence in this sample. Single source, medium confidence.
- Seth Partnow and Zach Harper are named only in low-quality listicles (brainmindsociety fetch failed, certificate expired). Not profiled.


### Iter 14: Brand-stats X accounts via socialpruf (EuroLeague, Cleaning the Glass, The Analyst gated; @UnderdogNBA profiled)
- socialpruf pages for @euroleague, @cleaningtheglass and @theanalyst are gated ("Get the full report"): no figures. Not counted.
- @UnderdogNBA (Underdog Fantasy brand account, not a stats creator), window 2025-11-03 to 2026-11-03 (socialpruf, read 2026-11-03): 765K followers; 17.4K posts (about 48/day, 334/week, my calculation); engagement rate 0.458% (formula inferred, not stated); about 734 likes/post; about 166K impressions/post; 14 of its top 20 posts include an image or graphic, 6 are text-only; top post is text-only at about 10.1M impressions. Source: https://socialpruf.com/x/UnderdogNBA (read 2026-11-03). Copyright note: brand's own graphics and some league footage; use only the format pattern.
- Key pattern: a high-volume NBA brand account where the top posts are mostly graphics and single text posts, not threads or video. Confidence: medium (single tracker, top-20 sample).

### Iter 15: Enjoy Basketball newsletter (growth channels and cadence)
- Enjoy Basketball (beehiiv case study, page dated 2025-04-07): 3 posts per week; launched March 2022; 10,000 subscribers in first 24 hours; 45,000+ after one year. Growth channels named: Twitter (X), Reddit, creator distribution; referral program planned later. Format: casual friend-style recaps with memes, GIFs, light takes; no charts or threads mentioned. Source: https://www.beehiiv.com/case-studies/enjoy-basketball (read 2026-11-03).
- Conflict noted: "12 months" claim does not match the 2025 publish date; treat growth timing as unverified.
- Their method: analytics on subscriber source and content performance, then doubling down on the channels that worked. Transferable for us (track which post type drives link clicks).


### Iter 16: r/nba top posts and the only [OC] data post (sentinel snapshot, 2026-04-15)
- Snapshot 64 of 174, r/nba, read 2026-11-03. Top 8 posts are news and tags: "[Highlight]" 7,711 pts / 800 comments; "[Haynes]" sourced news 1,354 / 560; "[Palmer]" 3,649 / 628; a text-only opinion post 6,507 / 581. Daily thread index 13 pts. Source: https://reddit.sentinel-team.org/subreddits/nba/snapshots/2026-04-15T17%3A09%3A57.65112Z
- The only [OC] post: "[OC] and the results are in for... LVP. LEAST Valuable Player." 4,613 pts / 243 comments; written award column citing box plus/minus, VORP and win shares, a ranked list. Same source. Shows a stats-led [OC] written as a long-form ranking can reach top-5 on r/nba. Confidence: medium (one snapshot, 9 posts).
- Title convention in top posts: bracketed source tags ([Highlight], [Haynes], [Palmer], [OC]). Same source.
- Rules: the snapshot lists none. Subscriber count not shown. Post ages ("202 days ago") do not match the snapshot date, so the timing is unreliable.

### Iter 17: Reddit posting-time study (vendor, redditapis.com)
- redditapis.com "Best Time to Post on Reddit in 2026" (published 2026-07-09, updated 2026-10-29): 6,600 top posts from 22 subreddits, trailing 12 months, times in US Eastern. Medians: best single hour 6pm ET (15,368), 4pm (12,767), 6am (12,295); 9am-noon block is the most common posting window but median 5,144. Weekend median 7,266 vs weekday 5,958; Sunday best day (8,938). Subreddit medians range from 71 (r/marketing) to 83,038 (r/pics). Source: https://www.redditapis.com/blogs/best-time-to-post-on-reddit-2026 (read 2026-11-03).
- Conflict of interest: the author sells a Reddit API and runs an affiliate program; the study is observational and top-posts only. Use the direction (late afternoon/evening ET, weekend) as a hypothesis to test, not as a rule.

### Iter 18: Upvote.net press release on r/all posts (vendor with a stake; flag strongly)
- Upvote.net (a company selling upvotes; TechBullion press release dated 2026-03-15; data 2026-03-11): 1,000 hot r/all posts from 831 subreddits. Median score by ET time: 9am-noon 6,479; 9pm-midnight 783; 5-8am 13,482 (n=14). Subreddit size was the strongest predictor: 10M+ subscriber subs median 7,578 vs under 500k 1,236. External-link posts had highest median score (3,015); video +78% over text; cross-posts +195%; question-style titles 16% worse than statements. Source: https://techbullion.com/?p=707903 (read 2026-11-03).
- Implication for r/Euroleague (~38-41K members, iter 1/5): the size effect points to a small ceiling per post, so expect lower absolute scores than r/nba. Statement titles beat question titles (single vendor, flagged).


### Iter 19: r/nbadiscussion rule posture (mod posts via snippets; full rules not fetched)
- In-season rules FAQ (mod post, Oct 2024): the sub excludes jokes and hot takes, and points users to other NBA subs for those. Source: https://lr.in.psf.lt/r/nbadiscussion/comments/1gafd4n/inseason_rules_faq_and_megathreads_for (search snippet, 2026-11-03; direct fetch failed with TLS error).
- Off-season: the sub loosens standards and allows high-effort, in-depth OC that compares or ranks players (recent mod post, snippet). Implication: our stats posts fit the off-season window better.
- A May 2026 mod rules update covering AI, gambling and hyperbole exists (title only, snippet). Content not read; flag as a pre-post check.
- Flair "Statistical Analysis" exists and is used for analysis posts (snippet). Source of the flair observation: search result for r/nbadiscussion (2026-11-03).
- r/Euroleague rules and flair text: not reachable. Mirrors tried: r-weld.vercel.app (404), axebps-redlib (loading page), cal1.lr.ggtyler.dev (connection refused). Gap: the match-thread and flair rules still need a manual sidebar check.

### Iter 20: X link-post reach (do links get suppressed?)
- OpenTweet data report (updated 2026-10-10; data 2026-10-10): 28,124 posts with synced impressions (13,815 with a link, 14,309 without); 60 accounts with at least 5 link and 5 no-link posts. Median per-account ratio of link to no-link impressions: 1.05 (Jan 1 to Oct 10, 2026); 1.07 since Musk's 2026-07-29 reply. Links did worse on 27 of 60 accounts. Authors say it is observational and mostly small accounts (median post about 50 impressions); threads excluded. Source: https://opentweet.io/answers/does-x-penalize-links-2026 (read 2026-11-03).
- Conflict: a beehiiv newsletter (roo.beehiiv.com) claims non-Premium link posts drop to zero median engagement since March 2026; the page returned 404 on fetch, so this claim is UNVERIFIED and not used.
- Musk statement (2026-07-29, via PPC Land snippet): X has not penalized links for over a year. Unverified second-hand, cited via https://ppc.land/x-drops-year-old-link-penalty-musk-tells-zuckerberg-on-platform/ (snippet).
- Ranking weights disagree (thekeyword: Reposts 20x, Replies 13.5x, Link clicks 11x, Bookmarks 10x, Likes 1x; a Medium post claims a 75x author-reply weight). Source weights are from blogs and the 2023 code; NOT used for decisions. Primary check: github.com/xai-org/x-algorithm.
- Practical rule: post the chart as a native image and put the site link in a reply or the caption, which avoids the link-vs-no-link question (the chart carries the value). Confidence: low on X link penalties, medium that link posts are not clearly penalized.

## Synthesis at iteration 20 (updated baseline)

Evidence base: 20 iterations, 9 X/Reddit leads profiled (X: @notbpod, @UnderdogNBA, @crumpledjumper, @noahchestnut, @themarginsports, @EuroLeagueWomen, plus gated @euroleague/@cleaningtheglass/@theanalyst; Reddit: r/Euroleague, r/nba, r/nbadiscussion, r/dataisbeautiful norms).

- **Posts per day (X):** 5.1/day for @notbpod (35.7K followers, tracker, 12 months); about 48/day for @UnderdogNBA (765K followers, brand account); Socialinsider average 70/month (about 2.3/day). Confidence: medium that a 35-40K stats account runs 3-6/day. Our target of about 1-2 X posts per day is below the sampled stats accounts, so it is a choice, not a norm.
- **Video vs image (X):** Ordinal fetched: image 0.79% > text 0.68% > video 0.54%. UnderdogNBA: 14 of its top 20 posts are image/graphic, 6 text. Confidence: medium. Graphics over video on X.
- **Threads:** Ordinal calls threads the highest format (figure missing); one thread example (@noahchestnut, 11 tweets, 12,399 views). Confidence: low.
- **Caption length:** 100-200 characters best (Ordinal, fetched). Confidence: medium, one source.
- **Top topics:** match threads and efficiency or net-rating charts (r/Euroleague, Hudl, EuroLeague stats reviews); r/nba LVP ranking [OC] (4,613 pts). Confidence: medium.
- **Voice:** data-first, with methodology disclosed (The Margin; r/NBA sentiment post 2,608 pts; dataisbeautiful OC norm). Humour sits in comments, not posts. Confidence: low-medium.
- **Forecast-record display:** The Margin publishes misses and admits overconfident buckets. The Model claims "every miss published" but its numbers render as placeholders (unverified). Confidence: medium.
- **Best times:** vendor studies (redditapis, Upvote.net) agree on weekend and late-afternoon ET, but both are commercial. Confidence: low.
- **Reddit size:** r/Euroleague 38-41K members, about 31 flaired posts/month. Reddit posting rules for r/Euroleague: not obtained.
- **Gaps:** animation styles, hook patterns, hashtags (X), and r/Euroleague sidebar rules remain unsourced.

### Iter 21: X hashtag effect (weak; blog-only)
- Hashtag Tools blog claims 1-2 hashtags earn about 21% more engagement than none, and 3+ hashtags about 17% less. Source: https://hashtagtools.io/blog/do-hashtags-actually-work-data-analysis-2026 (snippet, 2026-11-03). Not verified; no method shown. A DEV post cites "Feb 2026" research without a primary source (unverified).
- Unfollr and Wild & Free Tools: hashtags act as search labels more than reach boosters on X (blog claims, snippets). No study-based impression figure found.
- Use with caution: no source here is a primary study. Working rule for us: 0-2 hashtags.

### Iter 22: r/nba Weekly Friday Self-Promotion thread rules (mod post, sentinel snapshot)
- Mod post "Weekly Friday Self-Promotion and Fan Art Thread" by u/NBA_MOD, snapshot 2025-12-06 (post age 333 days, date conflict noted). Rules (paraphrased): no links to resellers or retailers; no donation or payment sites; no content behind a paywall or sign-up; content must be relevant to the NBA; posters must be active community members outside self-promotion; comments from accounts sharing a name with the promoted brand are removed; no spam in comments or DMs; removals and bans for breaches; questions to mod mail. Source: https://reddit.sentinel-team.org/posts/1peugid/snapshots/2025-12-06T02%3A59%3A03.358867Z (read 2026-11-03).
- Consequence for us: the r/nba route is the weekly thread, not the main feed; a paywall or sign-up on 675hoops would block the link; our account name matching the brand must not be the only commenter. Confidence: high for this sub's weekly-thread rules (one mod post, read directly).


### Iter 23: r/dataisbeautiful removal reasons (Olson, 2016; historic)
- Moderator Randal Olson (post dated 2016-03-18; removal data Jan 2013-Jan 2016): about 50% of removals were posts without a data visualization, about 40% without credit to the visualization's original author; sensational titles and reposts were edge cases. Source: https://randalolson.com/2016/03/18/why-posts-get-removed-from-rdataisbeautiful (read 2026-11-03). Old data (2013-2016) but the most concrete removal breakdown found. Use the rule (credit + visualization + source) not the percentages.

### Iter 24: forecast-record display (ESPN BPI retrospective; Silver Bulletin gap)
- ESPN Stats & Info "So how did BPI do with its projections" (2015-06-01, season 2014-15): a selective review of three teams (Hawks projected 60-22, finished 60-22; Cavs 44% to reach the Finals, won the East; Warriors 99% to be No. 1 seed, clinched it). Author admits some projections "felt too high"; no full track record, no calibration. Source: https://africa.espn.com/blog/statsinfo/post/_/id/106121/so-how-did-bpi-do-with-its-projections (read 2026-11-03). Lesson: a selective recap is a weak record; ours should be complete.
- ESPN BPI still active for 2026-27 (ESPN preview dated 2026-10-07, snippet). FiveThirtyEight closed (snippet: "crunched its last number"; date not confirmed).
- Silver Bulletin: no published 2025-26 NBA accuracy record found. Gap.


### Iter 25: Named recurring EuroLeague analytics series (Vujovic, Medium 2025-26)
- Series titles and dates from the Medium author page (search snippets, read 2026-11-03; page fetch returned 403): "Efficiency Landscape, Rounds 5-10" (2025-11-13); "Drama Report, Rounds 1-10" (2025-11-17); "Heat Check, Rounds 1-13" (2025-11-28); "Efficiency Landscape, Rounds 10-15" (2025-12-23). Source: https://medium.com/@vujke
- Format pattern: a named series, round-range title, one chart per post, teams sorted into contenders/pretenders/decline. Consistent with "series + round number" as a repeatable template for us. Confidence: medium (titles from snippets, not body text).
- No 2026-27 posts from this series found; gap for the current season.

### Iter 26: Panathinaikos X game-stats graphics (lead, unverified)
- Club account @Paobcgr (Panathinaikos BC) reportedly posts "Game Stats" graphics for EuroLeague games; a LunarCrush page claims about 146K followers. The LunarCrush page (read 2026-11-03) shows "no data generated" and no follower count, so the 146K figure is UNVERIFIED and not used. Source for the lead: https://lunarcrush.ai/mdx/creator/twitter/Paobcgr (snippet).
- Christos Marmarinos / NewStats.eu: still unverified as an X or graphics account (search snippets only).
- Weak iteration: lead yields a club-account format lead only. Gain counted as 1.


### Iter 27: EuroLeague copyright and social-video scale
- No EuroLeague fan or social content-use policy found (searches 2026-11-03; EuroLeague legal pages not reached). Gap. Treat all league footage, logos and clips as NOT reusable. Our graphics should use public box-score numbers, our own charts, and no league logos beyond the brand-neutral text.
- 2025-26 season social figures: a search snippet says "social media content generated 2.27 billion video views" (+49% YoY). The Eurohoops article of 2026-05-08 (iter 11) says 1.49 billion video views across league-owned platforms. Different scopes; both cited, not merged. Source for 2.27B: search snippet (EuroLeague season report), 2026-11-03. Not fetched.
- Conduct: EuroLeague opened a disciplinary case over social-media posts (Eurohoops, undated snippet). Rule for us: no commentary on referees or players that the league could treat as conduct breach.

### Iter 28: Reddit 10% self-promotion guideline status and subreddit caps
- Official Reddit page not reached (support.reddithelp.com 403; redditinc.com fetch refused). Marketing sources disagree on whether the 10% ratio is still official. One says it is retired but enforced in spirit by mods; another says it is defunct. Sources (snippets, 2026-11-03): https://redship.io/blog/reddit-self-promotion-rules-2026 and the mythos.one page (judged low quality, not used).
- Stricter subreddit caps found in wiki snippets: r/cybersecurity: under 10% of posts and comments on that sub, plus a weekly cap per promoted entity (https://redlib.hbubli.cc/r/cybersecurity/wiki/rules/promotion); r/pcgaming: no more than 10% of Reddit-wide submissions from any single source (https://redlib.belloworld.it/r/pcgaming/wiki/selfpromotion); r/entrepreneur: promo only in designated threads (snippet). Shows that caps are per-sub and sometimes stricter than 10%.
- Working rule: keep our r/Euroleague posts under 1 per week and never the same link across subs in one day, until the sidebar is checked.


### Iter 29: r/dataisbeautiful 2026 [OC] snapshot (score vs methodology line)
- Snapshot 2026-05-19 (sentinel mirror, read 2026-11-03), 19 posts. Scores run from 0 to 3,864. Top [OC] posts carried no labeled Source or Methodology line ("No Warming in Years" 2,795 pts, none; "China added a Germany-sized electricity grid" 2,549 pts, none). Posts with labeled lines: "Tool: Python (matplotlib, numpy) Data: HIPPARCOS, NASA" (237 pts); "Calculated in Excel, mapped using Datawrapper" (31 pts). Source: https://reddit.sentinel-team.org/subreddits/dataisbeautiful/snapshots/2026-05-19T18%3A39%3A52.629824Z.
- One post was noted as "previously removed, reposting". Removal flags otherwise absent.
- Read: the methodology line is required for credibility (Olson, iter 23), but does not drive score. The topic and the visual do. Confidence: medium (one snapshot).

### Iter 30: X posting timing and thread split (OpenTweet, vendor; flagged)
- OpenTweet timing study (published 2026-04-22; 50,000+ tweets, 2026-01-01 to 2026-04-15, accounts 100 to 100K+ followers): engagement rate per impression. Best day Wednesday (+17% vs weekly average); Tuesday +15%, Thursday +12%, Sunday -23%, Saturday -15%. Hours: weekday 8-11 AM peak; 4-7 tweet threads reportedly 35% above standalone tweets; images and video best 12-2 PM weekdays. Source: https://opentweet.io/blog/best-time-to-post-on-twitter-data-study (read 2026-11-03).
- Flag: the author sells a scheduling tool; no significance tests; users skew tech/SaaS. Sprout Social (multi-platform, ~307K profiles, Nov 2025-Feb 2026) favours midday to late afternoon, Tue-Thu 12-6 PM local (https://sproutsocial.com/insights/best-times-to-post-on-twitter/, snippet). The two disagree; test ours against our own analytics.

## Accounts (X, with figures)
| Handle | Type | Followers | Posting | Format evidence | Source (read 2026-11-03) |
|---|---|---|---|---|---|
| @themarginsports (The Margin) | forecast model, NBA and other sports | not captured | not captured | public calibration page; misses and failed models shown | https://themargin-89y.pages.dev/calibration/ |
| @crumpledjumper (Todd Whitehead) | data-viz artist | not given | not given | hand-built physical charts; FiveThirtyEight-style headline and subhead | https://nightingaledvs.com/meet-the-data-visualization-king-of-basketball-twitter-todd-whitehead/ (2022) |
| @EuroLeagueWomen | league women's competition | 45,916 | not captured | none | https://www.fiba.basketball/en/events/euroleague-women-25-26/news/euroleague-women-surpasses-1-million-followers-on-social-media (undated) |
| @notbpod (Numbers On The Board) | NBA stats/analysis | 35.7K | about 5.1/day | not captured | https://socialpruf.com/x/notbpod (12-month window to 2026-11-03) |
| @UnderdogNBA | sportsbook brand | 765K | about 48/day | top 20: 14 image/graphic, 6 text-only | https://socialpruf.com/x/UnderdogNBA |
| @noahchestnut | analyst thread | n/a | n/a | 11-tweet thread with screenshots, 12,399 views | https://threadreaderapp.com/thread/1063488415541288962.html |

Not counted (gated or unverified): @euroleague, @cleaningtheglass, @theanalyst (socialpruf gated); @Paobcgr (146K claim unverified); Christos Marmarinos / NewStats.eu (no X handle found). Men's EuroLeague X follower count: not obtained.

## Subreddits
- r/Euroleague: about 38-41K members (GummySearch 2026-06-21; Hive Index 2026-10-27); about 31 flaired posts per month (17 EuroLeague, 14 EuroCup; Hive Index). Dominant post types: match threads and team-home threads. Rules: not obtained (sidebar check needed).
- r/nba: the 9 top posts on 2026-04-15 were news and [Highlight]/[Haynes]/[Palmer] tags; the only [OC] was a long-form stats ranking (4,613 pts). The weekly Friday self-promo thread has paywall, sign-up, reseller and activity rules (sentinel snapshot 2025-12-06).
- r/nbadiscussion: about 1.2M members (GummySearch); in-season no jokes or hot takes; off-season allows in-depth OC; "Statistical Analysis" flair exists.
- r/dataisbeautiful: [OC] needs the visualization, the data source and tool in the first comment (mirror rules). Removals 2013-16: about 50% no visualization, about 40% no creator credit (Olson 2016). 2026 top posts often lacked a labeled methodology line.
- Greek subreddit: none found (search 2026-11-03).

## Patterns
- Format: static graphics beat video on X by impression-based engagement (Ordinal, fetched: image 0.79%, text 0.68%, video 0.54%); UnderdogNBA's top posts are mostly images.
- Titles: source-tag prefixes ([OC], [Highlight]) are the norm on r/nba; statements beat questions (vendor claim, one source).
- Methodology: r/nba's 2,608-point [OC] disclosed the Arctic Shift source, sample sizes and 96% classifier accuracy in the body, with dashboard and GitHub links.
- Record display: The Margin shows losses and failed models; ESPN's 2015 BPI review is selective (three teams). Ours should show every graded game.
- Reach: link posts showed no median penalty in one 60-account sample (ratio 1.05; small accounts; observational).
- Timing: vendor studies disagree (redditapis: 6pm ET peak, Sunday; OpenTweet: Wednesday 8-11 AM; Sprout: Tue-Thu 12-6pm). Treat as hypotheses.

## Synthesis at 30 (final baseline)
Evidence: 30 iterations, 117 cumulative data points, 6 X profiles with figures, 4 Reddit communities. Most X figures come from third-party trackers or vendor blogs, not from fetched X pages (X returned 402 and social platforms gated).

- Posts per day (X): stats/analysis account sampled at about 5 posts/day (@notbpod); brand account about 48/day (@UnderdogNBA). Industry average 70 posts/month (Socialinsider, about 2.3/day). Confidence: low-medium. Our 1-2 X posts a day is below the sampled stats account and is a choice, not a norm.
- Video vs image: image > text > video on X by impression engagement (Ordinal, fetched; sample size not stated). Confidence: medium.
- Threads: highest by Ordinal's ranking (figure missing in the fetch); OpenTweet says 4-7 tweet threads run about 35% above single tweets (vendor, relative). Confidence: low.
- Caption length: 100-200 characters best (Ordinal). Confidence: medium, one source.
- Hashtags: 0-2 suggested by one blog; no primary study. Confidence: low.
- Top topics: match results, efficiency or net-rating landscapes, named round series (Vujovic), LVP-style rankings on r/nba. Confidence: medium.
- Voice: data-first, with methodology disclosed and misses visible (The Margin, r/nba, r/dataisbeautiful). Humour sits in comments, not posts. Confidence: low-medium.
- Animation styles and hook patterns: not sourced in this slice (no X post examples fetched). Gap.
- Best times: conflicting (see Patterns). Confidence: low.
- Copyright: league footage and logos are not reusable (no league content policy found; EuroLeague opened a disciplinary case over social posts). Use our own charts and public box-score numbers only.

## Reddit posting rules for r/Euroleague (pending sidebar check)
1. Keep site self-promo under about 10% of our Reddit activity (guideline; not verified as official); no more than one link post a week to r/Euroleague.
2. Post a self-made chart as [OC], with the data source and tool in the first top-level comment (dataisbeautiful norm).
3. Never post the same chart or link to several subs on one day.
4. Use neutral titles, no sensational wording, no question titles (vendor claim, one source).
5. Build real comment history in r/Euroleague before posting links; the r/nba weekly thread bars paywalled or sign-up links, so the 675hoops page must open free.
6. Match threads are the community's core flair; our posts should fit a match-thread or round-review slot.
7. Read the r/Euroleague sidebar and modmail before the first post; the rules were not readable here.

## 5 best post templates (with sources)
X
1. Round-recap card: one image, one headline stat, round-number title. Source: Vujovic named series (Medium, 2025-26; "Efficiency Landscape, Rounds 5-10", 2025-11-13); Ordinal image > video.
2. Forecast-record card: "our call vs result" table with misses shown and a calibration line. Source: The Margin calibration page (1,220 games, misses published).
3. Methodology thread (4-7 tweets): tweet 1 = finding plus chart; tweets 2-4 = method, source, sample size; last = link. Source: OpenTweet thread split (vendor).
4. Distinctive chart with a FiveThirtyEight-style headline and subhead. Source: Whitehead interview (2022).
5. Short text-led post of 100-200 characters with one image. Source: Ordinal (text 0.68%; 100-200 characters best); UnderdogNBA top posts 14 of 20 image/graphic.

Reddit
1. [OC] methodology post: title "[OC] <finding> (<season>)", body with sample size, method and data links, source and tool in the first comment. Source: r/nba 2,608-point [OC] (sentinel 2026-02-17 snapshot); dataisbeautiful norms (mirror).
2. Long-form ranking [OC] ("[OC] ... LVP. LEAST Valuable Player"), 4,613 pts on r/nba, 2026-04-15 (sentinel).
3. Source-tag title convention ([OC], [Highlight]) in r/nba top posts (sentinel 2026-04-15).
4. Weekly-thread route: link only in the designated self-promo thread and obey its paywall and sign-up rules (r/nba mod post, sentinel 2025-12-06).
5. Off-season in-depth OC for r/nbadiscussion (mod post, snippet): schedule high-effort ranking posts for the off-season.

## Caveats
- X handles and metrics come mostly from trackers and vendor blogs. Direct X pages were blocked (402).
- Reddit direct and mirror access failed for the r/Euroleague sidebar and most rule pages, so rules come from mod posts, snapshots and guides.
- Vendor studies (redditapis, Upvote.net, OpenTweet, Sprout) sell tools; their timing and format figures are hypotheses.
