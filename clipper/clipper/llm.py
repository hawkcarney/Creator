"""Two-tier ranking: a cheap model screens every candidate, a strong model picks and writes captions.

Both only see transcripts, never the video, so visual-only gags are invisible to them. Loudness
still surfaces those moments; the reviewer (you) is the final filter.
"""

import json

SCREEN_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "score", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scores"],
    "additionalProperties": False,
}

PICK_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "keep": {"type": "boolean"},
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "why": {"type": "string"},
                    "needs_visual_check": {"type": "boolean"},
                    "captions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "keep", "start", "end", "why", "needs_visual_check", "captions"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["picks"],
    "additionalProperties": False,
}

SCREEN_PROMPT = """You are screening candidate moments from a livestream for short-form clips (TikTok, Reels, Shorts).

Each candidate is a window of the stream around a spike in volume or speech. You only have the transcript, not the video.

Score each candidate 1-10 for how well it would work as a standalone 15-60 second clip for viewers who have never seen this streamer. Strong clips have a clear setup and payoff, a big reaction, a quotable line, conflict, or something absurd. Weak clips are fragments that need earlier context, inside jokes, sponsor reads, dead air, or transcripts that are mostly noise.

Stream context: {context}

Candidates:
{candidates}"""

PICK_SYSTEM = """You help run a meme/clip TikTok account with 34.5K followers and several videos over 1M views. Its format: a short clip with one punchy caption in a white box on top. The caption carries the joke. It is deadpan, specific and conversational. It never explains the joke and never uses hashtags.

Past captions and their views, for voice only. Don't reuse them:
{examples}"""

PICK_PROMPT = """Stream context: {context}

Below are the strongest candidate moments from this stream (transcript only; you can't see the video). For each one:
- keep: true only if you'd actually post it. Be selective; a weak clip costs the account reach.
- start/end: trim within the given bounds (seconds) so it opens on the setup and ends right after the payoff. Aim for 15-45s.
- why: one sentence on why it works or doesn't.
- needs_visual_check: true if the payoff likely depends on something visual you can't confirm from the transcript.
- captions: exactly 5 options in the account's voice, under 15 words each and varied: a "X when Y" framing, a line quoted or riffed from the clip, a 2-4 word minimal one, and two of your choice. Write only from what the transcript supports; don't invent visuals.

List kept clips first, best first.

Candidates:
{candidates}"""


class LLMError(Exception):
    pass


def _client():
    try:
        import anthropic
    except ImportError:
        raise SystemExit("anthropic is not installed: pip install anthropic (or run with --no-llm)")
    return anthropic.Anthropic()


def _json_text(response):
    if response.stop_reason == "refusal":
        raise LLMError("the model declined this transcript")
    if response.stop_reason == "max_tokens":
        raise LLMError("response was cut off; too many candidates for max_tokens")
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def _fmt(cands, with_bounds=False):
    lines = []
    for c in cands:
        bounds = f" bounds={c['start']:.1f}-{c['end']:.1f}s" if with_bounds else ""
        lines.append(f"[id {c['id']}]{bounds}\n{c['transcript'] or '(no speech detected)'}")
    return "\n\n".join(lines)


def screen(cands, context, model, client=None):
    """Adds 'screen_score' and 'screen_reason' to each candidate. Cheap model, one call."""
    client = client or _client()
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        output_config={"format": {"type": "json_schema", "schema": SCREEN_SCHEMA}},
        messages=[{"role": "user", "content": SCREEN_PROMPT.format(context=context, candidates=_fmt(cands))}],
    )
    by_id = {s["id"]: s for s in _json_text(response)["scores"]}
    for c in cands:
        s = by_id.get(c["id"], {})
        c["screen_score"] = s.get("score", 0)
        c["screen_reason"] = s.get("reason", "")
    return cands


def pick(cands, context, examples, model, effort, client=None):
    """Returns kept picks, best first, with trims and caption options. Strong model, one call."""
    client = client or _client()
    ex = "\n".join(f"- {e['caption']} ({e['views']})" for e in examples)
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # on a policy decline, the API re-runs this on a fallback model
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": PICK_SCHEMA}},
        system=PICK_SYSTEM.format(examples=ex),
        messages=[{"role": "user", "content": PICK_PROMPT.format(context=context, candidates=_fmt(cands, True))}],
    )
    by_id = {c["id"]: c for c in cands}
    out = []
    for p in _json_text(response)["picks"]:
        c = by_id.get(p["id"])
        if c is None or not p["keep"]:
            continue
        # Keep trims inside the candidate window and at a sane length.
        start = min(max(p["start"], c["start"]), c["end"] - 5)
        end = max(min(p["end"], c["end"]), start + 5)
        out.append({**c, "start": round(start, 2), "end": round(end, 2), "why": p["why"],
                    "needs_visual_check": p["needs_visual_check"], "captions": p["captions"][:5]})
    return out
