from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Source:
    type: str
    value: str


@dataclass(frozen=True)
class InstagramAuth:
    username: str | None
    password: str | None
    session_file: str | None


@dataclass(frozen=True)
class AppConfig:
    database_path: str
    max_posts_per_source: int
    trend_window_hours: int
    sources: tuple[Source, ...]
    auth: InstagramAuth


@dataclass(frozen=True)
class ScrapedPost:
    source_type: str
    source_value: str
    shortcode: str
    url: str
    caption: str
    posted_at: datetime | None


@dataclass(frozen=True)
class PublicKeywordSnapshot:
    keyword: str
    title: str
    total_media_count: str
    related_keywords: tuple[str, ...]
