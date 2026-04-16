from __future__ import annotations

from ai_daily.render.markdown import (
    article_metadata_comment,
    extract_article_ids_from_draft,
)


def test_article_metadata_comment_contains_trace_fields() -> None:
    comment = article_metadata_comment(12, "https://example.com", "abc123")

    assert "article_id:12" in comment
    assert "source_url:https://example.com" in comment
    assert "dedupe_key:abc123" in comment


def test_extract_article_ids_from_draft_preserves_order() -> None:
    content = """
    # AI 早报 2026-04-15

    ### [One](https://example.com/1)
    summary
    <!-- article_id:12 source_url:https://example.com/1 dedupe_key:abc -->

    ### [Two](https://example.com/2)
    summary
    <!-- article_id:3 source_url:https://example.com/2 dedupe_key:def -->
    """

    assert extract_article_ids_from_draft(content) == [12, 3]
