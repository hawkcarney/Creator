import io
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone

from niche_scout import db, report, scan
from niche_scout.config import Config, Niche
from niche_scout.youtube import QuotaExceeded, YouTube, parse_duration


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeAPI:
    """Serves canned search/videos/channels responses keyed off the endpoint in the URL."""

    def __init__(self, videos, channels, views_bump=0):
        self.videos, self.channels, self.bump = videos, channels, views_bump
        self.calls = []

    def __call__(self, url, timeout=None):
        endpoint = url.split("/v3/")[1].split("?")[0]
        self.calls.append(endpoint)
        if endpoint == "search":
            body = {"items": [{"id": {"videoId": v["id"]}} for v in self.videos]}
        elif endpoint == "videos":
            items = []
            for v in self.videos:
                v = json.loads(json.dumps(v))
                v["statistics"]["viewCount"] = str(int(v["statistics"]["viewCount"]) + self.bump)
                items.append(v)
            body = {"items": items}
        else:
            body = {"items": self.channels}
        return FakeResp(json.dumps(body).encode())


def video(vid, channel, views, duration, published="2026-09-30T00:00:00Z"):
    return {
        "id": vid,
        "snippet": {"channelId": channel, "title": f"title {vid}", "publishedAt": published},
        "contentDetails": {"duration": duration},
        "statistics": {"viewCount": str(views)},
    }


def channel(cid, subs, hidden=False):
    return {
        "id": cid,
        "snippet": {"title": f"chan {cid}", "publishedAt": "2020-01-01T00:00:00Z"},
        "statistics": {"subscriberCount": str(subs), "hiddenSubscriberCount": hidden, "videoCount": "10", "viewCount": "1"},
    }


def cfg(**kw):
    n = Niche("finance", ["q"], ["short"], rpm_short=0.05, rpm_long=15.0)
    return Config(api_key="k", niches=[n], **kw)


NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
silent = lambda *a: None


class DurationTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_duration("PT1M5S"), 65)
        self.assertEqual(parse_duration("PT1H"), 3600)
        self.assertEqual(parse_duration("P1DT1S"), 86401)
        self.assertEqual(parse_duration("P0D"), 0)
        self.assertIsNone(parse_duration("garbage"))

    def test_live_streams_are_excluded(self):
        self.assertIsNone(report.fmt_of(0))
        self.assertEqual(report.fmt_of(180), "short")
        self.assertEqual(report.fmt_of(181), "long")


class ScanAndReportTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.videos = [
            video("a", "small", 200_000, "PT45S"),     # small channel, 20x outlier -> breakout
            video("b", "big", 50_000, "PT12M"),
            video("live", "big", 9, "P0D"),             # live stream: must be ignored
        ]
        self.channels = [channel("small", 10_000), channel("big", 2_000_000)]

    def test_scan_then_report(self):
        api = FakeAPI(self.videos, self.channels)
        scan.run(cfg(), self.conn, YouTube("k", 10_000, opener=api), NOW, log=silent)
        self.assertEqual(api.calls, ["search", "videos", "channels"])

        rows = report.video_rows(self.conn, cfg(), days=7, now=NOW)
        self.assertEqual({r["video_id"] for r in rows}, {"a", "b"})
        summary = {s["format"]: s for s in report.summarize(rows, cfg())}
        self.assertEqual(summary["short"]["breakouts"], 1)
        self.assertEqual(summary["short"]["small_channel_pct"], 100)
        self.assertAlmostEqual(summary["long"]["est_usd_median_video"], 50_000 * 15 / 1000)
        self.assertIn("finance", report.table(report.summarize(rows, cfg())))

    def test_second_scan_gives_growth(self):
        scan.run(cfg(), self.conn, YouTube("k", 10_000, opener=FakeAPI(self.videos, self.channels)), NOW, log=silent)
        later = NOW + timedelta(days=1)
        scan.run(cfg(), self.conn, YouTube("k", 10_000, opener=FakeAPI(self.videos, self.channels, views_bump=1000)), later, log=silent)
        rows = {r["video_id"]: r for r in report.video_rows(self.conn, cfg(), days=7, now=later)}
        self.assertAlmostEqual(rows["a"]["growth_per_day"], 1000)

    def test_budget_stops_scan_but_keeps_run(self):
        api = FakeAPI(self.videos, self.channels)
        yt = YouTube("k", 50, opener=api)  # not enough for one search
        scan.run(cfg(), self.conn, yt, NOW, log=silent)
        self.assertEqual(api.calls, [])
        note = self.conn.execute("SELECT note FROM runs").fetchone()[0]
        self.assertIn("stopped early", note)

    def test_quota_is_tracked_per_pacific_day(self):
        scan.run(cfg(), self.conn, YouTube("k", 10_000, opener=FakeAPI(self.videos, self.channels)), NOW, log=silent)
        self.assertEqual(scan.remaining_budget(self.conn, cfg(), NOW), 10_000 - 1_000 - 102)

    def test_prune_drops_old_data(self):
        scan.run(cfg(), self.conn, YouTube("k", 10_000, opener=FakeAPI(self.videos, self.channels)), NOW, log=silent)
        db.prune(self.conn, scan.iso(NOW + timedelta(days=1)))
        for t in ("hits", "videos", "video_stats", "channels", "channel_stats"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], 0, t)


class ErrorTest(unittest.TestCase):
    def test_google_quota_error_maps_to_quota_exceeded(self):
        def opener(url, timeout=None):
            raise urllib.error.HTTPError(url, 403, "x", {}, io.BytesIO(b'{"reason":"quotaExceeded"}'))

        with self.assertRaises(QuotaExceeded):
            YouTube("secret", 10_000, opener=opener).search("q", "t", "short", "viewCount")


if __name__ == "__main__":
    unittest.main()
