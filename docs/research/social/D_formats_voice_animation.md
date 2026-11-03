# D — Formats, voice, animation, benchmarks (agent D)

Read date for all sources: 2026-11-03 (search/fetch date). "est." = estimate, method stated.

## Scoreboard

| iter | lead | new data points | cumulative | accounts profiled (cum) | notes |
|---|---|---|---|---|---|
| 1 | Instagram AI-profile / AI-label rules 2026 (TechCrunch fetch) | 4 | 4 | 0 | Policy 31 Aug 2026; AI-edited graphics exempt; reach cut for unlabelled AI *persons* |
| 2 | TikTok AI-label rules 2026 (secondary blogs; TikTok page not fetchable) | 3 | 7 | 0 | Realistic AI must be labelled; auto-label not removable; unoriginal-content rule NOT verified BELOW BAR (gain 3 < median 4) |
| 3 | Instagram Reels length/limits (secondary blogs) | 2 | 9 | 0 | Sources conflict (90 s vs 3 min); treat as low confidence BELOW BAR (gain 2 < median 3.5) |
| 4 | AI voice trust: Adobe Express consumer survey + TUM poster + Studio Resonate (voice) | 6 | 15 | 0 | Adobe n=850 (pub 18 Feb 2026); TUM poster numbers NOT fetchable (404) |
| 5 | Instagram format benchmarks: Socialinsider 2026 + Netinfluencer (700M posts) | 9 | 24 | 0 | Socialinsider 67.5M posts; Netinfluencer posting-frequency vs growth |
| 6 | Best posting times: Sprout Social 2026 (fetched) vs Later Apr 2026 (fetched) | 8 | 32 | 0 | Sprout n≈2B engagements/307k profiles; Later data is 2024 (flagged); no Greece/Europe study found |
| 7 | EuroLeague's own channels: 2025-26 social results (Eurohoops, fetched) + EuroLeague Women FIBA release | 5 | 37 | 2 (league-level only; no per-account data) | 47.1M followers; 1.49B video views; discrepancy with 2.27B snippet; copyright: league footage = restricted |
| 8 | Data-source licensing for stats reels: Basketball-Reference / Sports-Reference terms (snippets; site 403 to fetch) + open-source bar-race repo (fetched) | 5 | 42 | 2 (repo + tool precedents, no social accounts) | Chartball fetch 403; no social-account case study found |
| 9 | Hook/retention: TikTok for Business creative best practices (fetched, updated Jun 2025) + Quso retention benchmarks (fetched, Jun 2026, 508k posts) | 8 | 50 | 2 (no accounts; platform guidance) | Hook 6 s, proposition 3 s, 5–10 words/s captions; YouTube Shorts-only retention |
| 10 | Hashtags and caption keywords: Instagram cap change (BusinessToday, fetched) + Fanpage Karma 1.6M posts (fetched) | 9 | 59 | 2 (no accounts; platform data) | Synthesis at 10 below. Caption-length data still missing |
| 11 | Music licensing: Meta Help Center (search summaries; pages JS-only, fetch returned no text) + TikTok CML (vendor) | 6 | 65 | 2 (no accounts) | Meta help not fetchable: snippet-level; vendor-level for CML |
| 12 | TTS licences: Piper (GitHub, fetched), Kokoro (HF, fetched), XTTS-v2 (HF, fetched), edge-tts (GitHub, fetched) | 7 | 72 | 2 (tools) | Median of iters 1–11 = 6; iter 12 gain 7 |
| 13 | Programmatic video licences: Remotion (licence FAQ via search + pricing page fetched), Manim (fetched), MoviePy (fetched) | 8 | 80 | 2 (tools) | Remotion: free for up to 3 people; paid tiers quoted via search, third-party prices conflict |
| 14 | Captions: faster-whisper, openai/whisper (fetched), Instagram auto-captions (TechCrunch 2022 fetched; search summaries) | 7 | 87 | 2 (tools) | Greek WER not in text (chart image); captions on-by-default not confirmed by primary |
| 15 | Other sports' data pages: Opta Analyst / Stats Perform (statsperform pages 403; search snippets) + F1 Insights (snippets) | 7 | 94 | 4 (brand/data pages, not personal accounts) | All Stats Perform primary pages returned 403: snippet-level only |
| 16 | Greek audience reach: DataReportal Digital 2026 Greece (fetched, Nov 2025 data). Loop/CTA lead dried up (0 counted, vendor-only) | 7 | 101 | 0 | Keepface and Affect Group figures conflict with DataReportal (not used) |
| 17 | Win-probability / result graphics: Zoomph final-score graphic analysis (fetched) + search results on win-prob models (FlowingData 403) | 6 | 107 | 0 | Zoomph: sample and platform not stated; engagement 4.95% win vs 2.09% loss BELOW BAR (gain 6 < median 7) |
| 18 | Platform rule on mass-produced/repetitive content: YouTube 'inauthentic content' (support.google.com/youtube/answer/1311392 fetched; Plagiarism Today fetched) | 8 | 115 | 0 | YouTube help page gives templated/slideshow/reused-content examples; monetisation scope only |
| 19 | Basketball TikTok creator list (Heepsy, updated 1 Nov 2026, fetched): top 10 by followers | 10 | 125 | 10 | None are stats accounts; NBA @nba 25.1M followers, 0.6% ER; engagement 0.01–6% |
| 20 | Account-level tools for basketball IG: HypeAuditor @nba snippet (pages 403 on fetch), Heepsy pricing, Greek sports lists (404, dead end) | 5 | 130 | 1 (@nba IG, snippet) | BELOW BAR (5 < median 7). Greek basketball account lists not found; reported honestly, not padded BELOW BAR (gain 5 < median 7) |
| 21 | Free-tier cloud TTS (Azure AI Speech pricing page, fetched) + FFmpeg licence (ffmpeg.org/legal.html, fetched) | 6 | 136 | 0 | Azure page: F0 0.5M chars/month; paid price and Greek voices missing from capture BELOW BAR (gain 6 < median 7) |
| 22 | TikTok posting frequency: Buffer 2025 TikTok study (11.4M posts, fetched) + Metricool 2026 (search) + TT Calculator (search, method unclear) | 9 | 145 | 0 | Buffer: fixed-effects regression, views not followers; TT Calculator conflicts (daily), flagged |
| 23 | Official Reels length rules: Instagram Creators blog (21 Jan 2025, fetched) + Creators FAQ / help pages (search) | 6 | 151 | 0 | Resolves iter 3 conflict: 90 s was the old recommendation cap; 3 min now eligible for non-followers (US first) BELOW BAR (gain 6 < median 7) |
| 24 | Captions and sound-off viewing: Verizon Media/Publicis 2019 survey (3Play writeup fetched: n=5,616, Apr 2019) + Instapage A/B test (snippet) + 85% claim traced (Digiday 2016) | 7 | 158 | 0 | Facebook 12% view-time claim is secondhand; 85% sound-off has no primary study |
| 25 | Animation tool licences: Motion Canvas (GitHub, fetched), matplotlib (license page, fetched), Flourish free-plan terms (fetched) | 8 | 166 | 0 | Flourish free plan: credit line + hyperlink required on social video; no bar-race template verified |
| 26 | Music sourcing: Pixabay content licence summary (fetched) + Suno free-plan commercial terms (search, multiple secondary) | 7 | 173 | 0 | Pixabay: no attribution, but no standalone use and trademark rule; Suno free tier = non-commercial (secondary) |
| 27 | Hootsuite Social Trends 2026 (Carahsoft page 639k chars; adindex PDF too large to fetch) | 3 | 176 | 0 | BELOW BAR (3 < 7). No usable survey statistic retrieved; reported as-is BELOW BAR (gain 3 < median 7) |
| 28 | Meta 'AI info' label rules for organic AI audio (Meta transparency page: fetch empty; search summary of Meta policy) | 0 | 176 | 0 | CORRECTED by iter 29: the search-summary 'must disclose / penalties' claim is NOT in Meta's primary page. Counted 0 BELOW BAR (gain 0 < median 7) |
| 29 | Meta primary: 'Our approach to labeling AI-generated content' (about.fb.com, 5 Apr 2024; updated 23 Oct 2025; fetched) | 6 | 182 | 0 | Organic disclosure duty for AI audio NOT stated there; advertiser rule only; below bar (6 < 7) BELOW BAR (gain 6 < median 7) |
| 30 | Greek narration: Kokoro language count (HF, fetched) + Piper VOICES.md Greek voice (GitHub, fetched) | 4 | 186 | 0 | Greek: no Kokoro Greek voice listed (8 languages); Piper has one low-quality Greek voice (el_GR rapunzelina) BELOW BAR (gain 4 < median 7) |

Bar check (rule 2: gain >= median of earlier iterations): missed at iterations 2, 3, 17, 20, 21, 23, 27, 28, 29, 30. Met at the other 19 (iteration 1 has no earlier bar). Final median gain 6.5; total 186 new sourced data points. Iteration 28 was corrected to 0 after the primary page did not support its claim (see iter 29).

## Structure
### Iter 9 — hook and retention
- TikTok for Business, "Creative best practices for performance ads" (last updated June 2025; fetched 2026-11-03): "Prioritize your hook in the first 6 seconds to boost engagement and increase watch time," using suspense/surprise/emotion; "Introduce your content proposition in the first 3 seconds for better recall and awareness"; "Use captions or text overlays"; "We recommend displaying 5-10 words per second when using text"; 3–5 creatives per ad group. These are ad guidelines, not organic rules; the page cites no statistics. Source: https://ads.tiktok.com/help/article/creative-best-practices?lang=en
- Quso.ai "video retention benchmarks" (published/modified 29 Jun 2026; dataset ~508,000 posts, 1,900+ creators, 80+ countries, matured posts 14+ days; YouTube Shorts only; fetched 2026-11-03): median Short holds ~45% average view-through; bottom 90% ~40%; top 10% ~91%; "most retention loss happens in the first three seconds" (no rate given); 11–20 s band has highest median views. Vendor source, sample for the retention subset not stated. Source: https://quso.ai/research/video-retention-benchmarks
- Unverified (secondhand only): "~1.3 s decision window" (Meta 2025 study via Green Frog Labs); "68% of TikTok and 54% of Reels views start sound-off" (dev.to, no study named); "50–60% of drop-offs in first 3 s" (blog, no study). Excluded from the baseline.
- Implication: hook in the first 1–3 s with the claim on screen; captions at ≤10 words/s; a 15–20 s reel is the best-supported length for median views on Shorts (not verified on Instagram).

### Iter 5 — Instagram format benchmarks (benchmarks for format choice)
- Socialinsider "2026 Instagram Organic Benchmarks", 67,541,436 organic posts, ~579,000 business accounts (1K–1M followers), read 2026-11-03: engagement rate Reels 0.50% (2024) / 0.52% (2025) / 0.48% (Q3 2026); carousels 0.55 / 0.55 / 0.50; images 0.45 / 0.37 / 0.35. Average posts per month 2025: Reels 8, carousels 5, images 7. Dates internally inconsistent (flagged). Source: https://www.socialinsider.io/instagram-benchmarks
- Netinfluencer, 700M Instagram posts, Jan–Jun 2025 (read 2026-11-03). Median reach under 1k followers: Reels 134 views, carousels 56, static 23. Over 1M followers: creator reach carousels ~219,000 vs Reels (not given); creator likes carousels 15,080 vs Reels 6,400. 93.5% of accounts post ≤ once a week; average yearly growth by weekly posting: 2–3x 19%, 4–6x 33%, 7–10x 63%, >10x 79%. Correlational, not causal. Source: https://www.netinfluencer.com/instagram-carousels-outperform-reels-for-larger-accounts-content-performance-benchmarks-show/
- Secondary, unverified: Sprout Social's Reels 1.23%/carousel 0.99%/image 0.70% (cited second-hand by sqmagazine, searchlab; sample not found). Buffer March 2026 carousel median 6.9% vs Reels 3.3% (n=520 in one ranking, via blckalpaca) — different metric, do not mix.
- Dash Social (~1.2M posts, ~3,000 brands): 2–3 posts/week drives the highest engagement (secondary citation of their study).
- Implication: for a sub-1k account, Reels are the reach lever; carousels are the save/like lever. Frequency correlates with growth; the 2–3x/week tier is the floor, and daily is not the evidence-backed default.
### Iter 1 — Instagram AI-profile rules
- Instagram announced on Mon 31 Aug 2026 that the opt-in "AI creator" label is renamed "AI-generated profile"; profiles that feature an AI-generated *person* without the label may see reduced reach. Source: https://techcrunch.com/2026/08/31/instagram-puts-new-limits-on-undisclosed-ai-profiles/ (read 2026-11-03, WebFetch). No % cap stated.
- Using AI to edit photos, polish captions, make graphics or other creative tweaks does not require the label. Same source.
- The article does not mention an "AI info" tag; a separate search snippet (implicator.ai / marketing-interactive, Aug–Sep 2026) says the per-post "AI info" tag exists and takes precedence over the profile label. Secondary only.
- Implication for 675hoops: a faceless data reel with an AI *voice* is not an AI-generated person. An AI *presenter avatar* would trigger the profile label rule.

### Iter 2 — TikTok AI labelling
- Secondary reporting (cinerads.com, storrito.com, pixo.video, all 2026, read 2026-11-03 via search): creators must label realistic AI images/audio/video; stylised/clearly non-realistic AI content falls outside the requirement; automatic "AI-generated" labels are applied when AI effects or Content Credentials are detected and creators cannot remove them.
- The TikTok support page (https://www.tiktok.com/support/faq_detail?id=7636670084747893268) returned only a title on fetch, so the wording is unverified against the primary source.
- Public figures in AI content are allowed except for political/commercial endorsements.
- Unoriginal-content rule: no primary text found. Unverified.

### Iter 3 — Reel length limits
- Secondary sources disagree: one says in-app recording up to 3 min and uploads up to 15 min (inro.social / postnext-type guides, 2025–26); another says the feed prioritises Reels under 90 s (2025). Low confidence. Reach-oriented guides suggest 7–15 s for reach, 30–60 s for saves/engagement (klap.app, go-viral.app, 2026). No sample sizes given; not usable as evidence on its own.
- Guides claim 45% of viewers leave in the first 3 s; no primary study found, so treat as unverified.

## Benchmarks
### Iter 7 — EuroLeague channel scale (lead: the league's own social)
- Eurohoops, 8 May 2026, EuroLeague 2025-26 regular season: 47.1M followers across League + clubs (first in league history); 1.49B video views on EuroLeague-owned platforms; 3B+ impressions; video views +1,067% vs 2021-22; follower growth +80% (2.13M). No per-platform split and no statement on reels/short-form. Source: https://www.eurohoops.net/en/euroleague/1965635/2025-26-euroleague-regular-season-breaks-all-historic-records/ (WebFetch). Conflict: a search snippet from another EuroLeague release cites 2.27B video views (+49% YoY); not verified, not used.
- FIBA release, EuroLeague Women: >1M combined followers; ~188,442 Instagram and ~178,606 TikTok followers (undated snapshot). Source: https://www.fiba.basketball/en/news/euroleague-women-surpasses-1-million-followers-on-social-media (snippet; not fetched, medium).
- Copyright note: these are league-owned accounts using league footage and logos. A 675hoops reel must not reuse EuroLeague footage or logos without a licence (rule 7); our own data graphics are the copyable format.
- No public per-account data found for independent basketball stats creators (search for TikTok/IG stats accounts returned mostly vendor pages). Chartball (animated sports charts, FlowingData, 2022) is the best-known original-graphic precedent; dated.

### Iter 6 — posting times
- Sprout Social, "Best times to post on Instagram" (updated March 2026), ~2 billion engagements across ~307,000 profiles (30,000+ customers), 27 Nov 2025 – 27 Feb 2026, times in audience local time (read 2026-11-03, WebFetch). Monday 2–4 pm; Tuesday 1–7 pm; Wednesday 12–9 pm (+11 pm spike); Thursday 12–2 pm; Friday no clear peak, avoid 3–7 am; Saturday lowest; Sunday among worst. Reels not broken out (page says Reels mirror overall windows). No Europe split. Source: https://sproutsocial.com/best-times-to-post/instagram-media
- Later, Apr 2026 (updated 21 Apr 2026), 6M+ Instagram posts, 975k+ Reels analysed, but the data covers Jan–Oct 2024 (flagged). Overall best 5 am local; Reels best 12 am (Monday); Stories 6–8 am and 7–9 pm (no sample). Conflicts with Sprout; author says "a grain of salt". Source: https://later.com/blog/best-time-to-post-on-instagram/
- Greece/Europe: no Greece-specific Instagram study found (Radaar's Athens pages are generic, X/Twitter-oriented). Estimate: use Sprout's local-time windows converted to Athens time (EET/EEST, UTC+2/+3) and then test in our own Insights. Confidence low for region.

## Voice
### Iter 4 — consumer reaction to AI voice
- Adobe Express consumer + marketer survey, US, n=850 consumers and 205 marketers (SurveyMonkey), published 18 Feb 2026, read 2026-11-03: 77% say they trust human voices most; 14% don't trust any voice they think is AI; 88% have wondered if a voice was AI. 58% would trust a brand less if its ads used AI voices; 9% accept AI voices in news, 8% in podcasts, 51% in video games. Nearly 3 in 4 want disclosure of AI voice/music. Source: https://www.adobe.com/express/learn/blog/ai-audio-consumer-trust (WebFetch, vendor survey, fieldwork date not stated, sponsor = Adobe).
- Studio Resonate, "The Power of the Human Voice in an Age of AI", n=1,300 US respondents, paired human/AI ads: human voices scored 23% higher on trust; telling listeners in advance it was AI cut trust 27% even for human voices. Source (search snippet, 2025): https://www.contentgrip.com/studio-resonate-ai-voice-study/ — not fetched, mark medium.
- Crowd React Media radio blind test (July 2026): AI and human voices rated nearly identically on credibility; objections were about trust/authenticity. Source: https://barrettmedia.com/2026/07/14/crowd-react-media-study-divided-radio/ (snippet only).
- Futuri/CMG: listeners identified AI as human ~60% of the time (radio, snippet only). Low weight.
- Video-specific: TUM Junge Akademie poster (June 2025, N=441) reports visible speakers and human voices judged more trustworthy than AI content. PDF returned 404 on fetch, so no exact figures: UNVERIFIED numbers.
- Sports-channel specific: no independent study found. Vendor claims (Revid.ai "55.3% of its users are faceless"; autofaceless.ai stats) are not evidence.
- Implication: AI voice is a trust cost in ads and news; a stats reel that is disclosed and clearly data-led is the lower-risk case. Disclose the AI voice in the caption.

## Animation
### Iter 8 — animation precedents and data licensing
- Open-source NBA bar-chart-race (https://torbenginsberg.github.io/NBA-Bar-Chart-Races/, WebFetch 2026-11-03): data from basketball-reference.com; 2000 onwards; points, rebounds, assists; one year per step, x-axis rescales, bars re-sort each step. No licence named on the page (GitHub repo link present).
- Sports-Reference terms (search snippets of https://www.sports-reference.com/data_use.html and terms page; both returned 403 to fetch, so snippet-only, date unknown): reuse of data restricted; no tools "based on data you scrape"; no use to train generative AI without permission; spidering prohibited; bulk data requests start at $1,000 minimum. Commercial social video using these numbers = contract risk, not copyright. Our pipeline must NOT scrape Basketball-Reference; use EuroLeague API (rule 7) or licensed data.
- Chartball (animated sports charts; FlowingData 2022): page returned 403; no follower/format data verified.
- Vendor bar-race claims (24 s retention, 5x shares) are unsourced marketing; excluded.



## Tooling
### Iter 12 — open TTS licences
- Piper (original): github.com/rhasspy/piper states MIT licence; repo archived 6 Oct 2025, development moved to github.com/OHF-Voice/piper1-gpl (fetched 2026-11-03).
- Piper successor (piper1-gpl): GPL-3.0 licence (fetched). GPL-3 is copyleft: distributing the code in a product carries obligations; generating audio with it is not itself restricted. Voice-model licences must be checked per voice (VOICES.md not retrieved).
- Kokoro-82M (huggingface.co/hexgrad/Kokoro-82M, fetched): Apache-2.0; v1.0 released 27 Jan 2025; trained on public-domain and permissive-licensed audio plus CC BY sources (Koniwa, SIWIS) and synthetic audio from closed providers; "deployed in numerous projects and commercial APIs". No voice-specific licence stated (VOICES.md not retrieved). Best licence fit for a commercial social channel, pending a per-voice check.
- Coqui XTTS-v2 (huggingface.co/coqui/XTTS-v2, fetched): Coqui Public Model License (CPML). Commercial terms are in the CPML text, which returned 404 (coqui.ai/cpml). Treat as NOT cleared for commercial use until the text is read. Avoid.
- edge-tts (github.com/rany2/edge-tts, fetched): uses Microsoft Edge's online voices; the README says "Microsoft prevents the use of any SSML that could not be generated by Microsoft Edge itself." No licence named in text (file list suggests GPL-3.0). It is an unofficial client of a Microsoft service, so its use in a monetised channel rests on Microsoft's service terms, which we have not read. Risk: medium.

### Iter 20 — account-level tools (bar missed: gain 5 vs median 7)
- HypeAuditor @nba Instagram page (search snippet, 2026-11-03; page 403 on fetch): ~87.9M followers at 17 Oct 2026 (87,902,526, down from 87,970,249 on 24 Sep 2026); engagement rate 2.19% labelled "Average"; follower growth -0.09%. Source: https://hypeauditor.com/instagram/nba/ (snippet).
- HypeAuditor: Audience Quality Score 1–100, 60+ counted as good (search snippet of its free tool page). Vendor definition.
- Heepsy: paid plans from $49/month, free engagement calculator, free trial (search snippet; vendor claims).
- Greek sports influencer list (heepsy.com/top-instagram/sports/greece): 404; Greek basketball TikTok/IG accounts not found via search. Dead end for Greek sports accounts.
- Honest note: this iteration did not reach the rising bar. Next iterations target platform/tool data with stronger sample sizes.

### Iter 19 — profiled basketball TikTok accounts (first real account data)
Source: Heepsy, "Top basketball TikTok creators" ('Oppdatert 1. november 2026'; fetched 2026-11-03). Ranked by followers; engagement rate and average likes as shown (Heepsy's definitions; averages not verified):
| Handle | Followers | Eng. rate | Avg likes |
|---|---|---|---|
| @mdmotivator (Zachery Dereniowski) | 26.1M | 1.7% | 443K |
| @nba (NBA, league account, uses league footage: copyright-restricted) | 25.1M | 0.6% | 147K |
| @onlyjayus | 17.5M | <0.01% | 534 |
| @serenaneel | 12.5M | 6.0% | 748K |
| @leethe4th | 12.2M | 0.02% | 1.9K |
| @ate_audwii | 10.6M | 0.1% | 15.4K |
| @lexihensler | 10.4M | 0.3% | 32.4K |
| @kimpeeee | 8.9M | 0.09% | 8.3K |
| @seanfreestyle | 8.8M | 0.01% | 1K |
| @ashtonhallofficial | 7.2M | 5.2% | 372K |
Takeaway: the top basketball TikTok accounts are entertainment creators, not stats accounts; no stats creator appears in the top 10. Engagement ranges 0.01% to 6%, so follower count does not predict engagement. Heepsy's engagement figures are third-party estimates. Source: https://www.heepsy.com/no/finn-influensere/tiktok/basketball

### Iter 18 — unoriginal / repetitive content rules (YouTube as the nearest precedent)
- YouTube YPP "inauthentic content" (renamed from "repetitious content"), effective 15 Jul 2025: aimed at "mass-produced and repetitive content"; applies regardless of whether AI is used; enforcement mostly automated; penalties = demonetisation or removal from YPP, not removal of the video. Source: https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/ (fetched 2026-11-03; article dated 8 Jul 2025). Plagiarism Today notes no official examples and no mention of AI voiceover.
- YouTube help page (support.google.com/youtube/answer/1311392, fetched 2026-11-03), exact examples: content must be "Not mass-produced, generic, repetitive, or manipulative"; "content that looks like it's made with a template"; not monetisable: "Image slideshows, templated storylines, or scrolling text with minimal or no narrative, commentary, or educational value"; "AI-generated content made with generic or unoriginal templates giving the impression of mass production"; "Reused content" that "exclusively features readings of other materials you did not originally create". No AI-voice example. The rename from "repetitious" to "inauthentic" is stated there (15 Jul 2025).
- Key test for us: templated, scrolling text with minimal commentary is named. A data reel needs its own angle (a comment line, a result, an insight) each time, not just swapped numbers.
- Implication for us: a reel template reused across weekly reels with only the numbers changed is exactly the "repetitive" pattern. Keep each reel's script and graphic meaningfully different (new angle, new chart), and add a human-written take each week. This is an inference from the policy, not a stated rule for Instagram or TikTok.
- Instagram/TikTok unoriginal-content rule: still not found in primary text (TikTok page returned title only).

### Iter 17 — win-probability and result graphics
- Zoomph analysis of final-score graphics (zoomph.com/?p=51360, fetched 2026-11-03; post dated "12 Feb", year not stated, probably 2025): winning teams' graphics 4.95% engagement rate and 1,162,791 impressions; losing teams 2.09% and 648,243. Sample size, platform and method not stated: medium-low. Implication: result-led graphics (a clear winner/score) carry more reach. Our EuroLeague forecast reel can lead with "model said X%, result Y".
- NBA social team (older, per search snippet, undated, treat as dated): average graphic ~120,000 Instagram interactions. Not verified.
- Win-probability line charts: public models exist (inpredictable.com, Michael Beuoy 2000–2012 play-by-play model; hoopR pulls ESPN win-probability data). Animated playoff win-probability by Adam Pearce (FlowingData, 9 Oct 2020) found, page returned 403 (snippet only).
- Blinkfire 2025-26 NBA season report (snippet): engagement fell overall; Instagram a bright spot; mixed media replacing images. Full text not retrievable: not counted.
- Gap: no named account with a documented win-probability reel and its numbers was found.

### Iter 16 — Greek audience reach (regional lead)
- DataReportal "Digital 2026: Greece" (Kepios for DataReportal; published 8 Nov 2025; fetched 2026-11-03): 7.40M social media user identities (74.5% of population, Oct 2025); Facebook 5.10M (51.4% of pop; 61.2% of adults 18+); Instagram 4.60M (46.3% of pop; 54.6% of adults 18+); TikTok 55.3% of adults 18+ (count given as 4.60M for 18+ in the table). Platform figures are advertising-reach estimates, not active users; DataReportal warns not to compare with older reports. Source: https://datareportal.com/reports/digital-2026-greece
- Conflicts (not used): Keepface and Affect Group TikTok estimates (4.06M 18+) differ from DataReportal's table; flagged.
- Looping/ending-CTA lead (iter 16 attempt): search returned only vendor blogs with no sampled data; the only percentage (Buffer 30–50% watch-time lift from pattern-interrupt openings) is secondhand and unverified. Not counted.
- Implication: Instagram reaches ~half of Greek adults, so a Greek-language caption or on-screen Greek text is a real reach lever for a Greek audience; EuroLeague's audience is pan-European.

### Iter 15 — other sports' data pages (comparison)
- Opta Analyst (Stats Perform), a football data editorial site: "more than a million fans visit ... every month" and a 2025 award announcement citing "more than 200 million social impressions" across platforms (not split). Source: https://www.statsperform.com/insights/opta-analyst-win-at-future-of-media-awards-2025/ (search snippet; page 403 on fetch).
- Stats Perform case study (FC Barcelona "Best Built Goal" series, Opta goal-sequence data): 229 million+ impressions across Instagram, Facebook, X, Threads and Stories from 104 posts. Brand account, not a stats page; the closest format precedent for a data-driven goal graphic series. Source: statsperform.com (search snippet; 403 on fetch).
- Opta graphics tool: 22,000 graphics produced across 2025 (Stats Perform developer page, snippet). Shows demand for templated data graphics at scale.
- F1 Insights (AWS-powered, broadcast graphics): seven graphics at launch in 2020, 22+ real-time statistics by the time of the snippet. Broadcast, not social; a format reference for "one stat, one card".
- Opta Analyst lists a dedicated Managing Editor, Social & Multimedia (Hashtag Sports awards entry, snippet): a social function is staffed.
- Blinkfire's 2025 F1 social report exists but its text was garbled; no per-account figure used.
- Lesson: sports-data brands that scale do it through a repeatable graphic template (one stat, one card, one series name), not one-off edits.

### Iter 14 — captions and speech-to-text
- openai/whisper (github.com/openai/whisper, fetched): MIT licence; six sizes tiny (39M) to large (1550M) plus turbo (809M); Greek WER only in a chart image, not retrieved.
- SYSTRAN faster-whisper (github.com/SYSTRAN/faster-whisper, fetched): MIT; README claims "up to 4 times faster than openai/whisper for the same accuracy while using less memory" (hardware for the claim not stated; benchmark tables use RTX 3070 Ti). Model-weight licence not stated on page (flag).
- Instagram auto-captions: TechCrunch, 1 Mar 2022 (fetched): captions for "videos on its app" in 17 languages at launch; users toggle "show captions" in advanced settings. The article does not say whether captions are default-on or whether creators can edit them (secondary coverage claims both; unverified). Meta's standalone Edits app added auto-captions in 2025 (third-party blog only).
- Practical: burn captions yourself (ffmpeg subtitles filter from our own SRT) so the captions survive on every platform and the 5–10 words/s rule holds; Instagram's own captions cannot be relied on for styling.

### Iter 13 — programmatic video tools
- Remotion (remotion.dev): pricing page (fetched 2026-11-03) says "Remotion is completely free to use for any individual or small company - no catch"; bigger companies pay a licence fee. Search snippets of the official FAQ/terms (remotion.dev/docs/license/faq, remotion.dev/docs/pricing) say free covers individuals and for-profit organisations with up to 3 people; paid options: "Remotion for Creators" $25 per seat per month; "Remotion for Automators" $0.01 per render with $100/month minimum (both as quoted in the terms, via search). Toolradar quotes a flat $100/month (conflict, secondary). Verdict: free at our size; check remotion.dev/pricing before any growth. Remotion renders React to MP4 using headless Chrome/FFmpeg. Source: https://www.remotion.dev/docs/license/pricing
- Manim Community (github.com/ManimCommunity/manim, fetched): MIT licence; copyright 3Blue1Brown LLC and Manim Community Developers; "animation engine for explanatory math videos". Good for formulas and equations, not charts.
- MoviePy (github.com/Zulko/moviepy, fetched): MIT; v2.0 released with breaking changes; v1 no longer maintained. Use v2 only.

### Iter 11 — music licensing (both platforms)
- Instagram Help Center (help.instagram.com/402084904469945/ and /1612770602842742/; fetch returned only the page title, so these are search-snippet level, 2026-11-03): song may be unavailable by account type or region; if no Licensed Music Library access, use Sound Collection; for Reels, Meta recommends royalty-free Sound Collection music or original audio; subscriber-only content limited to Sound Collection or music you own; Ads Manager music = royalty-free Meta Sound Collection.
- Business-library size (~14,000 tracks cleared for commercial use on FB/IG vs millions for personal) and claim that in-app licences do not cover cross-posting to TikTok/YouTube Shorts: foximusic.com "Instagram Reels Music Copyright: The 2026 Legal Guide" (vendor, read via search 2026-11-03). https://www.foximusic.com/blog/instagram-reels-music-copyright-legal-guide/
- TikTok: business accounts see only the Commercial Music Library in-app; standard library unavailable to business and monetised personal accounts (Soundstripe / Thematic vendor pages, 2026; TikTok primary page not retrieved). Thematic is a self-described CML partner (conflict of interest).
- Practical rule: use Meta Sound Collection / TikTok CML tracks for the reel, or music from a licensed royalty-free library with its licence kept on file; do not assume it transfers across platforms. Original generated music (own composition) avoids this but must be original.


## Synthesis at 10/20/30

### Synthesis at 10 (iterations 1–10, 59 data points, 2 platform accounts-level benchmarks, 0 individual basketball accounts profiled)

Baseline for a 675hoops reel (confidence in brackets):
- **Posting frequency:** 2–3 posts/week is the best-supported floor; Netinfluencer (700M posts, Jan–Jun 2025) found yearly growth 19% at 2–3x/week, 33% at 4–6x, 63% at 7–10x, 79% above 10x. Correlational; 93.5% of accounts post ≤ weekly. [medium: one large sample, correlation only]
- **Video vs image share:** Socialinsider 2025 average posts per month: Reels 8, carousels 5, images 7. Reels reach beats carousels for sub-1k accounts (median 134 vs 56 views, Netinfluencer). Carousels win on likes/saves for creators >1M. [medium]
- **Top topics:** no data gathered for basketball stats accounts yet (gap). [low]
- **Voice/tone:** AI voice carries a trust cost: 58% (Adobe, n=850, US, Feb 2026) would trust a brand less with AI voice in ads; 9% accept AI voice in news. Disclosure is wanted by ~3 in 4. Sports-specific evidence: none. [medium: sponsored survey]
- **Animation styles:** bar-chart race precedent (open-source NBA repo, data from Basketball-Reference, which carries licence risk); no account-level performance data. [low]
- **Hook patterns:** TikTok official: hook within 6 s; proposition within 3 s; text 5–10 words/s. Quso (YouTube Shorts, 508k posts): median average view-through ~45%, top 10% ~91%; most loss in first 3 s. [medium for guidance, low for Shorts-to-Instagram transfer]
- **Caption length:** no sourced benchmark yet (gap).
- **Hashtags:** Instagram cut the cap from 30 to 5 (announced 18–19 Dec 2025 via @Creators; applies to posts and Reels). Fanpage Karma (1.6M posts, 2026): 0–1 hashtags ≈ baseline; 4 = +1%; 5 = +3%; 2–3 lower; 45% of posts use none. Keyword captions and on-screen text drive discovery per Mosseri (via BusinessToday). [medium]
- **Best times:** Sprout Social (≈2B engagements, 307k profiles, 27 Nov 2025–27 Feb 2026, local time): Mon 2–4 pm, Tue 1–7 pm, Wed 12–9 pm, Thu 12–2 pm; avoid weekends. Later (2024 data, 6M posts) says 5 am / 12 am for Reels: conflicts; no Greece-specific study (estimate: test Athens-time windows in Insights). [medium for Sprout; low for Greece]
- **AI labelling:** Instagram (31 Aug 2026): AI-generated *person* profiles need the "AI-generated profile" label or lose reach; AI-edited graphics/voice are exempt per the TechCrunch article. TikTok: realistic AI content should be labelled; auto labels cannot be removed. [medium: secondary reporting for TikTok]
- **Copyright:** league footage/logos are owned content (EuroLeague 47.1M followers, 1.49B video views in 2025-26). Our reels must use original graphics only.

Gaps for iterations 11–30: caption length and on-screen text studies; music licensing on both platforms; TTS licence checks (Piper, Kokoro, Coqui, edge-tts); Remotion, MoviePy, Manim, matplotlib + ffmpeg; faster-whisper captions; sports-stats account profiles (IG/TikTok public pages, Social Blade); other-sport data pages (F1, football); endings/CTA and loop research.

### Iter 28 — Meta AI-info rules for AI audio (primary page empty)
- Meta Transparency Center, "Labeling AI Content": fetch returned title only. Search-summary claims (creators "must disclose" realistic AI audio on organic posts, with penalties) were NOT confirmed by Meta's primary article (see iter 29) and are treated as UNVERIFIED.
- Meta scale (search snippet, unverified): 1 trillion label views and 60 million label actions in 29 days (Oct 2024). Not used.
- Meta AudioSeal (research): audio watermarking for AI speech; detectability of a TTS voice is a live risk. Not a rule.
- Implication (revised after iter 29): no primary text in our sources requires a label for AI narration of a data reel. Disclosing the AI voice in the caption is still the low-cost, trust-preserving choice (Adobe: ~3 in 4 want disclosure).

### Iter 30 — Greek-language narration (final lead)
- Kokoro-82M (HF model page, fetched): languages "Multiple"; release table says v1.0 has 8 languages and 54 voices; Greek not named on the page. Greek voice assumed absent: verify on VOICES.md before use.
- Piper voices (github.com/rhasspy/piper/blob/master/VOICES.md, fetched): one Greek voice, el_GR "rapunzelina", quality "low". No licence or dataset note on the page; check the model card before publishing.
- Implication: an English voice is the safe default for a Kokoro/Piper narration. A Greek-language narration would need a Greek voice of verifiable licence and quality (low-quality voices are audibly robotic, which hurts trust), or a human voice. Azure free tier (iter 21) has Greek voices (unverified).

### Iter 29 — Meta primary text on AI labels (correction to iter 28)
- Meta, "Our approach to labeling AI-generated content and manipulated media" (about.fb.com/news/2024/04/..., originally 5 Apr 2024; page shows update 23 Oct 2025; fetched 2026-11-03):
  - 'AI info' applied "when we detect industry standard AI image indicators or when people disclose that they're uploading AI-generated content."
  - Content edited only with AI tools: "we are moving the 'AI info' label to the post's menu." AI-generated content still shows the label, marked as industry-signal or self-disclosed.
  - Disclosure duty stated for advertisers ("advertisers have to disclose when they digitally create or alter a political or social issue ad in certain cases"). No organic-audio disclosure rule and no penalty for organic non-disclosure in this text.
  - Fact-checked false or altered content: "we show it lower in Feed so fewer people see it."
- Source: https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/

### Iter 27 — Hootsuite Social Trends 2026 (bar missed)
- Carahsoft summary of Hootsuite's 2026 Social Media Trends (fetched; the page is a 639k-character listing, mostly encoded data): "18 key shifts"; "human-led authenticity and nuanced audience understanding now outweigh follower counts" (qualitative). No survey n or % for short-form video or AI content was readable.
- Adindex copy of the 2026 PDF exceeds the fetch size limit (10 MB). Not read.
- 2025 edition (search snippet): survey of 3,864 marketers, fielded August 2024. Older, not comparable.
- Use: confirms the direction (authenticity over reach) at medium-low confidence; no numbers taken for the baseline.

### Iter 26 — music sourcing for an original reel
- Pixabay Content License summary (pixabay.com/service/license-summary/, fetched 2026-11-03): "Use Content without having to attribute the author"; no sale or standalone use ("Standalone means where no creative effort has been applied to the Content"); content with recognisable trademarks/logos cannot be used commercially; third-party rights are the user's responsibility. Music and social-video use are not addressed on the summary page; the full licence must be read. Content ID behaviour not verified.
- Suno (AI music) free plan: multiple secondary sources say free-plan songs are for non-commercial use only and Suno owns them; paid tiers grant commercial rights for songs made while subscribed (disputed on cancellation). Terms page not accessible. Do not use Suno free-plan songs in the reel. Paid plan terms need reading before use.
- Implication: safest music is either (a) Instagram Sound Collection/TikTok CML for in-app use, or (b) a licensed library with a written licence kept on file; or (c) a sound-only reel with the voice and data graphics and no music.

### Iter 25 — animation tools and their licence fit
- Motion Canvas (github.com/motion-canvas/motion-canvas, fetched): MIT licence; TypeScript library and editor for coding vector animations; designed "to create informative vector animations and synchronize them with voice-overs" (page wording). Best fit for a voice-synced, fully programmatic reel; renders via its own tooling. Commercial use is allowed under MIT.
- matplotlib (matplotlib.org/stable/project/license.html, fetched): licence agreement for versions 1.3.0+, royalty-free, "to reproduce ... and otherwise use ... distribute"; requires retaining the copyright notice; derivative works need a summary of changes; no commercial restriction stated (not explicitly addressed). Use with FuncAnimation + ffmpeg writer for static-to-animated charts.
- Flourish free plan (flourish.studio/terms, fetched): credit required on images, videos or GIFs that contain Flourish content: "Created with flourish.studio" or equivalent, plus a hyperlink on social posts; embedded projects must keep the credit. Downloads depend on plan (not verified for Free). Implication: a Flourish bar race exported to a reel needs a visible credit on-screen. Our custom pipeline avoids this.
- MoviePy, Manim, Remotion, FFmpeg, faster-whisper, Kokoro: see iterations 12–21.

### Iter 24 — captions, sound-off viewing
- Verizon Media + Publicis Media, "Relationship of Video, Sound and Captions" (survey, April 2019, n=5,616 US adults 18–54; 3Play Media writeup 19 Jul 2019, fetched 2026-11-03): the writeup does not report the sound-off percentages; it quotes "41% of videos are incomprehensible without sound" (content, not behaviour). Secondary summaries (not verified): 69% watch sound-off in public; 25% in private; 80% more likely to finish with captions. Source: https://www.3playmedia.com/blog/verizon-media-and-publicis-media-find-viewers-want-captions/
- Facebook captions study (secondhand via 3Play and others): captions increase view time on Facebook video by 12%. No primary Meta page found; treat as secondary.
- Instapage A/B test (vendor, search snippet): captioned variant +5% average total view time, +16% reach. Single vendor test; treat as directional.
- "85% of Facebook video watched without sound": traces to Digiday 2016 reporting relying on publishers' own numbers (snippet); no primary study. Do not cite as a fact.
- Implication: captions are a low-risk default for a sound-off feed; they help a reel that opens with a voice and a number.

### Iter 23 — Reels length rules (primary, resolves iter 3)
- Instagram for Creators blog, "Finding success on reels in 2025" (21 Jan 2025; fetched 2026-11-03, https://creators.instagram.com/blog/the-latest-with-instagram): "Starting today, we're letting creators in the United States publish reels up to 3 minutes long in the Reels editor." "Previously, only reels up to 90 seconds were eligible for recommendation," but "now reels up to 3 minutes will be eligible to be seen by non-followers in places like the Reels tab and Explore."
- Help Center and Reels feature page (search snippets only): reels can be recorded/edited up to 20 minutes, but over 3 minutes are not recommended to new audiences. Creators FAQ: recommendation to unconnected audiences for videos of 3 minutes or less (snippet).
- Implication: a 30-s reel is far inside the recommendable window; the 3-minute cap is irrelevant to us. The live cap may have changed since Jan 2025 (post is ~21 months old); recheck before relying on it.

### Iter 22 — TikTok posting frequency
- Buffer, "How Often Should You Post on TikTok" (2025 TikTok Study, published 8 Oct 2025; fetched 2026-11-03): 11.4M posts from 150,000+ accounts; date range not stated. Views-per-post lift vs posting once a week (fixed-effects regression, each account against itself): 2–5/week +17%; 6–10/week +29%; 11+/week +34%. Median views: 1/week 489; 2–5 506; 6–10 487; 11+ 459. p90 views: 3,722; 6,983; 10,092; 14,401. Gains are in the top posts (viral skew), not the typical post. No follower-growth finding. Source: https://buffer.com/resources/how-often-should-you-post-on-tiktok/
- Metricool 2026 TikTok study (search snippet): 2,314,756 posts from 92,000+ accounts; average 2.54 videos per week; 16.47% of accounts moved up a follower tier in 2026. Methodology not read.
- TT Calculator (search snippet, unclear method): claims a 12-week panel of 38,000 accounts (Nov 2025–Jan 2026) where daily posting gives best growth; conflicts with Buffer; not used for the baseline.
- RivalIQ (2024, brands): 1.75 videos per week average brand cadence across 374,000+ videos (snippet, older).
- Implication: for a small account, 2–5 videos per week is the best-supported range for view lift; the gain is concentrated in the viral tail, so volume matters for finding outliers.

### Iter 21 — cloud TTS free tier and ffmpeg licence
- Azure AI Speech pricing (azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/, fetched 2026-11-03): neural TTS free tier (F0) 0.5 million characters per month. Paid rate and Greek (el-GR) voice names not present in captured text. Commercial use is allowed under Azure terms (not read). At ~1,000 characters per 30-s reel, the free tier covers ~500 reels a month, far above our needs (estimate: 30 s at ~150 words/min ≈ 75 words ≈ 450 characters per reel, so ~1,000 reels). Verify the Azure Greek voice and pricing before relying on it.
- FFmpeg legal page (ffmpeg.org/legal.html, fetched): default licence LGPL-2.1-or-later; enabling GPL options (e.g. libx264) makes the build GPL; "not available under any other licensing terms, especially not proprietary/commercial ones"; patent note warns commercial products may face licence fees. Use a standard LGPL build, or the stock Windows build with checked licence flags. Not legal advice.

### Synthesis at 20 (iterations 1–20, 130 data points, 11 accounts/brands profiled, 0 stats-specialist accounts)

Changes since synthesis at 10:
- Voice: Adobe (n=850, Feb 2026) reinforced the trust cost of AI voice in ads and news; still no sports-specific study. Confidence medium.
- Hooks: YouTube's inauthentic-content help page now gives the nearest platform test: templated, scrolling text with minimal commentary is named as non-monetisable. Our reels need a unique commentary line each time. Confidence medium for the principle, low for Instagram transfer.
- Tooling: licence picture is clear for Kokoro (Apache-2.0, v1.0 Jan 2025), Piper (MIT archived; successor GPL-3.0), Whisper and faster-whisper (MIT), Manim (MIT), MoviePy (MIT, v2 only), Remotion (free for up to 3 people; paid tiers quoted). XTTS-v2 (CPML) and edge-tts (unofficial Microsoft service) are not safe for a monetised channel. Confidence high on licences, from primary pages.
- Accounts: top basketball TikTok creators are entertainment, not stats; NBA (25.1M TikTok, 87.9M Instagram) sets the reach ceiling but is copyright-restricted. No stats-specialist account with verified numbers found yet. Confidence low.

Updated baseline:
- Posting frequency: 2–3 posts/week floor; 4–6/week median for growth (Netinfluencer 33% yearly growth at 4–6x vs 19% at 2–3x; correlational). Medium.
- Format: Reels for reach on small accounts; carousels for saves/likes. Medium.
- Times: Sprout (Nov 2025–Feb 2026, local time): Tue–Wed afternoons and evenings, Mon 2–4 pm, Thu 12–2 pm, avoid weekends. Medium; Greek-specific times unverified.
- Hashtags: cap 5 since Dec 2025; 4–5 tags best in one 1.6M-post study (+1–3%); keyword captions and on-screen text drive discovery. Medium.
- Captions/on-screen text: TikTok 5–10 words/s; burn-in our own captions. Medium.
- Hook: claim in the first 1–3 s, TikTok proposition-within-3-s. Medium.
- Length: no Instagram-specific evidence; Quso (Shorts) 11–20 s band highest median views. Low.
- Voice: AI voice plus disclosure in caption; Instagram/TikTok labels only needed for realistic AI people or realistic AI content. Medium.

### Iter 4 — (see Voice)

### Synthesis at 30 (final; iterations 1–30, 186 new sourced data points, 11 accounts or account-level records, 0 stats-specialist accounts profiled)

**Reel recipe (for a 675hoops data reel)**
- **Length:** 20–30 s (target 25 s). Shorts evidence: the 11–20 s band had the highest median views (Quso, June 2026, vendor). Instagram's 3-minute limit (Creators blog, 21 Jan 2025) is irrelevant. Confidence: low–medium.
- **Hook (0–3 s):** the result or claim as on-screen text plus the number, in the first frame. TikTok's own guidance: hook within 6 s, proposition within 3 s (ads.tiktok.com, updated June 2025). Confidence: medium.
- **Structure:** Hook (0–3 s) → one context line (3–8 s) → one animated stat build (8–22 s: counter, win-probability line or comparison card) → one human-written insight line (22–27 s) → end card that repeats the first frame so it loops, with a CTA ("next forecast Tuesday"). Each reel's commentary line must differ week to week (YouTube inauthentic-content rule names templated, minimal-commentary content).
- **Voice:** AI narration in English (Kokoro-82M, Apache-2.0) at or under 10 words/s; say "AI voice" in the caption. Greek narration has no verified-quality voice yet (Piper el_GR is low quality; Azure free tier unverified). Evidence on AI voice: Adobe (n=850, Feb 2026) trust cost in ads; ~3 in 4 want disclosure. Confidence: medium.
- **Captions:** burn in your own SRT (faster-whisper, MIT), 5–10 words/s, sized for a sound-off feed. Captions raised view time in one vendor A/B test (+5%; Instapage) and a secondhand Facebook figure (+12%). Confidence: low–medium.
- **Animation:** number counter or win-probability line; one stat per reel. Result-led graphics show higher engagement in one (undated, unsized) Zoomph analysis: 4.95% win vs 2.09% loss. Original graphics only.
- **Music:** Instagram Sound Collection or TikTok Commercial Music Library, used in-app; or no music. No Suno free-plan songs. No league footage or logos (league accounts are copyright-restricted).
- **Cadence:** 2–3 reels a week as the floor; test 4–5 a week for growth (Netinfluencer: +33% yearly growth at 4–6x vs +19% at 2–3x, correlational; Buffer TikTok: +17% views per post at 2–5/week, fixed-effects). Times (Sprout, Nov 2025–Feb 2026, local time): Mon 2–4 pm, Tue 1–7 pm, Wed 12–9 pm, Thu 12–2 pm; avoid weekends. Athens-time conversion is an estimate; verify in Insights.
- **Hashtags:** 3–5 (cap is 5 since Dec 2025); keyword-rich caption and on-screen text matter more (Mosseri, via BusinessToday). One 1.6M-post study: 4–5 tags +1–3% vs 0–1; 45% of posts have none.
- **Labels:** no AI-person avatar (that triggers the "AI-generated profile" label from 31 Aug 2026). Disclose the AI voice.

**Free tool stack (licence notes)**
- Animation: Motion Canvas (MIT; voice-sync built for it) or Remotion (free for individuals and companies up to 3 people; paid per seat from $25/month or per render, quoted via search, check remotion.dev). Manim (MIT) for formulas only. matplotlib charts (matplotlib licence: keep copyright notice). Flourish is free but needs a visible credit and link on social video.
- Video: FFmpeg on an LGPL build (LGPL-2.1+; GPL options make the whole build GPL; avoid --enable-nonfree).
- TTS: Kokoro-82M (Apache-2.0, v1.0 27 Jan 2025; per-voice licence to check). Piper: MIT on the archived original (6 Oct 2025); successor piper1-gpl is GPL-3.0. Do not use Coqui XTTS-v2 (CPML; commercial terms unread) or edge-tts (unofficial Microsoft client).
- Captions: faster-whisper (MIT; weights licence unstated) or openai/whisper (MIT).
- Data: EuroLeague data via our own pipeline. Do not scrape Basketball-Reference / Sports-Reference (terms restrict reuse and scraping; bulk data from $1,000).

**Limits of this study:** 11 accounts or account-level records (10 basketball TikTok creators, none a stats account, plus @nba); no Greek basketball account found; most benchmarks are vendor reports (Sprout, Buffer, Netinfluencer, Socialinsider, Quso, Fanpage Karma), not peer-reviewed; the Hootsuite 2026 report and the Meta help pages could not be read; 10 iterations missed the rising bar (2, 3, 17, 20, 21, 23, 27–30), as marked in the scoreboard.

**Key sources (read 2026-11-03):** creators.instagram.com/blog/the-latest-with-instagram (21 Jan 2025); techcrunch.com/2026/08/31/instagram-puts-new-limits-on-undisclosed-ai-profiles/; ads.tiktok.com/help/article/creative-best-practices?lang=en; buffer.com/resources/how-often-should-you-post-on-tiktok/; socialinsider.io/instagram-benchmarks; netinfluencer.com (Instagram carousels vs Reels); sproutsocial.com/best-times-to-post/instagram-media; businesstoday.in (19 Dec 2025, hashtag cap); about.fb.com (Meta AI labels, 5 Apr 2024); support.google.com/youtube/answer/1311392; adobe.com/express/learn/blog/ai-audio-consumer-trust (18 Feb 2026); remotion.dev/docs/license/pricing; github.com/rhasspy/piper (archived); huggingface.co/hexgrad/Kokoro-82M; ffmpeg.org/legal.html; pixabay.com/service/license-summary/; datareportal.com/reports/digital-2026-greece (8 Nov 2025).

