from __future__ import annotations

from collections import Counter
import re

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_]+")
HASHTAG_RE = re.compile(r"#([A-Za-z0-9가-힣_]+)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "our",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
        "you",
        "your",
        "그리고",
        "그",
        "그냥",
        "나는",
        "너무",
        "더",
        "에서",
        "에게",
        "하다",
        "합니다",
        "오늘",
        "사진",
        "영상",
        "좋아요",
    }
)


def extract_keywords(text: str) -> list[str]:
    if not text:
        return []
    normalized = URL_RE.sub(" ", text.lower())
    keywords: list[str] = []
    seen: set[str] = set()

    for raw in HASHTAG_RE.findall(normalized):
        keyword = raw.strip("_")
        if _accept(keyword) and keyword not in seen:
            seen.add(keyword)
            keywords.append(keyword)

    for raw in TOKEN_RE.findall(normalized):
        keyword = raw.strip("_")
        if _accept(keyword) and keyword not in seen:
            seen.add(keyword)
            keywords.append(keyword)

    return keywords


def build_keyword_counter(texts: list[str]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(extract_keywords(text))
    return counter


def _accept(keyword: str) -> bool:
    return len(keyword) >= 2 and keyword not in STOPWORDS and not keyword.isdigit()
