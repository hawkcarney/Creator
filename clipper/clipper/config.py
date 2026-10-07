"""Settings, read from config.toml when present. Every field has a working default."""

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

# The account's own winners, used to teach the caption model its voice.
DEFAULT_STYLE = [
    {"caption": "“Make sure it’s on low”", "views": "19.9M"},
    {"caption": "Snoop Dogg rages when he can’t stop pooping in Ark \U0001F602", "views": "4.2M"},
    {"caption": "Took his ancestors ankles", "views": "1.9M"},
    {"caption": "“Call em” \U0001F602\U0001F602", "views": "1.6M"},
    {"caption": "Ice in his veins", "views": "1.3M"},
    {"caption": "A classic \U0001F602\U0001F602\U0001F602", "views": "1.2M"},
    {"caption": "RIP to the \U0001F410 Kazuki Takahashi creator of Yu-Gi-Oh! \U0001F97A", "views": "1.2M"},
    {"caption": "The captain when the rescue sub finds them but can’t tow them to the surface", "views": "771.8K"},
]


@dataclass
class Config:
    work_dir: str = "work"
    # transcription
    whisper_model: str = "small"
    language: str = "en"
    # moment finding
    lead: int = 18
    tail: int = 8
    min_len: int = 12
    max_len: int = 60
    min_gap: int = 45
    max_candidates: int = 20
    # ranking
    screen_model: str = "claude-haiku-4-5"
    pick_model: str = "claude-opus-5-5"
    pick_effort: str = "medium"
    pick_top: int = 8
    style: list = field(default_factory=lambda: list(DEFAULT_STYLE))
    # rendering
    render_top: int = 5
    layout: str = "meme"
    encoder: str = "libx264"
    font_file: str = ""


def load(path):
    p = Path(path)
    if not p.exists():
        return Config()
    with open(p, "rb") as f:
        raw = tomllib.load(f)
    known = {f.name for f in fields(Config)}
    unknown = set(raw) - known
    if unknown:
        raise SystemExit(f"{path}: unknown settings {sorted(unknown)}")
    return Config(**raw)
