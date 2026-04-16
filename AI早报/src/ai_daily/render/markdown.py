from __future__ import annotations

import re

from ai_daily.models.article import Article

ARTICLE_ID_PATTERN = re.compile(r"<!--\s*article_id:(\d+)\b[^>]*-->")


def article_metadata_comment(article_id: int, source_url: str, dedupe_key: str) -> str:
    return (
        f"<!-- article_id:{article_id} "
        f"source_url:{source_url} "
        f"dedupe_key:{dedupe_key} -->"
    )


def render_article_block(article: Article, rendered_summary: str) -> str:
    return "\n".join(
        [
            f"### [{article.title}]({article.url})",
            rendered_summary,
            article_metadata_comment(article.id or 0, article.url, article.dedupe_key),
        ]
    )


def extract_article_ids_from_draft(content: str) -> list[int]:
    return [int(match) for match in ARTICLE_ID_PATTERN.findall(content)]
