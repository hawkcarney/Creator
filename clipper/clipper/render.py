"""Renders 1080x1920 vertical clips with ffmpeg.

Layouts:
  meme  the account's format: full 16:9 frame on black, empty space on top for the caption box
  crop  center crop to fill the whole 9:16 frame (works when the action is in the middle)
"""

import os
import re
import sys
import textwrap
from pathlib import Path

from .media import FFMPEG, _run
from .transcribe import words_in

W, H = 1080, 1920
VIDEO_Y = 700            # meme layout: top of the video; caption sits in the space above
CAPTION_SIZE = 62
CAPTION_CHARS = 26       # wrap width at that size

DEFAULT_FONTS = {
    "win32": "C:/Windows/Fonts/arialbd.ttf",
    "darwin": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
}
LINUX_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# drawtext can't draw color emoji; strip them rather than render empty boxes.
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def default_font():
    return DEFAULT_FONTS.get(sys.platform, LINUX_FONT)


def _filter_path(p):
    # ffmpeg filter args: forward slashes, escaped drive colon (C\:/...), quoted.
    return "'" + str(p).replace("\\", "/").replace(":", "\\:") + "'"


def caption_filters(text, font, top_of_video, work_dir, stem):
    """One drawtext per line, each with its own white box, bottom line sitting just above the video.

    Each line goes through a text file (no expansion) so quotes, colons and % never need escaping.
    """
    text = _EMOJI.sub("", text).strip()
    lines = textwrap.wrap(text, CAPTION_CHARS) or []
    line_h = int(CAPTION_SIZE * 1.45)
    y0 = top_of_video - 60 - line_h * len(lines)
    filters = []
    for i, line in enumerate(lines):
        name = f"{stem}.cap{i}.txt"
        (Path(work_dir) / name).write_text(line, encoding="utf-8")
        filters.append(
            f"drawtext=fontfile={_filter_path(font)}:textfile={name}:expansion=none"
            f":fontsize={CAPTION_SIZE}:fontcolor=black:box=1:boxcolor=white:boxborderw=18"
            f":x=(w-text_w)/2:y={y0 + i * line_h}"
        )
    return filters


def _ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def write_subs(path, words, offset, per_chunk=3):
    """Word-by-word captions in the lower third, 3 words at a time."""
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "BorderStyle, Outline, Shadow, Alignment, MarginV\n"
        "Style: Default,Arial,78,&H00FFFFFF,&H00000000,&H00000000,1,1,5,0,2,520\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Text\n"
    )
    events = []
    for i in range(0, len(words), per_chunk):
        chunk = words[i : i + per_chunk]
        text = " ".join(w["word"] for w in chunk).upper().replace("{", "").replace("}", "")
        events.append(f"Dialogue: 0,{_ass_time(chunk[0]['start'] - offset)},{_ass_time(chunk[-1]['end'] - offset)},Default,{text}")
    Path(path).write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def render(src, out, start, end, layout="meme", caption=None, transcript=None, subs=False,
           font=None, encoder="libx264"):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    font = font or default_font()

    if layout == "meme":
        chain = [f"scale={W}:-2", f"pad={W}:{H}:0:{VIDEO_Y}:black"]
        if caption:
            if not os.path.exists(font):
                raise SystemExit(f"Font not found: {font}. Set font_file in config.toml.")
            chain += caption_filters(caption, font, VIDEO_Y, out.parent, out.stem)
    elif layout == "crop":
        chain = ["crop='min(iw,ih*9/16)':ih", f"scale={W}:{H}"]
    else:
        raise ValueError(f"unknown layout {layout!r}")

    if subs and transcript:
        ass = out.with_suffix(".ass")
        write_subs(ass, words_in(transcript, start, end), start)
        # Relative name + cwd avoids Windows drive-letter escaping in the subtitles filter.
        chain.append(f"subtitles={ass.name}")
    chain.append("setsar=1")

    codec = ["-c:v", encoder]
    codec += ["-preset", "veryfast", "-crf", "20"] if encoder == "libx264" else ["-b:v", "8M"]
    _run([FFMPEG, "-y", "-hide_banner", "-ss", f"{start:.2f}", "-i", str(Path(src).resolve()),
          "-t", f"{end - start:.2f}", "-vf", ",".join(chain), *codec, "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out.name], cwd=out.parent)
    return out
