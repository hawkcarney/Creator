"""Minimal YouTube Data API v3 client (stdlib only) with quota accounting."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/"

# Quota units charged per call, per Google's published costs.
COST = {"search": 100, "videos": 1, "channels": 1}

BATCH = 50  # max ids per videos.list / channels.list call


class QuotaExceeded(Exception):
    pass


class ApiError(Exception):
    pass


_DURATION = re.compile(
    r"P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$"
)


def parse_duration(iso):
    """'PT1M5S' -> 65. Returns None for anything unparseable."""
    m = _DURATION.match(iso or "")
    if not m:
        return None
    d, h, mi, s = (int(m.group(k) or 0) for k in "dhms")
    return ((d * 24 + h) * 60 + mi) * 60 + s


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


class YouTube:
    def __init__(self, api_key, budget, opener=urllib.request.urlopen):
        self.api_key = api_key
        self.budget = budget
        self.used = 0
        self._open = opener

    def _get(self, endpoint, **params):
        cost = COST[endpoint]
        if self.used + cost > self.budget:
            raise QuotaExceeded(
                f"{endpoint} needs {cost} units; {self.budget - self.used} left in today's budget"
            )
        # Google charges for failed requests too, so count before calling.
        self.used += cost
        params["key"] = self.api_key
        url = API + endpoint + "?" + urllib.parse.urlencode(params)
        try:
            with self._open(url, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 403 and "quotaExceeded" in body:
                raise QuotaExceeded("Google reports the project's daily quota is exhausted") from None
            # Deliberately omit the URL: it contains the API key.
            raise ApiError(f"{endpoint} HTTP {e.code}: {body[:300]}") from None

    def search(self, query, published_after, duration, order, region=None, language=None):
        """Returns up to 50 video ids, best first."""
        params = dict(
            part="id",
            q=query,
            type="video",
            maxResults=BATCH,
            order=order,
            publishedAfter=published_after,
            videoDuration=duration,
        )
        if region:
            params["regionCode"] = region
        if language:
            params["relevanceLanguage"] = language
        data = self._get("search", **params)
        return [it["id"]["videoId"] for it in data.get("items", []) if it["id"].get("videoId")]

    def videos(self, ids):
        out = []
        for chunk in _chunks(list(ids), BATCH):
            data = self._get("videos", part="snippet,contentDetails,statistics", id=",".join(chunk))
            out.extend(data.get("items", []))
        return out

    def channels(self, ids):
        out = []
        for chunk in _chunks(list(ids), BATCH):
            data = self._get("channels", part="snippet,statistics", id=",".join(chunk))
            out.extend(data.get("items", []))
        return out
