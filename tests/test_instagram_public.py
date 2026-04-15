from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from insta_scraper.instagram import InstagramScraper
from insta_scraper.models import InstagramAuth, Source


class InstagramPublicTests(unittest.TestCase):
    def test_collect_public_snapshot_parses_related_keywords(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:title" content="Popular hashtag fashion" />
          </head>
          <body>
            <script>
              window.__sharedData = {"total_media_count_intl":"1.2M","related_keywords":["streetstyle","outfit","trend"]};
            </script>
          </body>
        </html>
        """
        scraper = InstagramScraper(InstagramAuth(username=None, password=None, session_file=None))
        scraper._fetch_public_hashtag_page = lambda keyword: html  # type: ignore[method-assign]

        snapshot = scraper.collect_public_snapshot(Source(type="hashtag", value="fashion"))

        self.assertEqual(snapshot.keyword, "fashion")
        self.assertEqual(snapshot.title, "Popular hashtag fashion")
        self.assertEqual(snapshot.total_media_count, "1.2M")
        self.assertEqual(snapshot.related_keywords, ("streetstyle", "outfit", "trend"))

    def test_collect_public_snapshot_rejects_profiles(self) -> None:
        scraper = InstagramScraper(InstagramAuth(username=None, password=None, session_file=None))

        with self.assertRaises(ValueError):
            scraper.collect_public_snapshot(Source(type="profile", value="nike"))


if __name__ == "__main__":
    unittest.main()
