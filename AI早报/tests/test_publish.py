from __future__ import annotations

from pathlib import Path

from ai_daily.config import load_categories
from ai_daily.models.article import Article
from ai_daily.pipeline.draft import build_draft, select_articles_for_draft
from ai_daily.pipeline.publish import GitHubIssueResponse, publish_draft
from ai_daily.storage.article_repo import ArticleRepository
from ai_daily.storage.db import Database


def _selected_article(
    *,
    category: str,
    score: float,
    title: str,
    url: str,
    dedupe_key: str,
) -> Article:
    return Article(
        source_id="src-1",
        source_name="Test Source",
        source_type="rss",
        author="Alice",
        title=title,
        url=url,
        canonical_url=url,
        raw_text=f"{title} raw text",
        summary="",
        category=category,
        score=score,
        dedupe_key=dedupe_key,
        metadata_snapshot={"source_weight": 1.0},
        status="selected",
    )


def _seed_publish_draft(database: Database, draft_path: Path) -> list[int]:
    repo = ArticleRepository(database)
    repo.upsert(
        _selected_article(
            category="模型发布",
            score=98.0,
            title="Release A",
            url="https://example.com/a",
            dedupe_key="publish-a",
        )
    )
    repo.upsert(
        _selected_article(
            category="模型发布",
            score=91.0,
            title="Release B",
            url="https://example.com/b",
            dedupe_key="publish-b",
        )
    )
    repo.upsert(
        _selected_article(
            category="开发工具",
            score=90.0,
            title="Tooling C",
            url="https://example.com/c",
            dedupe_key="publish-c",
        )
    )

    selected = repo.list_by_status(statuses=["selected"])
    sections = select_articles_for_draft(
        selected,
        categories=load_categories(),
        per_section_limit=1,
        max_total=2,
    )
    draft_path.write_text(build_draft("2026-04-15", sections), encoding="utf-8")
    return [item.id or 0 for items in sections.values() for item in items]


def test_publish_dry_run_only_parses_draft(tmp_path) -> None:
    db_path = tmp_path / "ai_daily.db"
    draft_path = tmp_path / "draft_2026-04-15.md"
    database = Database(db_path)
    database.initialize()

    expected_ids = _seed_publish_draft(database, draft_path)

    result = publish_draft(
        database,
        report_date="2026-04-15",
        draft_path=draft_path,
        repo_slug="example/repo",
        dry_run=True,
    )

    assert result.status == "dry_run"
    assert result.article_ids == expected_ids

    with database.connect() as connection:
        issue_count = connection.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
        statuses = {
            row["status"]: row["total"]
            for row in connection.execute(
                "SELECT status, COUNT(*) AS total FROM articles GROUP BY status"
            ).fetchall()
        }

    assert issue_count == 0
    assert statuses == {"selected": 3}


def test_publish_transaction_persists_issue_and_archives_leftovers(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "ai_daily.db"
    draft_path = tmp_path / "draft_2026-04-15.md"
    database = Database(db_path)
    database.initialize()

    published_ids = _seed_publish_draft(database, draft_path)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        "ai_daily.pipeline.publish.create_github_issue",
        lambda *args, **kwargs: GitHubIssueResponse(
            number=88,
            html_url="https://github.com/example/repo/issues/88",
        ),
    )

    result = publish_draft(
        database,
        report_date="2026-04-15",
        draft_path=draft_path,
        repo_slug="example/repo",
    )

    assert result.status == "published"
    assert result.issue_number == 88
    assert result.github_url == "https://github.com/example/repo/issues/88"
    assert result.article_ids == published_ids

    with database.connect() as connection:
        issue_row = connection.execute(
            """
            SELECT issue_number, title, status, markdown_path, github_url
            FROM issues
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        issue_links = connection.execute(
            """
            SELECT article_id, section, rank, title_snapshot, source_url_snapshot
            FROM issue_articles
            ORDER BY rank
            """
        ).fetchall()
        status_counts = {
            row["status"]: row["total"]
            for row in connection.execute(
                "SELECT status, COUNT(*) AS total FROM articles GROUP BY status"
            ).fetchall()
        }

    assert issue_row["issue_number"] == 88
    assert issue_row["status"] == "published"
    assert issue_row["markdown_path"] == str(draft_path)
    assert issue_row["github_url"] == "https://github.com/example/repo/issues/88"
    assert [row["article_id"] for row in issue_links] == published_ids
    assert [row["rank"] for row in issue_links] == [1, 2]
    assert status_counts == {"archived": 1, "published": 2}
