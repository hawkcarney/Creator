"""Speech-to-text with word timestamps.

Default backend is faster-whisper on CPU (int8). It works on any machine, AMD included;
faster-whisper's GPU path is NVIDIA-only. Output format, saved as transcript.json:
    {"segments": [{"start": s, "end": s, "text": "...", "words": [{"start": s, "end": s, "word": "..."}]}]}
"""


def transcribe(path, model="small", language="en", device="cpu", compute_type="int8"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("faster-whisper is not installed: pip install faster-whisper (or run with --no-transcribe)")

    whisper = WhisperModel(model, device=device, compute_type=compute_type)
    segments, _ = whisper.transcribe(str(path), language=language, word_timestamps=True, vad_filter=True)
    out = []
    for seg in segments:
        out.append(
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
                "words": [{"start": w.start, "end": w.end, "word": w.word.strip()} for w in (seg.words or [])],
            }
        )
    return {"segments": out}


def words_in(transcript, start, end):
    if not transcript:
        return []
    return [w for s in transcript["segments"] for w in s["words"] if w["start"] >= start and w["end"] <= end]


def text_in(transcript, start, end):
    return " ".join(w["word"] for w in words_in(transcript, start, end))
