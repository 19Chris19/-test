from __future__ import annotations

from ai_daily.config import load_categories
from ai_daily.llm.client import LlmClient
from ai_daily.models.article import Article
from ai_daily.pipeline.classify import run_classify
from ai_daily.pipeline.dedupe import run_dedupe
from ai_daily.pipeline.score import score_article
from ai_daily.storage.article_repo import ArticleRepository
from ai_daily.storage.db import Database


def _article(**overrides) -> Article:
    payload = {
        "source_id": "src-1",
        "source_name": "Test Source",
        "source_type": "rss",
        "author": "Alice",
        "title": "Test title",
        "url": "https://example.com/post",
        "canonical_url": "https://example.com/post",
        "raw_text": "Release text",
        "dedupe_key": "key-1",
        "metadata_snapshot": {"source_weight": 0.9},
        "status": "new",
        "score": 0.0,
    }
    payload.update(overrides)
    return Article(**payload)


def test_score_prefers_high_leverage_over_low_leverage() -> None:
    high = _article(title="Open source breakthrough release", raw_text="SOTA system")
    low = _article(title="Minor fix discussion", raw_text="Opinion piece", dedupe_key="key-2")

    high_score = score_article(high, source_weight=0.9)
    low_score = score_article(low, source_weight=0.9)

    assert high_score["high_leverage"] is True
    assert low_score["low_leverage"] is True
    assert high_score["score"] > low_score["score"]


def test_run_dedupe_filters_duplicate_urls(tmp_path) -> None:
    database = Database(tmp_path / "ai_daily.db")
    database.initialize()
    repo = ArticleRepository(database)

    first_id = repo.upsert(
        _article(
            source_id="src-1",
            dedupe_key="dedupe-1",
            url="https://example.com/post?utm_source=rss",
            canonical_url="https://example.com/post?utm_source=rss",
        )
    )
    second_id = repo.upsert(
        _article(
            source_id="src-2",
            dedupe_key="dedupe-2",
            url="https://example.com/post?utm_medium=email",
            canonical_url="https://example.com/post?utm_medium=email",
        )
    )

    result = run_dedupe(repo)
    remaining = repo.list_by_status(statuses=["new", "filtered"])
    by_id = {item.id: item for item in remaining}

    assert result["filtered"] == 1
    assert by_id[first_id].status == "new"
    assert by_id[second_id].status == "filtered"
    assert by_id[first_id].canonical_url == "https://example.com/post"


def test_run_classify_uses_rules_and_degraded_fallback(tmp_path) -> None:
    database = Database(tmp_path / "ai_daily.db")
    database.initialize()
    repo = ArticleRepository(database)

    repo.upsert(
        _article(
            dedupe_key="classify-1",
            title="Gaussian Splatting viewer release",
            raw_text="WebXR gaussian splatting pipeline update",
            score=90.0,
        )
    )
    repo.upsert(
        _article(
            dedupe_key="classify-2",
            title="A new post with ambiguous theme",
            raw_text="No matching category keyword here",
            score=88.0,
            url="https://example.com/post-2",
            canonical_url="https://example.com/post-2",
        )
    )

    stats = run_classify(
        repo,
        categories=load_categories(),
        llm_client=LlmClient(database=database),
        threshold=45.0,
    )

    selected = repo.list_by_status(statuses=["selected"])
    degraded = repo.list_by_status(statuses=["degraded"])

    assert stats["selected"] == 1
    assert stats["degraded"] == 1
    assert selected[0].category == "3DGS / XR 专报"
    assert degraded[0].category == "行业动态"
