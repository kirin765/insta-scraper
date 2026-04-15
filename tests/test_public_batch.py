from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from insta_scraper import cli
from insta_scraper.models import PublicKeywordSnapshot
from insta_scraper.storage import connect


class PublicBatchTests(unittest.TestCase):
    def test_collect_public_command_stores_pages_and_keywords(self) -> None:
        snapshots = {
            "fashion": PublicKeywordSnapshot(
                keyword="fashion",
                title="Fashion",
                total_media_count="10",
                related_keywords=("streetwear",),
            ),
            "beauty": PublicKeywordSnapshot(
                keyword="beauty",
                title="Beauty",
                total_media_count="8",
                related_keywords=("makeup", "skincare"),
            ),
        }

        def fake_collect(self, source):
            return snapshots[source.value]

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "keywords.sqlite3"
            with (
                patch("insta_scraper.cli.InstagramScraper.collect_public_snapshot", fake_collect),
                patch("insta_scraper.cli._memory_usage_percent", return_value=10.0),
            ):
                exit_code = cli.main(
                    [
                        "collect-public",
                        "--database",
                        str(db_path),
                        "--categories",
                        "fashion",
                        "beauty",
                        "--target-keywords",
                        "4",
                    ]
                )

            self.assertEqual(exit_code, 0)
            with connect(db_path) as conn:
                public_pages = conn.execute(
                    "SELECT keyword, title, total_media_count, related_keyword_count FROM public_pages ORDER BY id"
                ).fetchall()
                self.assertEqual(len(public_pages), 2)
                self.assertEqual(public_pages[0]["keyword"], "fashion")
                self.assertEqual(public_pages[1]["keyword"], "beauty")

                keyword_counts = conn.execute(
                    "SELECT keyword, count FROM keyword_counts ORDER BY keyword ASC"
                ).fetchall()
                self.assertEqual(
                    [(row["keyword"], row["count"]) for row in keyword_counts],
                    [("beauty", 1), ("fashion", 1), ("makeup", 1), ("streetwear", 1)],
                )

    def test_collect_public_command_skips_when_memory_is_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "keywords.sqlite3"
            with (
                patch("insta_scraper.cli._memory_usage_percent", return_value=85.0),
                patch("insta_scraper.cli.InstagramScraper.collect_public_snapshot") as collect_mock,
            ):
                exit_code = cli.main(
                    [
                        "collect-public",
                        "--database",
                        str(db_path),
                        "--categories",
                        "fashion",
                        "--target-keywords",
                        "4",
                        "--max-memory-percent",
                        "80",
                    ]
                )

            self.assertEqual(exit_code, 0)
            collect_mock.assert_not_called()
            self.assertFalse(db_path.exists())


if __name__ == "__main__":
    unittest.main()
