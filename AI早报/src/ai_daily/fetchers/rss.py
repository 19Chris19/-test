from __future__ import annotations

import feedparser
import httpx

from ai_daily.fetchers.adapter import coerce_datetime
from ai_daily.fetchers.base import BaseFetcher
from ai_daily.models.article import Article


class RssFetcher(BaseFetcher):
    def fetch(self) -> list[Article]:
        response = httpx.get(
            self.source.url,
            headers={"User-Agent": "ai-daily/0.1"},
            timeout=self.settings.fetch_timeout_seconds,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        items: list[Article] = []
        for entry in feed.entries[: self.limit]:
            raw_html = entry.get("summary", "") or entry.get("description", "")
            raw_text = self.clean_html(raw_html) if raw_html else entry.get("title", "")
            author = entry.get("author", "")
            article = self.build_article(
                title=entry.get("title", "Untitled"),
                url=entry.get("link", ""),
                author=author,
                raw_text=raw_text,
                published_at=coerce_datetime(entry.get("published") or entry.get("updated")),
                metadata_snapshot={
                    "feed_id": entry.get("id", ""),
                    "tags": [tag.get("term", "") for tag in entry.get("tags", [])],
                },
            )
            items.append(article)
        return items
