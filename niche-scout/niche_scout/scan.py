"""One data-gathering pass: search every niche, snapshot videos and channels, prune old data."""

from datetime import datetime, timedelta, timezone

from . import db
from .youtube import QuotaExceeded, parse_duration

try:
    from zoneinfo import ZoneInfo

    PACIFIC = ZoneInfo("America/Los_Angeles")
except Exception:  # Windows without the tzdata package; DST error is at most an hour
    PACIFIC = timezone(timedelta(hours=-8))


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def quota_day(now):
    return now.astimezone(PACIFIC).date().isoformat()


def remaining_budget(conn, cfg, now):
    used = db.quota_used_on(conn, quota_day(now))
    return max(0, cfg.daily_quota - cfg.quota_reserve - used)


def run(cfg, conn, yt, now=None, log=print):
    now = now or datetime.now(timezone.utc)
    stamp = iso(now)
    run_id = db.start_run(conn, stamp, quota_day(now))
    published_after = iso(now - timedelta(days=cfg.lookback_days))
    note = None
    found = set()

    try:
        for niche in cfg.niches:
            for query in niche.queries:
                for filter_ in niche.filters:
                    for order in cfg.orders:
                        ids = yt.search(
                            query, published_after, filter_, order, cfg.region, cfg.language
                        )
                        for rank, vid in enumerate(ids, 1):
                            db.add_hit(conn, run_id, niche.name, query, filter_, order, rank, vid, stamp)
                        found.update(ids)
                        log(f"  {niche.name:<18} {filter_:<6} {order:<9} {len(ids):>3}  {query}")
            conn.commit()

        # Re-snapshot recently found videos too, so we get growth curves rather than one-off counts.
        since = iso(now - timedelta(days=cfg.track_days))
        to_fetch = sorted(found | set(db.tracked_video_ids(conn, since)))
        videos = yt.videos(to_fetch)
        for item in videos:
            db.save_video(conn, item, parse_duration(item["contentDetails"].get("duration")), stamp)
        conn.commit()

        channel_ids = sorted({v["snippet"]["channelId"] for v in videos})
        for item in yt.channels(channel_ids):
            db.save_channel(conn, item, stamp)
        conn.commit()
        log(f"Snapshotted {len(videos)} videos across {len(channel_ids)} channels.")
    except QuotaExceeded as e:
        note = f"stopped early: {e}"
        log(f"Quota: {note}. Partial data kept.")
    finally:
        db.finish_run(conn, run_id, stamp, yt.used, note)

    db.prune(conn, iso(now - timedelta(days=cfg.retention_days)))
    log(f"Used {yt.used} quota units.")
    return run_id
