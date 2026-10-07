# Project audit and handoff

_Written 2026-10-07 at the end of the first planning/build session. Read this before doing anything in this repo._

---

## 1. Who and what

**The owner:** runs TikTok **@triadhawk** ("Tea Baggins") and is an amateur **boxer** who knows fighting well. GitHub: `hawkcarney`.

**The account:**
- 34.5K followers, 3.7M likes.
- Hits: 19.9M, 4.2M, 1.9M, 1.6M, 1.3M, 1.2M, 1.2M, 771.8K.
- It went dormant when life got busy.
- It's still enrolled in **TikTok Creator Rewards**, but needs **100K views in the last 30 days** to count again.

**How the old content was made:** almost all of it was **viral clips found online (Reels etc.) with a deadpan caption added**, not footage the owner filmed. A few Rocket League highlights were their own gameplay; others were streamers'. The proven skill is **curation plus caption writing**, not filming.

**Goal:** make money from short-form video, with Claude and cheaper models doing the repetitive work and the owner doing taste and final approval.

**Home PC:** AMD **RX 7900** GPU. **OS not confirmed yet; ask.** Probably Windows.

**Working style the owner wants:**
- Super simple, plain-language steps. They said the plans got "complicated as hell."
- Short lists.
- Honest pushback; no yes-man.
- Analyze when they say "just analyze," and don't build.

---

## 2. Decisions so far, and why

| Decision | Reason |
|---|---|
| **No more reposting unlicensed viral clips for money** | Creator Rewards only pays for **original videos over 1 minute**; reposts, duets, stitches and slideshows are excluded. Reposts also risk copyright takedowns, and repeat strikes get accounts banned. The owner may still repost occasionally; that's their call, so credit the creator and delete anything that gets a notice |
| **Paid clipping campaigns (Whop) are the main volume source** | Same skill (find the moment, write the caption), but the footage comes with permission and pays per view |
| **Boxing voice-over series is the Creator Rewards earner** | Original, over 1 minute, uses real expertise. The owner is fine doing this sometimes, but voice-only is preferred to face on camera |
| **Faceless AI YouTube factory: rejected** | It's the most crowded lane and the exact target of YouTube's inauthentic-content policy, and it throws away the owner's real edges |
| **Fresh YouTube Shorts clip channel: parked** | The existing TikTok audience skips the zero-views months. `niche-scout/` exists if YouTube comes back up |
| **Avoid gambling and crypto campaigns** | Roobet, Stake, casino streams and crypto presales pay more because they're risky. TikTok cracks down on gambling promotion, and the account is the asset |

### Weekly plan agreed

| Day | Post |
|---|---|
| Most days | 1 Whop campaign clip, on the main account, only if it fits the page's humor |
| 2–3× a week | Boxing voice-over breakdown, over 1 minute |
| Whenever available | Own Rocket League highlights |
| Later | A second account for extra campaign volume, if the main page starts feeling like an ad feed |

### Boxing series ideas

- "Boxer rates movie fight scenes"
- "Boxer reacts to viral street fights"
- "Rating celebrities' punching form"
- "Things only boxers understand"

Movie and anime fights are evergreen. **Avoid pro fight broadcast footage**, because promoters file takedowns fast.

---

## 3. Facts researched (October 2026; verify before relying on numbers)

**TikTok Creator Rewards**
- Requires 18+, 10K followers, 100K views in 30 days, and a personal account.
- Pays only for **original videos over 1 minute** with at least 1K For You views.
- Reported pay: about $0.40–$1.00 per 1,000 qualified views.
- Since 2026-08-31, paid or branded posts need TikTok's **commercial content disclosure** toggle on.

**Whop Content Rewards**
- Brands, streamers and creators fund campaigns; clippers post and get paid per verified view.
- Reported rates: $0.20–$6 per 1,000 views, averaging about $1. Typical live rates are $0.50–$1.50.
- Whop takes about 7–10%, and payouts arrive roughly 10 days after approval.
- Auto-approval happens within about 48 hours.
- Budgets are first-come, first-served, so skip campaigns more than 80–90% spent.
- Clips can be rejected after views come in. Screenshot analytics at 24 hours and 7 days.

**Campaigns that fit the page, best first:**
1. Gaming streamers
2. Video games
3. Comedy podcasts
4. Boxing / MMA / influencer boxing

Searches to try in Whop: "streamer", "Twitch", "Kick", "gaming", "podcast", "boxing", "MMA". Check before joining: at least $1 per 1,000 views, lots of budget left, TikTok allowed, existing accounts allowed.

**MrBeast's Vyro** (outside Whop): reportedly a flat $3 per 1,000 views, capped at $1,000 per clip. Worth checking.

**YouTube**
- Partner Program needs 1,000 subscribers plus either 4,000 watch hours in 12 months or 10M Shorts views in 90 days. Views from before joining earn nothing.
- Shorts pay roughly $0.05–$0.15 per 1,000 views; finance pays somewhat more.
- API uploads from unaudited projects are **forced to private**.

**Instagram:** the main Reels bonus program ended around 2023. Treat "Reels bonus income" claims skeptically.

---

## 4. What's in this repo

### `clipper/`: the main tool

Footage → candidate moments → ranked, trimmed 9:16 clips with caption options.

**Pipeline:**
1. ffmpeg loudness scan against a rolling baseline, plus speech-burst scoring when there's a transcript.
2. **Haiku 4.5** screens every candidate.
3. **Opus 5.5** picks the top 8, trims each to setup and payoff, and writes 5 captions in the owner's voice. It's given the owner's real top captions as examples.
4. Renders **1080×1920 in the account's "meme" layout**: the full 16:9 frame on black with space above for a white-box caption. Optional word subtitles and a `crop` layout.
5. Writes `review.md`.

**Usage:**
- `python -m clipper run VIDEO --context "..."`
- `python -m clipper render VIDEO --pick N --caption-option N [--burn]`

**Behavior details:**
- If the API errors or refuses, it falls back to loudness ranking.
- The Opus call uses server-side `fallbacks: "default"`.
- `--burn` drops emoji, since ffmpeg's drawtext can't render them. The recommended path is adding the caption in TikTok's own text tool.

**Tests:** 11 unittest cases. They generate a synthetic video with ffmpeg and use a fake Claude client.

**Not yet verified for real:**
- faster-whisper transcription (the model download was blocked in the cloud session).
- Live Claude API calls (no key in the cloud session).

**The first real run on the home PC is the priority.**

### `niche-scout/`: parked

A YouTube Data API niche tracker (outlier ratio, small-channel breakouts, growth). Stdlib only. Needs `YOUTUBE_API_KEY`. Only useful if YouTube becomes a focus.

---

## 5. To-do, in order

### Owner

1. [ ] Open this repo in a **local** Claude Code session on the home PC (Claude desktop app → Code). Plugins only work in local sessions.
2. [ ] Confirm the OS. Install Python 3.11+ and ffmpeg. On Windows: `winget install Gyan.FFmpeg`.
3. [ ] `pip install -r clipper/requirements.txt`, then set `ANTHROPIC_API_KEY`.
4. [ ] In Whop, search the campaign keywords above, screenshot 5–10 listings, and have Claude pick the best 2.
5. [ ] Download one campaign's footage and do the first real `clipper run`. Give feedback on which captions are bad.
6. [ ] Screenshot TikTok Studio audience stats: countries, age, and the videos that drove follows.
7. [ ] Post daily per the weekly plan, and screenshot each campaign clip's views at 24 hours and 7 days.

### Claude

1. [ ] Babysit the first real clipper run and fix whatever breaks: whisper download, fonts on Windows, `h264_amf`.
2. [ ] Write **20 ready-to-film boxing voice-over ideas** (offered; owner hasn't answered yet).
3. [ ] Add a **whisper.cpp Vulkan** transcription backend so the RX 7900 does transcription. A pre-built Windows Vulkan build exists.
4. [ ] Add **face-tracking reframe** for the `crop` layout. Idea from `yt-short-clipper`.
5. [ ] Add **Twitch chat-spike detection** as a moment signal. Idea from `stream-clipper`; data via TwitchDownloader.
6. [ ] Add a **views and payout tracker** per clip: campaign, post URL, 24-hour and 7-day views, paid amount.
7. [ ] Feed caption winners back into `clipper` config `[[style]]` as new hits come in.

---

## 6. Plugins, connectors and tools

### Installed by the owner (local sessions only)

**Social Media Skills** (106 skills; community, unvetted quality). Use these, and treat the owner's own caption instinct as the stronger signal:

| Skill | Use it for |
|---|---|
| `caption-writer`, `hook-writer`, `meme-and-culture` | Caption options |
| `captions-and-clipping`, `opus-clip`, `capcut` | Editing workflows |
| `viral-reverse-engineering`, `trend-jacking` | Finding what's working now |
| `tiktok-growth`, `tiktok-script`, `short-form-video-script` | The boxing series |
| `content-calendar`, `batch-content-plan` | Weekly planning |
| `creator-monetization`, `collabs-and-cross-promotion` | Promos and brand deals |
| `analytics-and-reporting` | Reviewing performance |

**Other plugins:** the owner said "and others" without naming them. Check with `/plugin` or the plugin list.

### Recommended for later

**Posty: Social Media Scheduler** posts and schedules to TikTok, YouTube Shorts and Reels with browser sign-in. Use it once posting is daily. It's community-built and gets account access, so start with Reels and Shorts, not the main TikTok.

### Connected

**Canva** is connected on the claude.ai account. Use it for cover images and caption-box templates.

### Skip

These are for paid ads, and the owner isn't buying ads: Trackian, AdvisorPPC, Windsor.ai, Supermetrics, AdWhispr, Hyper Marketing. Anthropic's Marketing plugin is brand-oriented and low value here.

### GitHub tools (not code-reviewed; check a repo before the owner runs it)

| Tool | What it's for |
|---|---|
| whisper.cpp, Vulkan Windows build (DomoticX/whisper.cpp-windows-vulkan; pre-built via whisper-windows-mcp) | AMD GPU transcription |
| yt-dlp | Downloading campaign footage from links |
| TwitchDownloader | VODs and chat logs, for streams you're permitted to clip |
| LosslessCut | Fast manual trims |
| yt-short-clipper, stream-clipper, artbyjazi/autoclip, SamurAIGPT/AI-Youtube-Shorts-Generator | Comparable clippers, mined for ideas above |

---

## 7. Outside content the owner shared, already analyzed

**X post: "Claude faceless YouTube framework"**
- Long-form high-RPM niches (finance, tech, business). Its RPMs are best-case long-form figures.
- It ignores the inauthentic-content policy. Wrong business for this owner.

**"$15,400/month three-platform system" article**
- Unverifiable income, and it funnels readers to a Telegram.
- It's wrong that Reels Bonus is still a normal income stream.
- Its `publish.py` won't work as claimed: YouTube forces unaudited uploads to private, TikTok needs app audit before public posting, and the CI OAuth flow can't complete without a browser.
- The good ideas in it (repurposing, per-platform captions, analytics loop, don't quit at video 12) are already folded in.

**ChatGPT comparison:** the owner dropped it; they said it was confused.
