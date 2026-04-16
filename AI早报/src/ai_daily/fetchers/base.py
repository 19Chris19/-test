from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup
from trafilatura import extract

from ai_daily.config import load_settings
from ai_daily.models.article import Article
from ai_daily.models.source import SourceRecord
from ai_daily.utils.hashes import sha256_text
from ai_daily.utils.urls import canonicalize_url


class BaseFetcher(ABC):
    def __init__(self, source: SourceRecord, limit: int | None = None) -> None:
        self.source = source
        self.limit = limit
        self.settings = load_settings()
        self.config = source.model_dump()

    @abstractmethod
    def fetch(self) -> list[Article]:
        raise NotImplementedError

    def clean_html(self, raw_html: str) -> str:
        cleaned = extract(raw_html, include_links=False, include_images=False)
        if cleaned:
            return " ".join(cleaned.split())
        soup = BeautifulSoup(raw_html, "html.parser")
        return " ".join(soup.get_text(" ", strip=True).split())

    def generate_dedupe_key(self, title: str, url: str) -> str:
        canonical_url = canonicalize_url(url)
        fingerprint = f"{self.source.id}|{canonical_url}|{' '.join(title.lower().split())}"
        return sha256_text(fingerprint)

    def build_article(
        self,
        *,
        title: str,
        url: str,
        author: str = "",
        raw_text: str = "",
        published_at: str | None = None,
        metadata_snapshot: dict[str, Any] | None = None,
    ) -> Article:
        metadata = {
            "source_weight": self.source.weight,
            "source_parser": self.source.parser,
        }
        metadata.update(metadata_snapshot or {})
        return Article(
            source_id=self.source.id,
            source_name=self.source.name,
            source_type=self.source.type,
            author=author,
            title=title,
            url=url,
            canonical_url=canonicalize_url(url),
            published_at=published_at,
            fetched_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            raw_text=raw_text,
            dedupe_key=self.generate_dedupe_key(title, url),
            metadata_snapshot=metadata,
            status="new",
        )
