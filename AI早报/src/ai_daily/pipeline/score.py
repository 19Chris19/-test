from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import TypedDict

from ai_daily.models.article import Article
from ai_daily.storage.article_repo import ArticleRepository

HIGH_LEVERAGE_PATTERN = re.compile(
    r"(?i)\b(release|open[- ]?source|sota|breakthrough|v[1-9]\.[0-9]|deprecate)\b"
)
LOW_LEVERAGE_PATTERN = re.compile(r"(?i)\b(discussion|opinion|minor fix|rumor)\b")


class ScoreBreakdown(TypedDict):
    article_id: int
    title: str
    score: float
    high_leverage: bool
    low_leverage: bool
    source_component: float
    time_component: float
    leverage_component: float
    age_hours: float


def is_high_leverage(article: Article) -> bool:
    text = f"{article.title}\n{article.raw_text}"
    return bool(HIGH_LEVERAGE_PATTERN.search(text))


def is_low_leverage(article: Article) -> bool:
    return bool(LOW_LEVERAGE_PATTERN.search(article.title))


def _time_component(age_hours: float, *, high_leverage: bool) -> float:
    threshold = 72 if high_leverage else 24
    if age_hours <= threshold:
        return 30.0
    return 30.0 * math.exp(-((age_hours - threshold) / 24.0))


def score_article(article: Article, source_weight: float = 1.0) -> ScoreBreakdown:
    high = is_high_leverage(article)
    low = is_low_leverage(article)
    source_component = max(0.0, min(30.0, source_weight * 30.0))
    leverage_component = 40.0 if high else 0.0
    if low:
        leverage_component -= 30.0

    age_hours = 0.0
    if article.published_at:
        published = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
        age_hours = max(0.0, (datetime.now(UTC) - published).total_seconds() / 3600)
    time_component = _time_component(age_hours, high_leverage=high)
    score = round(max(0.0, min(100.0, source_component + leverage_component + time_component)), 2)
    return {
        "article_id": article.id or 0,
        "title": article.title,
        "score": score,
        "high_leverage": high,
        "low_leverage": low,
        "source_component": round(source_component, 2),
        "time_component": round(time_component, 2),
        "leverage_component": round(leverage_component, 2),
        "age_hours": round(age_hours, 2),
    }


def run_score(repo: ArticleRepository, *, dry_run: bool = False) -> list[ScoreBreakdown]:
    articles = repo.list_by_status(statuses=["new"])
    rows: list[ScoreBreakdown] = []
    for article in articles:
        source_weight = article.metadata_snapshot.get("source_weight", 1.0)
        breakdown = score_article(article, source_weight=source_weight)
        if not dry_run:
            repo.update_score(article.id or 0, breakdown["score"])
        rows.append(breakdown)
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows
