"""CLI.

  python -m clipper run VIDEO --context "Kai Cenat playing Fortnite"
      find moments -> rank -> render the top picks -> write review.md
  python -m clipper render VIDEO --pick 2 --caption-option 3 --burn
      re-render one pick as a final clip, optionally with the caption burned in
"""

import argparse
import json
from pathlib import Path

from . import config as config_mod
from . import llm, media, moments, review
from .render import render
from .transcribe import transcribe


def _cached(path, fresh, compute):
    path = Path(path)
    if path.exists() and not fresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = compute()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def work_dir(cfg, video):
    d = Path(cfg.work_dir) / Path(video).stem
    (d / "clips").mkdir(parents=True, exist_ok=True)
    return d


def cmd_run(cfg, args, client=None):
    video = args.video
    d = work_dir(cfg, video)
    info = media.probe(video)
    if not info["has_audio"]:
        raise SystemExit("This video has no audio track; moment finding needs audio.")

    print(f"[1/5] Loudness scan ({info['duration'] / 60:.0f} min of audio)")
    levels = _cached(d / "levels.json", args.fresh, lambda: media.loudness(video))

    transcript = None
    if not args.no_transcribe:
        print(f"[2/5] Transcribing with whisper '{cfg.whisper_model}' on CPU (slow the first time; cached after)")
        transcript = _cached(d / "transcript.json", args.fresh,
                             lambda: transcribe(video, cfg.whisper_model, cfg.language))
    else:
        print("[2/5] Skipping transcription")

    cands = moments.find(levels, info["duration"], transcript, cfg.lead, cfg.tail, cfg.min_len,
                         cfg.max_len, cfg.min_gap, cfg.max_candidates)
    print(f"[3/5] {len(cands)} candidate moments")
    (d / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")

    used_llm = bool(transcript and cands) and not args.no_llm
    picks = cands
    if used_llm:
        print(f"[4/5] Screening with {cfg.screen_model}, picking with {cfg.pick_model}")
        try:
            llm.screen(cands, args.context, cfg.screen_model, client)
            shortlist = sorted(cands, key=lambda c: (c["screen_score"], c["signal"]), reverse=True)[: cfg.pick_top]
            picks = llm.pick(shortlist, args.context, cfg.style, cfg.pick_model, cfg.pick_effort, client)
        except Exception as e:  # API/auth/network errors or a refusal: degrade, don't lose the run
            if not isinstance(e, llm.LLMError) and type(e).__module__.split(".")[0] != "anthropic":
                raise
            print(f"  Claude ranking failed ({e}); falling back to loudness ranking")
            used_llm, picks = False, cands
        if used_llm and not picks:
            print("  Opus didn't think any moment was worth posting. Try --no-llm to see the loudest ones anyway.")
    else:
        print("[4/5] Ranking by loudness only")
    picks = picks[: args.top or cfg.render_top]

    print(f"[5/5] Rendering {len(picks)} clips ({cfg.layout} layout)")
    for i, p in enumerate(picks, 1):
        out = d / "clips" / f"{i:02d}_{int(p['start'])}s.mp4"
        render(video, out, p["start"], p["end"], cfg.layout, transcript=transcript, subs=args.subs,
               font=cfg.font_file or None, encoder=cfg.encoder)
        p["clip"] = str(out)
        print(f"  {out}")

    (d / "picks.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
    sheet = review.write(d / "review.md", video, picks, used_llm)
    print(f"\nReview: {sheet}")


def cmd_render(cfg, args):
    d = work_dir(cfg, args.video)
    picks_path = d / "picks.json"
    if not picks_path.exists():
        raise SystemExit("No picks yet. Run `python -m clipper run VIDEO` first.")
    picks = json.loads(picks_path.read_text(encoding="utf-8"))
    if not 1 <= args.pick <= len(picks):
        raise SystemExit(f"--pick must be 1-{len(picks)}")
    p = picks[args.pick - 1]

    caption = args.caption
    if args.caption_option:
        options = p.get("captions") or []
        if not 1 <= args.caption_option <= len(options):
            raise SystemExit(f"Pick {args.pick} has {len(options)} caption options")
        caption = options[args.caption_option - 1]

    transcript_path = d / "transcript.json"
    transcript = json.loads(transcript_path.read_text(encoding="utf-8")) if transcript_path.exists() else None
    out = d / "clips" / f"{args.pick:02d}_final.mp4"
    render(args.video, out, p["start"], p["end"], args.layout or cfg.layout,
           caption=caption if args.burn else None, transcript=transcript, subs=args.subs,
           font=cfg.font_file or None, encoder=cfg.encoder)
    print(out)
    if caption and not args.burn:
        print(f"Caption to add in TikTok: {caption}")


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(prog="clipper")
    ap.add_argument("-c", "--config", default="config.toml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="find, rank and render the best moments in a video")
    r.add_argument("video")
    r.add_argument("--context", default="a livestream", help="who/what this is, e.g. 'xQc reacting to videos'")
    r.add_argument("--top", type=int, help="clips to render (default: render_top in config)")
    r.add_argument("--no-transcribe", action="store_true", help="loudness only; implies no LLM ranking")
    r.add_argument("--no-llm", action="store_true", help="skip Claude ranking and captions")
    r.add_argument("--subs", action="store_true", help="burn word-by-word subtitles")
    r.add_argument("--fresh", action="store_true", help="ignore cached loudness/transcript")

    f = sub.add_parser("render", help="re-render one pick as a final clip")
    f.add_argument("video")
    f.add_argument("--pick", type=int, required=True)
    g = f.add_mutually_exclusive_group()
    g.add_argument("--caption", help="your own caption text")
    g.add_argument("--caption-option", type=int, help="use caption option N from review.md")
    f.add_argument("--burn", action="store_true", help="burn the caption into the video (emoji are dropped)")
    f.add_argument("--subs", action="store_true")
    f.add_argument("--layout", choices=["meme", "crop"])

    args = ap.parse_args(argv)
    cfg = config_mod.load(args.config)
    if args.cmd == "run":
        cmd_run(cfg, args, client)
    else:
        cmd_render(cfg, args)


if __name__ == "__main__":
    main()
