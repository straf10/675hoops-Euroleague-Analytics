# Social media baseline: summary (2026-11-03)

Four research agents, 30 iterations each (rules: `RULES.md`). Details and sources are in the per-agent files:
`A_euroleague_ig_tiktok.md`, `B_nba_stats_short_video.md`, `C_x_reddit.md`, `D_formats_voice_animation.md`.
Instagram, TikTok, X, Social Blade and HypeAuditor mostly blocked automated reading, so account-level numbers are thin
and many benchmarks come from vendor reports. Confidence is given per point.

## The opening

- No independent EuroLeague or Greek basketball **stats** page with public numbers was found on Instagram or TikTok
  (three search rounds, English and Greek). The space is held by the league, the clubs and news sites. (medium)
- No Greek basketball subreddit exists; r/Euroleague has about 38-41K members and about 31 posts a month. (medium)
- The closest realistic peer: panathinaikos24.gr on Instagram, 23.5K followers, 6.8% engagement rate. (low-medium)

## Formats

| Platform | What works | Confidence |
|---|---|---|
| Instagram | Carousels 0.55% engagement vs Reels 0.50% vs images 0.45% (Socialinsider 2025); carousels lead on saves. NBA team accounts post about 51% video, 29% images, 20% mixed. Use 1080x1350. | high (direction) |
| TikTok / Reels | 20-30 s (target 25 s). Claim or result as on-screen text in frame 1; one animated stat; end card that loops back to frame 1. | low-medium |
| X | Image posts beat text and video (0.79 / 0.68 / 0.54%); 100-200 characters; one stat per image. | medium |
| Reddit | Self-made `[OC]` charts, source and tool in the first comment, neutral titles, at most one link post a week, about 10% self-promotion; build comment history first. Read the r/Euroleague sidebar by hand before posting (not readable by the agents). | medium |

## Content that works

- Results and round recaps, efficiency or "landscape" charts, named recurring series (e.g. a weekly round card). (medium)
- Forecast accounts that show their misses and method build trust (The Margin's calibration page). (low-medium)
- Question- or claim-titled short videos pull the most views among analysis channels. (low-medium)

## Voice and AI

- **None of the verified stats or analysis accounts uses an AI voice.** They use human narration or text on screen. (medium)
- Instagram, TikTok and YouTube require labels for realistic AI content. Data graphics are exempt; an AI voice should be
  disclosed in the caption. Consumer trust in AI audio is mixed (Adobe survey, n=850, Feb 2026).
- No good free Greek AI voice was verified.
- Suggestion: start with text on screen plus captions (no voice). Test an English AI voice (Kokoro-82M) as a variant and
  keep the one that holds viewers longer.

## Cadence and timing

- Reels: 2-3 a week at least; test 4-5. Carousels or images around each round (preview, recap, projections).
- Best times (Sprout Social, local time): weekdays early to mid afternoon; weekends weaker. The conversion to Athens time is an estimate.
- Hashtags: 3-5 (Instagram caps hashtags at 5 since Dec 2025); keywords in the caption matter more.

## Legal

- No league footage, club logos or player photos; EuroLeague publishes no fan-content policy. Use original charts made
  from public box-score numbers.
- Don't scrape Basketball-Reference (its terms restrict reuse). Our data comes from the EuroLeague API cache.
- Music: the in-app commercial libraries, or none.

## Free tool stack (licences checked 2026-11-03)

- Video: matplotlib + FFmpeg (LGPL build) or Motion Canvas (MIT). Remotion is free only for teams of up to 3 people;
  check its terms.
- Voice: Kokoro-82M (Apache-2.0; check each voice). Avoid XTTS-v2 (non-commercial licence) and edge-tts (unofficial
  client). The original Piper is MIT but archived; its successor is GPL-3.0.
- Captions: faster-whisper or whisper (MIT).

## Gaps

- No post-level data (hooks, captions, posting times) for any EuroLeague account.
- StatMuse, Hoop Central and Basketball-Reference social accounts could not be verified.
- Follow-up, if wanted: profile A's shortlist via vidIQ and YouTube pages, which load.
