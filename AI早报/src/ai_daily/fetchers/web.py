from __future__ import annotations

import httpx

from ai_daily.fetchers.base import BaseFetcher
from ai_daily.models.article import Article


class WebPageFetcher(BaseFetcher):
    def fetch(self) -> list[Article]:
        response = httpx.get(
            self.source.url,
            headers={"User-Agent": "ai-daily/0.1"},
            timeout=self.settings.fetch_timeout_seconds,
        )
        response.raise_for_status()
        title = self.source.name
        raw_text = self.clean_html(response.text)
        return [
            self.build_article(
                title=title,
                url=self.source.url,
                raw_text=raw_text,
                metadata_snapshot={"source_url": self.source.url},
            )
        ]
