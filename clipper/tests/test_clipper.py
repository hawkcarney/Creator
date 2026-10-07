import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from clipper import config, llm, media, moments, render
from clipper.__main__ import main

HAS_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")
BURSTS = (60, 140)  # seconds where the test video gets loud


def make_video(path, seconds=180):
    """Test pattern with quiet tone, loud for 3s at each burst."""
    loud = "+".join(f"between(t,{b},{b + 3})" for b in BURSTS)
    media._run([
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=15:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-af", f"volume='if({loud},1,0.03)':eval=frame",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(path),
    ])


def fake_transcript():
    words = []
    for b in BURSTS:
        for i, w in enumerate("no way he actually did that bro".split()):
            words.append({"start": b + i * 0.3, "end": b + i * 0.3 + 0.25, "word": w})
    segs = [{"start": w["start"], "end": w["end"], "text": w["word"], "words": [w]} for w in words]
    return {"segments": segs}


class FakeClient:
    """Stands in for anthropic.Anthropic: records calls, returns canned structured output."""

    def __init__(self):
        self.calls = []
        self.messages = SimpleNamespace(create=self._screen)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._pick))

    def _reply(self, payload, stop="end_turn"):
        return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=json.dumps(payload))])

    def _screen(self, **kw):
        self.calls.append(("screen", kw))
        ids = [int(x.split("]")[0]) for x in kw["messages"][0]["content"].split("[id ")[1:]]
        return self._reply({"scores": [{"id": i, "score": 10 - i, "reason": "r"} for i in ids]})

    def _pick(self, **kw):
        self.calls.append(("pick", kw))
        return self._reply({"picks": [
            # trims outside the window must be clamped back inside it
            {"id": 1, "keep": True, "start": 0, "end": 9999, "why": "big reaction",
             "needs_visual_check": True, "captions": ["He really said: 'no way' 100% \U0001F602", "b", "c", "d", "e", "f"]},
            {"id": 2, "keep": False, "start": 0, "end": 1, "why": "weak", "needs_visual_check": False, "captions": []},
        ]})


class MomentsTest(unittest.TestCase):
    def test_spikes_beat_baseline(self):
        levels = [(t, -40.0) for t in range(300)]
        levels[100] = (100, -10.0)
        levels[200] = (200, -20.0)
        found = moments.find(levels, 300, limit=5)
        # Smoothing spreads a one-second spike over its neighbours, so allow +-1s.
        for c, spike in zip(found[:2], (100, 200)):
            self.assertLessEqual(abs(c["peak"] - spike), 1)
        self.assertTrue(all(c["end"] - c["start"] >= 12 for c in found))

    def test_silence_finds_nothing(self):
        self.assertEqual(moments.find([(t, -50.0) for t in range(100)], 100), [])


class LLMTest(unittest.TestCase):
    def test_refusal_raises(self):
        resp = SimpleNamespace(stop_reason="refusal", content=[])
        with self.assertRaises(llm.LLMError):
            llm._json_text(resp)

    def test_pick_uses_fallbacks_and_clamps(self):
        client = FakeClient()
        cands = [{"id": 1, "start": 40.0, "end": 70.0, "transcript": "x", "signal": 5},
                 {"id": 2, "start": 120.0, "end": 150.0, "transcript": "y", "signal": 4}]
        picks = llm.pick(cands, "ctx", config.DEFAULT_STYLE, "claude-opus-5-5", "medium", client)
        self.assertEqual(len(picks), 1)
        self.assertEqual((picks[0]["start"], picks[0]["end"]), (40.0, 70.0))
        self.assertEqual(len(picks[0]["captions"]), 5)
        kw = client.calls[0][1]
        self.assertEqual(kw["fallbacks"], "default")
        self.assertIn("Make sure it", kw["system"])


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.video = cls.tmp / "stream.mp4"
        make_video(cls.video)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.cfg_path = self.tmp / "config.toml"
        self.cfg_path.write_text(f'work_dir = "{(self.tmp / "work").as_posix()}"\n', encoding="utf-8")
        shutil.rmtree(self.tmp / "work", ignore_errors=True)

    def test_loudness_finds_bursts(self):
        levels = media.loudness(self.video)
        self.assertGreaterEqual(len(levels), 175)
        found = moments.find(levels, 180, limit=2)
        peaks = sorted(c["peak"] for c in found)
        for peak, burst in zip(peaks, BURSTS):
            self.assertTrue(burst - 1 <= peak <= burst + 4, (peak, burst))

    def test_run_without_llm(self):
        main(["-c", str(self.cfg_path), "run", str(self.video), "--no-transcribe", "--top", "2"])
        d = self.tmp / "work" / "stream"
        clips = sorted((d / "clips").glob("*.mp4"))
        self.assertEqual(len(clips), 2)
        info = media.probe(clips[0])
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertTrue(10 <= info["duration"] <= 61)
        self.assertIn("loudness only", (d / "review.md").read_text(encoding="utf-8"))

    def test_run_with_llm_then_burn_caption(self):
        d = self.tmp / "work" / "stream"
        d.mkdir(parents=True)
        (d / "transcript.json").write_text(json.dumps(fake_transcript()), encoding="utf-8")
        client = FakeClient()
        main(["-c", str(self.cfg_path), "run", str(self.video), "--context", "test", "--subs"], client=client)
        self.assertEqual([c[0] for c in client.calls], ["screen", "pick"])
        sheet = (d / "review.md").read_text(encoding="utf-8")
        self.assertIn("Watch it first", sheet)
        self.assertIn("no way", sheet)

        # Caption with quote, colon, percent and emoji must survive ffmpeg filter escaping.
        main(["-c", str(self.cfg_path), "render", str(self.video), "--pick", "1", "--caption-option", "1", "--burn"])
        final = d / "clips" / "01_final.mp4"
        self.assertEqual(media.probe(final)["height"], 1920)

    def test_api_error_falls_back_to_loudness(self):
        import anthropic, httpx
        d = self.tmp / "work" / "stream"
        d.mkdir(parents=True)
        (d / "transcript.json").write_text(json.dumps(fake_transcript()), encoding="utf-8")
        client = FakeClient()
        def boom(**kw):
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
        client.messages.create = boom
        main(["-c", str(self.cfg_path), "run", str(self.video), "--top", "1"], client=client)
        self.assertIn("loudness only", (d / "review.md").read_text(encoding="utf-8"))

    def test_crop_layout(self):
        out = self.tmp / "crop.mp4"
        render.render(self.video, out, 10, 20, layout="crop")
        info = media.probe(out)
        self.assertEqual((info["width"], info["height"]), (1080, 1920))


class ConfigTest(unittest.TestCase):
    def test_missing_file_gives_defaults(self):
        cfg = config.load("does-not-exist.toml")
        self.assertEqual(cfg.pick_model, "claude-opus-5-5")
        self.assertEqual(cfg.screen_model, "claude-haiku-4-5")

    def test_unknown_key_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write("typo_setting = 1\n")
        try:
            with self.assertRaises(SystemExit):
                config.load(f.name)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
