"""Turns raw snapshots into per-niche comparisons."""

import csv
from datetime import datetime, timedelta, timezone
from statistics import median

SHORT_MAX_S = 180  # Shorts can run up to 3 minutes

ROWS_SQL = """
WITH lv AS (
    SELECT video_id, views, captured_at,
           LAG(views)       OVER w AS prev_views,
           LAG(captured_at) OVER w AS prev_at,
           ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY captured_at DESC) AS rn
    FROM video_stats
    WINDOW w AS (PARTITION BY video_id ORDER BY captured_at)
),
lc AS (
    SELECT channel_id, subscribers,
           ROW_NUMBER() OVER (PARTITION BY channel_id ORDER BY captured_at DESC) AS rn
    FROM channel_stats
)
SELECT DISTINCT h.niche, v.video_id, v.title, v.channel_id, c.title AS channel,
       v.published_at, v.duration_s, lv.views, lv.captured_at, lv.prev_views, lv.prev_at,
       lc.subscribers
FROM hits h
JOIN videos v   ON v.video_id = h.video_id
JOIN lv         ON lv.video_id = v.video_id AND lv.rn = 1
LEFT JOIN lc    ON lc.channel_id = v.channel_id AND lc.rn = 1
LEFT JOIN channels c ON c.channel_id = v.channel_id
WHERE h.seen_at >= ?
"""


def _ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _days(a, b):
    return (_ts(b) - _ts(a)).total_seconds() / 86400


def fmt_of(duration_s):
    if not duration_s:  # None, or 0 for live/upcoming streams
        return None
    return "short" if duration_s <= SHORT_MAX_S else "long"


def video_rows(conn, cfg, days, now=None):
    """One dict per (niche, video) seen in the last `days`, with derived metrics."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for r in conn.execute(ROWS_SQL, (cutoff,)):
        fmt = fmt_of(r["duration_s"])
        if fmt is None or r["views"] is None or not r["published_at"]:
            continue
        # published_at from the API has the same Z format, but may carry fractional seconds.
        published = r["published_at"][:19] + "Z"
        age = max(_days(published, r["captured_at"]), 1.0)  # floor at a day so brand-new uploads don't explode
        subs = r["subscribers"]
        growth = None
        if r["prev_views"] is not None:
            span = _days(r["prev_at"], r["captured_at"])
            if span > 0:
                growth = (r["views"] - r["prev_views"]) / span
        out.append(
            dict(
                niche=r["niche"],
                format=fmt,
                video_id=r["video_id"],
                title=r["title"],
                channel=r["channel"],
                subscribers=subs,
                published_at=r["published_at"],
                duration_s=r["duration_s"],
                views=r["views"],
                views_per_day=r["views"] / age,
                outlier=(r["views"] / max(subs, 1000)) if subs is not None else None,
                growth_per_day=growth,
                url=f"https://youtu.be/{r['video_id']}",
            )
        )
    return out


def _med(xs):
    xs = [x for x in xs if x is not None]
    return median(xs) if xs else None


def summarize(rows, cfg):
    rpm = {n.name: n for n in cfg.niches}
    groups = {}
    for r in rows:
        groups.setdefault((r["niche"], r["format"]), []).append(r)

    out = []
    for (niche, fmt), rs in sorted(groups.items()):
        small = [r for r in rs if r["subscribers"] is not None and r["subscribers"] < cfg.small_channel_subs]
        with_subs = [r for r in rs if r["subscribers"] is not None]
        med_views = _med(r["views"] for r in rs)
        n = rpm.get(niche)
        rate = (n.rpm_short if fmt == "short" else n.rpm_long) if n else 0
        out.append(
            dict(
                niche=niche,
                format=fmt,
                videos=len(rs),
                channels=len({r["channel"] for r in rs}),
                median_views=med_views,
                median_views_per_day=_med(r["views_per_day"] for r in rs),
                median_outlier=_med(r["outlier"] for r in rs),
                small_channel_pct=100 * len(small) / len(with_subs) if with_subs else None,
                breakouts=sum(1 for r in small if r["outlier"] and r["outlier"] >= 5),
                median_growth_per_day=_med(r["growth_per_day"] for r in rs),
                growth_samples=sum(1 for r in rs if r["growth_per_day"] is not None),
                est_usd_median_video=(med_views or 0) * rate / 1000,
            )
        )
    return out


def _n(x, digits=0):
    if x is None:
        return "-"
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if abs(x) >= 10_000:
        return f"{x / 1_000:.0f}k"
    return f"{x:,.{digits}f}"


COLUMNS = [
    ("niche", "niche", lambda v: v),
    ("fmt", "format", lambda v: v),
    ("vids", "videos", str),
    ("chans", "channels", str),
    ("med views", "median_views", _n),
    ("views/day", "median_views_per_day", _n),
    ("outlier", "median_outlier", lambda v: _n(v, 2)),
    ("small%", "small_channel_pct", _n),
    ("breakouts", "breakouts", str),
    ("growth/day", "median_growth_per_day", _n),
    ("est $/vid", "est_usd_median_video", lambda v: _n(v, 2)),
]


def table(summary):
    head = [c[0] for c in COLUMNS]
    body = [[fmt(s[key]) for _, key, fmt in COLUMNS] for s in summary]
    widths = [max(len(x) for x in col) for col in zip(head, *body)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(head, widths))]
    lines.append("  ".join("-" * w for w in widths))
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths)) for row in body]
    return "\n".join(lines)


def top_breakouts(rows, cfg, per_niche=5):
    """Small channels punching far above their size: the clearest sign a niche is open to newcomers."""
    lines = []
    by_niche = {}
    for r in rows:
        if r["outlier"] is not None and r["subscribers"] is not None and r["subscribers"] < cfg.small_channel_subs:
            by_niche.setdefault(r["niche"], []).append(r)
    for niche, rs in sorted(by_niche.items()):
        lines.append(f"\n{niche}")
        for r in sorted(rs, key=lambda r: r["outlier"], reverse=True)[:per_niche]:
            lines.append(
                f"  {r['outlier']:>6.1f}x  {_n(r['views']):>6} views  {_n(r['subscribers']):>6} subs  "
                f"[{r['format']}] {r['title'][:70]}  {r['url']}"
            )
    return "\n".join(lines)


def write_csv(rows, path):
    if not rows:
        return 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)
