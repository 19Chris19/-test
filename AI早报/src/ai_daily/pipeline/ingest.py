from __future__ import annotations

from ai_daily.fetchers.base import BaseFetcher
from ai_daily.storage.article_repo import ArticleRepository


def run_ingest(fetcher: BaseFetcher, repo: ArticleRepository) -> int:
    count = 0
    for article in fetcher.fetch():
        repo.upsert(article)
        count += 1
    return count

