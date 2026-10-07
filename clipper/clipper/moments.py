"""Finds candidate clip windows from audio spikes (and speech bursts, when a transcript exists).

Streamer highlights are loud: yelling, laughing, hype. Loudness is judged against a rolling
baseline so a quiet streamer's outburst counts as much as a loud streamer's.
"""

from statistics import median

from .transcribe import text_in


def _rolling_median(values, half_window):
    out = []
    for i in range(len(values)):
        lo, hi = max(0, i - half_window), min(len(values), i + half_window + 1)
        out.append(median(values[lo:hi]))
    return out


def _smooth(values, half_window):
    out = []
    for i in range(len(values)):
        lo, hi = max(0, i - half_window), min(len(values), i + half_window + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def second_scores(levels, transcript=None, baseline_s=30, speech_weight=1.5):
    """Score per second: dB above local baseline, plus a bonus for unusually fast speech."""
    if not levels:
        return []
    n = levels[-1][0] + 1
    db = [-100.0] * n
    for t, v in levels:
        db[t] = v
    base = _rolling_median(db, baseline_s)
    score = [max(0.0, d - b) for d, b in zip(db, base)]

    if transcript:
        wps = [0] * n
        for seg in transcript["segments"]:
            for w in seg["words"]:
                t = int(w["start"])
                if 0 <= t < n:
                    wps[t] += 1
        wbase = _rolling_median(wps, baseline_s)
        score = [s + speech_weight * max(0, w - b) for s, w, b in zip(score, wps, wbase)]

    return _smooth(score, 1)


def _snap(transcript, start, end, slack=4.0):
    """Nudge edges to sentence boundaries so clips don't start or end mid-word."""
    if not transcript:
        return start, end
    starts = [s["start"] for s in transcript["segments"] if start - slack <= s["start"] <= start + slack]
    ends = [s["end"] for s in transcript["segments"] if end - slack <= s["end"] <= end + slack]
    if starts:
        start = min(starts, key=lambda x: abs(x - start))
    if ends:
        end = min(ends, key=lambda x: abs(x - end))
    return start, end


def find(levels, duration, transcript=None, lead=18, tail=8, min_len=12, max_len=60, min_gap=45, limit=20):
    """Top `limit` non-overlapping windows around the loudest moments, best first."""
    scores = second_scores(levels, transcript)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    peaks = []
    for i in order:
        if scores[i] <= 0 or len(peaks) >= limit:
            break
        if all(abs(i - p) >= min_gap for p in peaks):
            peaks.append(i)

    out = []
    for rank, p in enumerate(peaks, 1):
        start, end = _snap(transcript, max(0.0, p - lead), min(duration, p + tail))
        if end - start > max_len:
            start = max(0.0, end - max_len)
        if end - start < min_len:
            end = min(duration, start + min_len)
        out.append(
            {
                "id": rank,
                "peak": p,
                "start": round(start, 2),
                "end": round(end, 2),
                "signal": round(scores[p], 2),
                "transcript": text_in(transcript, start, end),
            }
        )
    return out
