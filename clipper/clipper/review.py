"""Writes review.md: one place to skim picks, watch clips and choose captions."""

from pathlib import Path


def ts(seconds):
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def write(path, video, picks, used_llm):
    lines = [f"# Review: {Path(video).name}", ""]
    if not used_llm:
        lines += ["_Ranked by loudness only (no transcript or no LLM). Captions are up to you._", ""]
    for i, p in enumerate(picks, 1):
        clip = p.get("clip")
        lines.append(f"## {i}. {ts(p['start'])}–{ts(p['end'])} ({p['end'] - p['start']:.0f}s)")
        if clip:
            lines.append(f"Clip: [{Path(clip).name}](clips/{Path(clip).name})")
        if p.get("why"):
            lines.append(f"\n{p['why']}")
        if p.get("needs_visual_check"):
            lines.append("\n**Watch it first:** the payoff may be visual, and the AI only read the transcript.")
        if p.get("captions"):
            lines.append("\nCaption options:")
            lines += [f"{n}. {c}" for n, c in enumerate(p["captions"], 1)]
        if p.get("transcript"):
            excerpt = p["transcript"] if len(p["transcript"]) < 400 else p["transcript"][:400] + "…"
            lines.append(f"\n> {excerpt}")
        lines.append(
            f"\nFinalize: `python -m clipper render \"{video}\" --pick {i} --caption-option 1 --burn`"
            " (or skip --burn and add the caption in TikTok's text tool)"
        )
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return path
