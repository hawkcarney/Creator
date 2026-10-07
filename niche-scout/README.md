# niche-scout

Collects YouTube data so we can choose a channel strategy from evidence: streamer clips or faceless long-form (finance, tech/AI, business stories). Shorts or long-form.

It runs once a day on your PC and saves to a local SQLite file. It has no dependencies beyond Python 3.11+.

## What it measures

Every day it searches each niche's queries, takes snapshots of the stats for every video and channel it finds, and re-checks videos from the last 14 days so you get **growth curves**, not one-off view counts.

`report` compares the niches on:

| Column | Meaning | Why it matters |
|---|---|---|
| `med views`, `views/day` | Typical performance of what ranks | Size of the prize |
| `outlier` | Views ÷ channel subscribers | Above 1 means the algorithm is pushing videos beyond the channel's own audience |
| `small%` | Share of results from channels under 50k subs | Whether newcomers can rank at all |
| `breakouts` | Small-channel videos at 5× or more their sub count | **The key number.** Proof a nobody can win here |
| `chans` vs `vids` | Concentration | 50 videos from 4 channels means incumbents own the niche |
| `growth/day` | Views gained between snapshots | Momentum. Available after 2+ days of scans |
| `est $/vid` | Median views × your RPM guess | Only as good as the RPM numbers in your config |

The "Top small-channel breakouts" list gives you real videos to study for titles, thumbnails and hooks.

**Bias warning:** search sorts by `viewCount` by default, so you are looking at the winners. Compare niches against each other rather than trusting the absolute numbers. Add `"date"` to `orders` in the config to also sample typical uploads.

## Setup (about 10 minutes)

1. **Python 3.11+**: `python --version`. Get it from python.org if needed (on Windows, tick "Add to PATH").
2. **YouTube API key** (free):
   - Go to https://console.cloud.google.com/, create a project, then **APIs & Services → Library** and enable **YouTube Data API v3**.
   - **Credentials → Create credentials → API key.** Restrict it to YouTube Data API v3.
3. **Config**: `cp config.example.toml config.toml`, then edit the queries to match what you want to test.
4. **Key in env var** (keeps it out of files):
   - macOS/Linux: `export YOUTUBE_API_KEY=...` (add it to `~/.zshrc` or `~/.bashrc`)
   - Windows: `setx YOUTUBE_API_KEY "..."` (then open a new terminal)

## Usage

```
python -m niche_scout scan                 # gather data (~3,500 of 10,000 daily quota units with the default config)
python -m niche_scout report               # compare niches over the last 7 days
python -m niche_scout report --days 14 --csv out.csv
python -m niche_scout status               # quota used today, row counts
python -m unittest                         # tests
```

Quota: each search costs 100 units, stat lookups cost 1 per 50 videos. Google resets the quota at midnight Pacific. The scan stops cleanly and keeps partial data if it runs out.

## Run it daily

**Windows (Task Scheduler):** Create Basic Task → Daily → Action "Start a program":
- Program: `python`
- Arguments: `-m niche_scout scan`
- Start in: the full path to this folder

**macOS/Linux (cron):** `crontab -e`, then:

```
15 9 * * * cd /path/to/niche-scout && YOUTUBE_API_KEY=... /usr/bin/python3 -m niche_scout scan >> data/scan.log 2>&1
```

Let it run for **2–3 weeks** before drawing conclusions. One day of data is anecdote.

## Data policy

YouTube's API policies require stored API data to be refreshed or deleted after 30 days, so every scan prunes anything older than `retention_days`. Export a CSV if you want to keep your own analysis.
