from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Iterable

from .models import PublicKeywordSnapshot, ScrapedPost


def initialize_database(path: str | Path) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                source_count INTEGER NOT NULL,
                post_count INTEGER NOT NULL DEFAULT 0,
                window_hours INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                source_type TEXT NOT NULL,
                source_value TEXT NOT NULL,
                shortcode TEXT NOT NULL,
                url TEXT NOT NULL,
                posted_at TEXT,
                caption TEXT NOT NULL,
                UNIQUE(run_id, source_type, source_value, shortcode)
            );

            CREATE TABLE IF NOT EXISTS keyword_counts (
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY (run_id, keyword)
            );

            CREATE TABLE IF NOT EXISTS public_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL,
                title TEXT NOT NULL,
                total_media_count TEXT NOT NULL,
                related_keyword_count INTEGER NOT NULL
            );
            """
        )


@contextmanager
def connect(path: str | Path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def start_run(conn: sqlite3.Connection, source_count: int, window_hours: int) -> int:
    started_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO runs (started_at, source_count, post_count, window_hours)
        VALUES (?, ?, 0, ?)
        """,
        (started_at, source_count, window_hours),
    )
    return int(cursor.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, post_count: int) -> None:
    finished_at = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE runs SET finished_at = ?, post_count = ? WHERE id = ?",
        (finished_at, post_count, run_id),
    )


def store_posts(conn: sqlite3.Connection, run_id: int, posts: Iterable[ScrapedPost]) -> list[str]:
    captions: list[str] = []
    for post in posts:
        conn.execute(
            """
            INSERT OR REPLACE INTO posts (
                run_id, source_type, source_value, shortcode, url, posted_at, caption
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                post.source_type,
                post.source_value,
                post.shortcode,
                post.url,
                post.posted_at.isoformat() if post.posted_at else None,
                post.caption,
            ),
        )
        captions.append(post.caption)
    return captions


def store_keyword_counts(conn: sqlite3.Connection, run_id: int, counts: Counter[str]) -> None:
    for keyword, count in counts.items():
        conn.execute(
            """
            INSERT OR REPLACE INTO keyword_counts (run_id, keyword, count)
            VALUES (?, ?, ?)
            """,
            (run_id, keyword, count),
        )


def store_public_pages(
    conn: sqlite3.Connection, run_id: int, pages: Iterable[PublicKeywordSnapshot]
) -> None:
    for page in pages:
        conn.execute(
            """
            INSERT INTO public_pages (
                run_id, keyword, title, total_media_count, related_keyword_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                page.keyword,
                page.title,
                page.total_media_count,
                len(page.related_keywords),
            ),
        )


def get_trending_keywords(
    conn: sqlite3.Connection,
    *,
    since_hours: int | None,
    limit: int,
) -> list[tuple[str, int]]:
    params: list[object] = []
    where_clause = ""
    if since_hours is not None:
        threshold = datetime.now(UTC) - timedelta(hours=since_hours)
        where_clause = "WHERE r.started_at >= ?"
        params.append(threshold.isoformat())
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT kc.keyword, SUM(kc.count) AS total_count
        FROM keyword_counts kc
        JOIN runs r ON r.id = kc.run_id
        {where_clause}
        GROUP BY kc.keyword
        ORDER BY total_count DESC, kc.keyword ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [(str(row["keyword"]), int(row["total_count"])) for row in rows]


def latest_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return int(row["id"]) if row else None
