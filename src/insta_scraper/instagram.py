from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import importlib
import json
import html as html_module
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from typing import Iterable

from .models import InstagramAuth, PublicKeywordSnapshot, ScrapedPost, Source


def _load_instaloader_module():
    try:
        return importlib.import_module("instaloader")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "instaloader is not installed; install requirements before running scrapes"
        ) from exc


@dataclass
class InstagramScraper:
    auth: InstagramAuth

    def __post_init__(self) -> None:
        self._loader = None

    def collect_posts(self, sources: Iterable[Source], limit_per_source: int) -> list[ScrapedPost]:
        loader = self._ensure_loader()
        instaloader = _load_instaloader_module()
        collected: list[ScrapedPost] = []
        for source in sources:
            iterator = self._iter_posts(loader, instaloader, source)
            for index, post in enumerate(iterator):
                collected.append(self._convert_post(source, post))
                if index + 1 >= limit_per_source:
                    break
        return collected

    def collect_public_snapshot(self, source: Source) -> PublicKeywordSnapshot:
        if source.type != "hashtag":
            raise ValueError("public scraping is only supported for hashtag sources")
        html = self._fetch_public_hashtag_page(source.value)
        related_keywords = self._extract_related_keywords(html)
        title = self._extract_title(html) or source.value
        total_media_count = self._extract_total_media_count(html) or "0"
        return PublicKeywordSnapshot(
            keyword=source.value,
            title=title,
            total_media_count=total_media_count,
            related_keywords=tuple(related_keywords),
        )

    def _ensure_loader(self):
        if self._loader is None:
            instaloader = _load_instaloader_module()
            loader = instaloader.Instaloader(
                download_pictures=False,
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                quiet=True,
                max_connection_attempts=3,
            )
            self._authenticate(loader)
            self._loader = loader
        return self._loader

    def _authenticate(self, loader) -> None:
        username = self.auth.username
        session_file = self.auth.session_file
        if session_file and username:
            session_path = Path(session_file)
            if session_path.exists():
                loader.load_session_from_file(username, str(session_path))
                return
        if self.auth.username and self.auth.password:
            loader.login(self.auth.username, self.auth.password)
            if session_file:
                Path(session_file).parent.mkdir(parents=True, exist_ok=True)
                loader.save_session_to_file(str(Path(session_file)))

    def _iter_posts(self, loader, instaloader, source: Source):
        if source.type == "hashtag":
            hashtag = instaloader.Hashtag.from_name(loader.context, source.value.lower())
            return hashtag.get_posts()
        if source.type == "profile":
            profile = instaloader.Profile.from_username(loader.context, source.value)
            return profile.get_posts()
        raise ValueError(f"unsupported source type: {source.type}")

    def _convert_post(self, source: Source, post) -> ScrapedPost:
        posted_at = getattr(post, "date_utc", None)
        if posted_at is not None and posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=UTC)
        shortcode = str(getattr(post, "shortcode"))
        return ScrapedPost(
            source_type=source.type,
            source_value=source.value,
            shortcode=shortcode,
            url=f"https://www.instagram.com/p/{shortcode}/",
            caption=getattr(post, "caption", "") or "",
            posted_at=posted_at if isinstance(posted_at, datetime) else None,
        )

    def _fetch_public_hashtag_page(self, keyword: str) -> str:
        url = f"https://www.instagram.com/popular/{quote(keyword)}/?hl=en"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")

    def _extract_title(self, html: str) -> str | None:
        match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        return html_module.unescape(match.group(1)) if match else None

    def _extract_total_media_count(self, html: str) -> str | None:
        match = re.search(r'"total_media_count_intl":"([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'"total_media_count":(\d+)', html)
        return match.group(1) if match else None

    def _extract_related_keywords(self, html: str) -> list[str]:
        match = re.search(r'"related_keywords":(\[[^\]]*\])', html)
        if not match:
            return []
        raw_keywords = json.loads(match.group(1))
        return [str(keyword) for keyword in raw_keywords if str(keyword).strip()]
