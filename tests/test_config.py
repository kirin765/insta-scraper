from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from insta_scraper.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.toml"
            config_path.write_text(
                """
database_path = "data/instagram.sqlite3"
max_posts_per_source = 12
trend_window_hours = 36

[instagram]
username = "user"
password = "pass"
session_file = "data/session.txt"

[[sources]]
type = "hashtag"
value = "fashion"

[[sources]]
type = "profile"
value = "nike"
""".strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.database_path, "data/instagram.sqlite3")
            self.assertEqual(config.max_posts_per_source, 12)
            self.assertEqual(config.trend_window_hours, 36)
            self.assertEqual(len(config.sources), 2)
            self.assertEqual(config.sources[0].type, "hashtag")
            self.assertEqual(config.sources[0].value, "fashion")


if __name__ == "__main__":
    unittest.main()
