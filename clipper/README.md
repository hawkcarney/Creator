# clipper

Turns campaign footage or a VOD into ready-to-post vertical clips:

```
video → loudness scan + transcript → candidate moments
      → Haiku screens all of them → Opus picks the best, trims them, drafts 5 captions each
      → 1080×1920 clips + review.md
```

You watch the clips, pick a caption, and post. **Nothing is posted automatically.**

Only use footage you have rights to: campaign-provided clips, streamers who allow clipping, or your own.

## Setup (Windows, macOS or Linux)

1. **Python 3.11+**
2. **ffmpeg** on your PATH.
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
3. `pip install -r requirements.txt`
4. **Anthropic API key** from console.anthropic.com, set as `ANTHROPIC_API_KEY`.
   - Windows: `setx ANTHROPIC_API_KEY "..."`, then open a new terminal.
   - Without a key, run with `--no-llm` and clips are ranked by loudness only.

The first transcription downloads the whisper model (about 500 MB for `small`). After that it runs offline.

## Use

```
python -m clipper run "D:\footage\kai_stream.mp4" --context "Kai Cenat playing Fortnite with friends"
```

Then open `work/kai_stream/review.md`. Each pick has its clip, why it was picked, 5 caption options, and the transcript.

Finalize one:

```
python -m clipper render "D:\footage\kai_stream.mp4" --pick 2 --caption-option 3 --burn
```

- **Without `--burn`**, add the caption in TikTok's own text tool. It looks native and keeps emoji, since burned captions drop them.
- **`--subs`** adds word-by-word subtitles under the video.
- **`--layout crop`** fills the whole frame instead of the meme layout.

Re-running is cheap: loudness and transcripts are cached per video. Use `--fresh` to redo them.

## How picking works

1. **Loudness spikes against a rolling baseline.** Yelling, laughing and hype stand out, even from a quiet streamer. Fast speech adds to the score when there's a transcript.
2. **Haiku 4.5 screens every candidate** from its transcript. It's cheap and catches the obvious duds.
3. **Opus 5.5 gets the top 8.** It keeps only what it would actually post, trims each to setup and payoff, and writes 5 captions in your voice, learned from your past hits.

The models only read transcripts. When a payoff might be visual, the review sheet says **Watch it first**.

**Cost:** two API calls per video. Roughly cents per video; the transcript size drives it.

## AMD GPU (RX 7900)

- **Rendering:** set `encoder = "h264_amf"` in config.toml to encode on the GPU (Windows builds of ffmpeg).
- **Transcription:** runs on the CPU here, because faster-whisper's GPU support is NVIDIA-only. Fine for campaign clips. For long VODs, use `whisper_model = "base"`. The planned upgrade is whisper.cpp with Vulkan, which runs on AMD GPUs.

## Tests

```
python -m unittest
```

The tests generate a synthetic video with ffmpeg and run the full pipeline against a fake Claude client. No API key or network needed.
