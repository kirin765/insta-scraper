from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from insta_scraper.keywords import build_keyword_counter, extract_keywords


class KeywordTests(unittest.TestCase):
    def test_extract_keywords(self) -> None:
        text = "New #Fashion drop for the winter season with viral reels and fashion trends"
        self.assertEqual(
            extract_keywords(text),
            ["fashion", "new", "drop", "winter", "season", "viral", "reels", "trends"],
        )

    def test_build_keyword_counter_deduplicates_per_post(self) -> None:
        counter = build_keyword_counter([
            "#fashion fashion fashion",
            "fresh fashion looks",
        ])
        self.assertEqual(counter["fashion"], 2)


if __name__ == "__main__":
    unittest.main()
