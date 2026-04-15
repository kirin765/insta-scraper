from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import sys

from .config import load_config, override_config
from .models import AppConfig, InstagramAuth, Source
from .instagram import InstagramScraper
from .keywords import build_keyword_counter
from .storage import (
    connect,
    finish_run,
    get_trending_keywords,
    initialize_database,
    start_run,
    store_public_pages,
    store_keyword_counts,
    store_posts,
)


DEFAULT_PUBLIC_CATEGORY_SEEDS: tuple[str, ...] = (
    "fashion",
    "beauty",
    "makeup",
    "skincare",
    "hair",
    "nails",
    "travel",
    "food",
    "cooking",
    "baking",
    "dessert",
    "coffee",
    "fitness",
    "workout",
    "yoga",
    "running",
    "health",
    "wellness",
    "music",
    "dance",
    "art",
    "photography",
    "design",
    "architecture",
    "interior design",
    "tech",
    "ai",
    "gaming",
    "sports",
    "basketball",
    "football",
    "soccer",
    "tennis",
    "cars",
    "motorcycles",
    "pets",
    "nature",
    "gardening",
    "parenting",
    "education",
    "business",
    "finance",
    "entrepreneurship",
    "luxury",
    "streetwear",
    "wedding",
    "lifestyle",
    "marketing",
)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="insta-scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="scrape configured Instagram sources once")
    run_parser.add_argument("--config", default="config.toml")
    run_parser.add_argument("--limit", type=int, default=None)
    run_parser.add_argument("--window-hours", type=int, default=None)

    public_parser = subparsers.add_parser(
        "public",
        help="scrape one public Instagram source without login/session",
    )
    public_parser.add_argument("--source-type", choices=["hashtag", "profile"], default="hashtag")
    public_parser.add_argument("--source-value", required=True)
    public_parser.add_argument("--database", default="data/instagram.sqlite3")
    public_parser.add_argument("--limit", type=int, default=1)
    public_parser.add_argument("--window-hours", type=int, default=24)

    batch_parser = subparsers.add_parser(
        "collect-public",
        help="collect public keyword pages across categories",
    )
    batch_parser.add_argument("--database", default="data/instagram.sqlite3")
    batch_parser.add_argument("--target-keywords", type=int, default=1000)
    batch_parser.add_argument(
        "--categories",
        nargs="*",
        default=None,
        help="optional category seeds; defaults to a broad built-in set",
    )
    batch_parser.add_argument("--window-hours", type=int, default=24)
    batch_parser.add_argument("--max-memory-percent", type=float, default=80.0)

    latest_parser = subparsers.add_parser("latest", help="show current keyword trends")
    latest_parser.add_argument("--config", default="config.toml")
    latest_parser.add_argument("--limit", type=int, default=20)
    latest_parser.add_argument("--window-hours", type=int, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "latest":
        config = load_config(args.config)
        initialize_database(config.database_path)
        window_hours = config.trend_window_hours if args.window_hours is None else args.window_hours
        return _print_latest(config.database_path, args.limit, window_hours)
    if args.command == "run":
        config = load_config(args.config)
        config = override_config(
            config,
            max_posts_per_source=args.limit,
            trend_window_hours=args.window_hours,
        )
        initialize_database(config.database_path)
        return _run_once(config)
    if args.command == "public":
        scraper = InstagramScraper(InstagramAuth(username=None, password=None, session_file=None))
        snapshot = scraper.collect_public_snapshot(Source(type=args.source_type, value=args.source_value))
        counts = Counter([snapshot.keyword, *snapshot.related_keywords])
        initialize_database(args.database)
        with connect(args.database) as conn:
            run_id = start_run(conn, source_count=1, window_hours=args.window_hours)
            store_keyword_counts(conn, run_id, counts)
            finish_run(conn, run_id, 0)
            trends = get_trending_keywords(conn, since_hours=args.window_hours, limit=10)
        print(f"scraped public page for {snapshot.keyword}")
        print(f"title: {snapshot.title}")
        print(f"total media count: {snapshot.total_media_count}")
        if snapshot.related_keywords:
            print("related keywords:")
            for keyword in snapshot.related_keywords:
                print(f"- {keyword}")
        else:
            print("related keywords: none")
        _print_trends(trends)
        return 0
    if args.command == "collect-public":
        memory_usage_percent = _memory_usage_percent()
        if memory_usage_percent > args.max_memory_percent:
            print(
                "skipping collect-public: "
                f"memory usage {memory_usage_percent:.1f}% exceeds {args.max_memory_percent:.1f}%"
            )
            return 0
        seeds = _resolve_public_seeds(args.categories)
        scraper = InstagramScraper(InstagramAuth(username=None, password=None, session_file=None))
        pages: list = []
        counts: Counter[str] = Counter()
        for seed in seeds:
            snapshot = scraper.collect_public_snapshot(Source(type="hashtag", value=seed))
            pages.append(snapshot)
            counts.update([snapshot.keyword, *snapshot.related_keywords])
            if len(counts) >= args.target_keywords:
                break
        top_counts = Counter(dict(counts.most_common(args.target_keywords)))
        initialize_database(args.database)
        with connect(args.database) as conn:
            run_id = start_run(conn, source_count=len(pages), window_hours=args.window_hours)
            store_public_pages(conn, run_id, pages)
            store_keyword_counts(conn, run_id, top_counts)
            finish_run(conn, run_id, len(top_counts))
            trends = get_trending_keywords(conn, since_hours=args.window_hours, limit=10)
        print(
            f"collected {len(top_counts)} keywords from {len(pages)} public category pages"
        )
        _print_trends(trends)
        return 0
    raise ValueError(f"unknown command: {args.command}")


def _run_once(config) -> int:
    scraper = InstagramScraper(config.auth)
    posts = scraper.collect_posts(config.sources, config.max_posts_per_source)
    keyword_counter = build_keyword_counter([post.caption for post in posts])

    with connect(config.database_path) as conn:
        run_id = start_run(conn, source_count=len(config.sources), window_hours=config.trend_window_hours)
        store_posts(conn, run_id, posts)
        store_keyword_counts(conn, run_id, keyword_counter)
        finish_run(conn, run_id, len(posts))
        trends = get_trending_keywords(conn, since_hours=config.trend_window_hours, limit=10)

    print(f"collected {len(posts)} posts across {len(config.sources)} sources")
    _print_trends(trends)
    return 0


def _print_latest(database_path: str, limit: int, window_hours: int) -> int:
    with connect(database_path) as conn:
        trends = get_trending_keywords(conn, since_hours=window_hours, limit=limit)
    _print_trends(trends)
    return 0


def _build_public_config(
    *,
    database_path: str,
    source_type: str,
    source_value: str,
    limit: int,
    window_hours: int,
) -> AppConfig:
    return AppConfig(
        database_path=database_path,
        max_posts_per_source=limit,
        trend_window_hours=window_hours,
        sources=(Source(type=source_type, value=source_value),),
        auth=InstagramAuth(username=None, password=None, session_file=None),
    )


def _resolve_public_seeds(categories: list[str] | None) -> tuple[str, ...]:
    if not categories:
        return DEFAULT_PUBLIC_CATEGORY_SEEDS
    seen: set[str] = set()
    ordered: list[str] = []
    for category in categories:
        normalized = category.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _memory_usage_percent() -> float:
    meminfo_path = Path("/proc/meminfo")
    if not meminfo_path.exists():
        raise RuntimeError("/proc/meminfo is not available on this system")
    values: dict[str, int] = {}
    for line in meminfo_path.read_text(encoding="utf-8").splitlines():
        key, _, remainder = line.partition(":")
        parts = remainder.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0])
        except ValueError as exc:
            raise RuntimeError(f"invalid memory info line: {line}") from exc
    total_kb = values.get("MemTotal")
    available_kb = values.get("MemAvailable")
    if total_kb is None or available_kb is None or total_kb <= 0:
        raise RuntimeError("MemTotal or MemAvailable missing from /proc/meminfo")
    used_kb = total_kb - available_kb
    return used_kb * 100 / total_kb


def _print_trends(trends: list[tuple[str, int]]) -> None:
    if not trends:
        print("no trending keywords yet")
        return
    for rank, (keyword, count) in enumerate(trends, start=1):
        print(f"{rank}. {keyword} ({count})")
