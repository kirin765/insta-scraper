from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tomllib

from .models import AppConfig, InstagramAuth, Source


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    database_path = str(_get_value(data, "database_path", default="data/instagram.sqlite3"))
    max_posts_per_source = _get_int(data, "max_posts_per_source", default=50)
    trend_window_hours = _get_int(data, "trend_window_hours", default=24)

    instagram_data = data.get("instagram", {})
    if instagram_data is None:
        instagram_data = {}
    if not isinstance(instagram_data, dict):
        raise ValueError("[instagram] must be a table")

    sources_data = data.get("sources", [])
    if not sources_data:
        raise ValueError("config must define at least one [[sources]] entry")

    sources = tuple(_parse_source(source) for source in sources_data)
    auth = InstagramAuth(
        username=_optional_string(instagram_data, "username"),
        password=_optional_string(instagram_data, "password"),
        session_file=_optional_string(instagram_data, "session_file"),
    )
    return AppConfig(
        database_path=database_path,
        max_posts_per_source=max_posts_per_source,
        trend_window_hours=trend_window_hours,
        sources=sources,
        auth=auth,
    )


def override_config(
    config: AppConfig,
    *,
    database_path: str | None = None,
    max_posts_per_source: int | None = None,
    trend_window_hours: int | None = None,
) -> AppConfig:
    return replace(
        config,
        database_path=config.database_path if database_path is None else database_path,
        max_posts_per_source=(
            config.max_posts_per_source if max_posts_per_source is None else max_posts_per_source
        ),
        trend_window_hours=(
            config.trend_window_hours if trend_window_hours is None else trend_window_hours
        ),
    )


def _parse_source(entry: object) -> Source:
    if not isinstance(entry, dict):
        raise ValueError("each [[sources]] entry must be a table")
    source_type = _required_string(entry, "type")
    if source_type not in {"hashtag", "profile"}:
        raise ValueError("source type must be either 'hashtag' or 'profile'")
    value = _required_string(entry, "value")
    return Source(type=source_type, value=value)


def _get_value(data: dict, key: str, default: object) -> object:
    value = data.get(key, default)
    if value is None:
        return default
    return value


def _get_int(data: dict, key: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return value


def _optional_string(data: dict, key: str) -> str | None:
    value = data.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _required_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()
