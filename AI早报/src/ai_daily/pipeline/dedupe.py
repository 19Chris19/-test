from __future__ import annotations

from ai_daily.models.article import Article
from ai_daily.storage.article_repo import ArticleRepository
from ai_daily.utils.hashes import sha256_text
from ai_daily.utils.urls import canonicalize_url


def normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def author_fingerprint(article: Article) -> str:
    author = article.author or article.metadata_snapshot.get("author", "")
    return sha256_text(f"{normalize_title(article.title)}|{' '.join(author.lower().split())}")


def run_dedupe(repo: ArticleRepository) -> dict[str, int]:
    articles = sorted(repo.list_by_status(statuses=["new"]), key=lambda item: item.id or 0)
    seen_urls: set[str] = set()
    seen_title_author: set[str] = set()
    filtered = 0

    for article in articles:
        canonical_url = canonicalize_url(article.url)
        title_author_key = author_fingerprint(article)
        duplicate = canonical_url in seen_urls or title_author_key in seen_title_author
        if duplicate:
            repo.update_after_dedupe(
                article.id or 0,
                canonical_url=canonical_url,
                status="filtered",
            )
            filtered += 1
            continue

        seen_urls.add(canonical_url)
        seen_title_author.add(title_author_key)
        repo.update_after_dedupe(article.id or 0, canonical_url=canonical_url, status="new")

    return {"processed": len(articles), "filtered": filtered, "kept": len(articles) - filtered}
