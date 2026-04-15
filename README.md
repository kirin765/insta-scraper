# Instagram Viral Keyword Collector

Periodic Instagram keyword collection for cron or any external scheduler.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Config

Create `config.toml`:

```toml
database_path = "data/instagram.sqlite3"
max_posts_per_source = 50
trend_window_hours = 24

[instagram]
username = ""
password = ""
session_file = "data/instagram.session"

[[sources]]
type = "hashtag"
value = "fashion"

[[sources]]
type = "profile"
value = "nike"
```

## Run

```bash
insta-scraper run --config config.toml
insta-scraper latest --config config.toml
```

Public-only, no-login one-source scrape against Instagram's logged-out popular hashtag page:

```bash
insta-scraper public --source-type hashtag --source-value fashion --limit 1
```

Hourly multi-category keyword collection to SQLite:

```bash
insta-scraper collect-public --database data/instagram.sqlite3 --target-keywords 1000 --max-memory-percent 80
```

To limit or override the category seeds:

```bash
insta-scraper collect-public --categories fashion beauty travel food fitness tech music sports
```

## Cron

```cron
0 * * * * /path/to/project/.venv/bin/insta-scraper collect-public --database /path/to/project/data/instagram.sqlite3 --target-keywords 1000 --max-memory-percent 80 >> /path/to/project/logs/public-keywords.log 2>&1
```
