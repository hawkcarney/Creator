# Creator

Tools and plans for the owner's short-form video business. The main account is TikTok @triadhawk.

**Read `docs/AUDIT.md` first.** It has the owner's situation, the decisions made and why, researched platform facts, plugin notes and the prioritized to-do list. Update it when decisions or state change.

## Layout

- `clipper/`: footage → ranked, trimmed 1080×1920 clips with caption options. This is the main tool. Run tests with `cd clipper && python -m unittest`.
- `niche-scout/`: YouTube niche data tracker. Parked. Run tests with `cd niche-scout && python -m unittest`.
- `docs/AUDIT.md`: the source of truth for plan and status.

## Rules

- Keep explanations to the owner short and in plain language, as simple step lists. Push back honestly when something is a bad idea.
- Only build pipelines for footage the owner has rights to: campaign footage, permitted streamers, or their own. Don't build tooling for mass reposting or for dodging platform originality and copyright systems.
- Avoid gambling and crypto campaigns. They put the account at risk.
- Nothing posts automatically without the owner reviewing it.
- Python 3.11+. clipper's runtime deps are `anthropic` and `faster-whisper`, plus ffmpeg on PATH. niche-scout is stdlib only.
- Claude API code: check current model IDs and parameters before editing `clipper/clipper/llm.py`. Don't rely on memory.
- Run the relevant tests before every commit.
