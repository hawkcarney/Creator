"""ffmpeg/ffprobe helpers. Everything shells out; no Python media libraries needed."""

import json
import re
import subprocess

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


class MediaError(Exception):
    pass


def _run(cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise MediaError(f"{cmd[0]} failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
    return proc


def probe(path):
    """Duration in seconds plus the first video stream's size."""
    out = _run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]).stdout
    info = json.loads(out)
    video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError(f"{path} has no video stream")
    return {
        "duration": float(info["format"]["duration"]),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "has_audio": any(s.get("codec_type") == "audio" for s in info["streams"]),
    }


_PTS = re.compile(r"pts_time:([\d.]+)")
_RMS = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-inf|inf|nan)")


def loudness(path, rate=16000):
    """RMS level in dB for each second of audio: [(second, db), ...]. Silence is -100."""
    af = (
        f"asetnsamples=n={rate}:p=0,astats=metadata=1:reset=1,"
        "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-"
    )
    out = _run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate),
                "-af", af, "-f", "null", "-"]).stdout
    levels, t = [], None
    for line in out.splitlines():
        if m := _PTS.search(line):
            t = float(m.group(1))
        elif (m := _RMS.search(line)) and t is not None:
            v = m.group(1)
            db = float(v) if v not in ("-inf", "inf", "nan") else -100.0
            levels.append((int(round(t)), max(db, -100.0)))
            t = None
    return levels
