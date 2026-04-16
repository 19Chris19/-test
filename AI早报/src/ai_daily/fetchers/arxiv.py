from __future__ import annotations

from ai_daily.fetchers.rss import RssFetcher


class ArxivFetcher(RssFetcher):
    """arXiv currently ships RSS, so we reuse the standard RSS fetcher."""
