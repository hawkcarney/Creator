"""CLI: python -m niche_scout {scan,report,status}"""

import argparse
import os
import sys
from datetime import datetime, timezone

from . import config as config_mod
from . import db, report, scan
from .youtube import YouTube


def main(argv=None):
    p = argparse.ArgumentParser(prog="niche_scout")
    p.add_argument("-c", "--config", default="config.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="search every niche and snapshot stats (run once a day)")

    r = sub.add_parser("report", help="compare niches from gathered data")
    r.add_argument("--days", type=int, default=7, help="use videos seen in the last N days (default 7)")
    r.add_argument("--top", type=int, default=5, help="breakout videos to list per niche (0 to hide)")
    r.add_argument("--csv", help="also write per-video rows to this CSV file")

    sub.add_parser("status", help="show quota use and data volume")

    args = p.parse_args(argv)
    cfg = config_mod.load(args.config)
    os.makedirs(os.path.dirname(cfg.db_path) or ".", exist_ok=True)
    conn = db.connect(cfg.db_path)

    if args.cmd == "scan":
        if not cfg.api_key:
            sys.exit("No API key. Set YOUTUBE_API_KEY or api_key in config.toml.")
        now = datetime.now(timezone.utc)
        budget = scan.remaining_budget(conn, cfg, now)
        planned = config_mod.searches_per_run(cfg) * 100
        print(f"Budget today: {budget} units. Searches planned: ~{planned} units.")
        if planned > budget:
            print("Warning: not enough quota for every search; the scan will stop early.")
        scan.run(cfg, conn, YouTube(cfg.api_key, budget), now)

    elif args.cmd == "report":
        rows = report.video_rows(conn, cfg, args.days)
        if not rows:
            sys.exit("No data yet. Run `scan` first.")
        print(report.table(report.summarize(rows, cfg)))
        print(
            "\noutlier = views / subscribers.  small% = share of results from channels under "
            f"{cfg.small_channel_subs:,} subs.\nbreakouts = small-channel videos at 5x+ their sub count.  "
            "est $/vid uses the RPM guesses in config.toml."
        )
        if args.top:
            print("\nTop small-channel breakouts:" + report.top_breakouts(rows, cfg, args.top))
        if args.csv:
            print(f"\nWrote {report.write_csv(rows, args.csv)} rows to {args.csv}")

    elif args.cmd == "status":
        now = datetime.now(timezone.utc)
        used = db.quota_used_on(conn, scan.quota_day(now))
        print(f"Quota used today (Pacific): {used} / {cfg.daily_quota}")
        for t in ("runs", "hits", "videos", "video_stats", "channels", "channel_stats"):
            print(f"  {t:<14} {conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
        last = conn.execute("SELECT started_at, quota_used, note FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        if last:
            print(f"Last run: {last['started_at']}  {last['quota_used']} units  {last['note'] or 'ok'}")


if __name__ == "__main__":
    main()
