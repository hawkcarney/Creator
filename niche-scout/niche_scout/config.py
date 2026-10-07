"""Loads config.toml. See config.example.toml for every field."""

import os
import tomllib
from dataclasses import dataclass, field

VALID_FILTERS = {"any", "short", "medium", "long"}  # YouTube's videoDuration filter values
VALID_ORDERS = {"viewCount", "date", "relevance", "rating"}


@dataclass
class Niche:
    name: str
    queries: list
    filters: list
    rpm_short: float
    rpm_long: float


@dataclass
class Config:
    api_key: str
    db_path: str = "data/scout.db"
    daily_quota: int = 10_000
    quota_reserve: int = 1_000
    lookback_days: int = 30
    track_days: int = 14
    retention_days: int = 30
    region: str = "US"
    language: str = "en"
    orders: list = field(default_factory=lambda: ["viewCount"])
    small_channel_subs: int = 50_000
    niches: list = field(default_factory=list)


def load(path):
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    niches = []
    for n in raw.pop("niche", []):
        filters = n.get("filters", ["short", "medium"])
        bad = set(filters) - VALID_FILTERS
        if bad:
            raise ValueError(f"niche {n['name']!r}: unknown filters {sorted(bad)}")
        niches.append(
            Niche(
                name=n["name"],
                queries=list(n["queries"]),
                filters=filters,
                rpm_short=float(n.get("rpm_short", 0)),
                rpm_long=float(n.get("rpm_long", 0)),
            )
        )
    if not niches:
        raise ValueError("config has no [[niche]] entries")

    # Env var wins so the key never has to live in a file.
    raw["api_key"] = os.environ.get("YOUTUBE_API_KEY") or raw.get("api_key", "")
    cfg = Config(niches=niches, **raw)
    bad = set(cfg.orders) - VALID_ORDERS
    if bad:
        raise ValueError(f"unknown orders {sorted(bad)}")
    return cfg


def searches_per_run(cfg):
    return sum(len(n.queries) * len(n.filters) for n in cfg.niches) * len(cfg.orders)
