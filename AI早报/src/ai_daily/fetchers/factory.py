from __future__ import annotations

from ai_daily.fetchers.arxiv import ArxivFetcher
from ai_daily.fetchers.base import BaseFetcher
from ai_daily.fetchers.github import GitHubReleaseFetcher
from ai_daily.fetchers.rss import RssFetcher
from ai_daily.fetchers.web import WebPageFetcher
from ai_daily.models.source import SourceRecord


def create_fetcher(source: SourceRecord, limit: int | None = None) -> BaseFetcher:
    parser = source.parser
    if parser == "arxiv":
        return ArxivFetcher(source, limit=limit)
    if parser == "github_release":
        return GitHubReleaseFetcher(source, limit=limit)
    if parser == "rss":
        return RssFetcher(source, limit=limit)
    if parser == "web":
        return WebPageFetcher(source, limit=limit)
    raise ValueError(f"Unsupported parser: {parser}")

