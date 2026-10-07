"""SQLite storage. Videos and channels are upserted; stats are append-only snapshots."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    quota_day   TEXT NOT NULL,          -- Pacific date; Google resets quota at Pacific midnight
    quota_used  INTEGER NOT NULL DEFAULT 0,
    note        TEXT
);
CREATE TABLE IF NOT EXISTS hits (
    run_id   INTEGER NOT NULL REFERENCES runs(id),
    niche    TEXT NOT NULL,
    query    TEXT NOT NULL,
    filter   TEXT NOT NULL,             -- videoDuration filter used in the search
    sort     TEXT NOT NULL,             -- search order (viewCount, date, ...)
    rank     INTEGER NOT NULL,
    video_id TEXT NOT NULL,
    seen_at  TEXT NOT NULL,
    PRIMARY KEY (run_id, niche, query, filter, sort, video_id)
);
CREATE TABLE IF NOT EXISTS videos (
    video_id     TEXT PRIMARY KEY,
    channel_id   TEXT NOT NULL,
    title        TEXT,
    published_at TEXT,
    duration_s   INTEGER,
    category_id  TEXT,
    first_seen   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS video_stats (
    video_id    TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    views       INTEGER,
    likes       INTEGER,
    comments    INTEGER,
    PRIMARY KEY (video_id, captured_at)
);
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    title      TEXT,
    created_at TEXT,
    country    TEXT
);
CREATE TABLE IF NOT EXISTS channel_stats (
    channel_id   TEXT NOT NULL,
    captured_at  TEXT NOT NULL,
    subscribers  INTEGER,               -- NULL when the channel hides its count
    video_count  INTEGER,
    total_views  INTEGER,
    PRIMARY KEY (channel_id, captured_at)
);
CREATE INDEX IF NOT EXISTS hits_seen ON hits(seen_at);
CREATE INDEX IF NOT EXISTS videos_first_seen ON videos(first_seen);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _int(d, key):
    v = d.get(key)
    return int(v) if v is not None else None


def start_run(conn, now, quota_day):
    cur = conn.execute(
        "INSERT INTO runs (started_at, quota_day) VALUES (?, ?)", (now, quota_day)
    )
    return cur.lastrowid


def finish_run(conn, run_id, now, quota_used, note=None):
    conn.execute(
        "UPDATE runs SET finished_at = ?, quota_used = ?, note = ? WHERE id = ?",
        (now, quota_used, note, run_id),
    )
    conn.commit()


def quota_used_on(conn, quota_day):
    row = conn.execute(
        "SELECT COALESCE(SUM(quota_used), 0) FROM runs WHERE quota_day = ?", (quota_day,)
    ).fetchone()
    return row[0]


def add_hit(conn, run_id, niche, query, filter_, sort, rank, video_id, now):
    conn.execute(
        "INSERT OR IGNORE INTO hits VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, niche, query, filter_, sort, rank, video_id, now),
    )


def save_video(conn, item, duration_s, now):
    sn, st = item["snippet"], item.get("statistics", {})
    conn.execute(
        """INSERT INTO videos VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(video_id) DO UPDATE SET title = excluded.title""",
        (
            item["id"],
            sn["channelId"],
            sn.get("title"),
            sn.get("publishedAt"),
            duration_s,
            sn.get("categoryId"),
            now,
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO video_stats VALUES (?, ?, ?, ?, ?)",
        (item["id"], now, _int(st, "viewCount"), _int(st, "likeCount"), _int(st, "commentCount")),
    )


def save_channel(conn, item, now):
    sn, st = item["snippet"], item.get("statistics", {})
    conn.execute(
        """INSERT INTO channels VALUES (?, ?, ?, ?)
           ON CONFLICT(channel_id) DO UPDATE SET title = excluded.title, country = excluded.country""",
        (item["id"], sn.get("title"), sn.get("publishedAt"), sn.get("country")),
    )
    subs = None if st.get("hiddenSubscriberCount") else _int(st, "subscriberCount")
    conn.execute(
        "INSERT OR REPLACE INTO channel_stats VALUES (?, ?, ?, ?, ?)",
        (item["id"], now, subs, _int(st, "videoCount"), _int(st, "viewCount")),
    )


def tracked_video_ids(conn, since):
    """Videos first seen on or after `since`, to keep re-snapshotting for growth curves."""
    return [r[0] for r in conn.execute("SELECT video_id FROM videos WHERE first_seen >= ?", (since,))]


def prune(conn, before):
    """Drop API data older than the retention window (YouTube API policy: refresh or delete after 30 days)."""
    conn.execute("DELETE FROM hits WHERE seen_at < ?", (before,))
    conn.execute("DELETE FROM video_stats WHERE captured_at < ?", (before,))
    conn.execute("DELETE FROM channel_stats WHERE captured_at < ?", (before,))
    conn.execute("DELETE FROM videos WHERE video_id NOT IN (SELECT video_id FROM video_stats)")
    conn.execute("DELETE FROM channels WHERE channel_id NOT IN (SELECT channel_id FROM channel_stats)")
    conn.commit()
