from __future__ import annotations

from pathlib import Path

from ai_daily.config import AppSettings, load_categories
from ai_daily.models.article import Article
from ai_daily.pipeline.draft import (
    DraftPlan,
    build_draft,
    build_draft_plan,
    select_articles_for_draft,
    write_draft,
)
from ai_daily.storage.article_repo import ArticleRepository
from ai_daily.storage.db import Database


def _selected_article(article_id: int, *, category: str, score: float, title: str) -> Article:
    return Article(
        id=article_id,
        source_id=f"src-{article_id}",
        source_name="Test Source",
        source_type="rss",
        author="Alice",
        title=title,
        url=f"https://example.com/{article_id}",
        canonical_url=f"https://example.com/{article_id}",
        raw_text=f"{title} raw text",
        summary="",
        category=category,
        score=score,
        dedupe_key=f"dedupe-{article_id}",
        metadata_snapshot={"source_weight": 0.9},
        status="selected",
    )


def test_select_articles_for_draft_caps_sections_and_total() -> None:
    categories = load_categories()
    articles = [
        _selected_article(1, category="模型发布", score=98, title="A"),
        _selected_article(2, category="模型发布", score=95, title="B"),
        _selected_article(3, category="模型发布", score=90, title="C"),
        _selected_article(4, category="模型发布", score=80, title="D"),
        _selected_article(5, category="开发工具", score=89, title="E"),
        _selected_article(6, category="开发工具", score=88, title="F"),
        _selected_article(7, category="产品更新", score=87, title="G"),
        _selected_article(8, category="产品更新", score=86, title="H"),
    ]

    selected = select_articles_for_draft(
        articles,
        categories=categories,
        per_section_limit=2,
        max_total=5,
    )

    assert sum(len(items) for items in selected.values()) == 5
    assert len(selected["模型发布"]) == 2
    assert [item.title for item in selected["模型发布"]] == ["A", "B"]


def test_write_draft_overwrites_and_contains_hidden_metadata(tmp_path) -> None:
    article = _selected_article(1, category="模型发布", score=98, title="Open source release")
    plan = DraftPlan(
        report_date="2026-04-15",
        output_path=tmp_path / "draft_2026-04-15.md",
        total_articles=1,
        per_section_limit=3,
        max_total=15,
        sections={"模型发布": [article]},
    )

    plan.output_path.write_text("stale content", encoding="utf-8")
    content = write_draft(plan)
    written = plan.output_path.read_text(encoding="utf-8")

    assert "stale content" not in written
    assert "<!-- article_id:1" in written
    assert "### [Open source release](https://example.com/1)" in content


def test_build_draft_plan_reads_selected_articles_from_db(tmp_path) -> None:
    database = Database(tmp_path / "ai_daily.db")
    database.initialize()
    repo = ArticleRepository(database)

    repo.upsert(
        _selected_article(1, category="模型发布", score=91, title="Release one").model_copy(
            update={"id": None, "dedupe_key": "draft-1"}
        )
    )
    repo.upsert(
        _selected_article(2, category="开发工具", score=77, title="Tooling two").model_copy(
            update={
                "id": None,
                "dedupe_key": "draft-2",
                "url": "https://example.com/2",
                "canonical_url": "https://example.com/2",
            }
        )
    )

    plan = build_draft_plan(
        repo,
        settings=AppSettings(),
        categories=load_categories(),
        report_date="2026-04-15",
        per_section_limit=3,
        max_total=15,
    )
    content = build_draft(plan.report_date, plan.sections)

    assert plan.report_date == "2026-04-15"
    assert plan.total_articles == 2
    assert Path("data/staging/draft_2026-04-15.md").name == plan.output_path.name
    assert "## 模型发布" in content
    assert "## 开发工具" in content
