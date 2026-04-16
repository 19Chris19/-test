from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_daily.cli import app
from ai_daily.config import AppSettings
from ai_daily.models.article import Article
from ai_daily.models.publication import PublishedArticle, PublishedIssue
from ai_daily.render.backup import render_backup_markdown
from ai_daily.render.readme import render_readme
from ai_daily.render.rss import render_rss_xml
from ai_daily.storage.article_repo import ArticleRepository
from ai_daily.storage.db import Database
from ai_daily.storage.issue_repo import finalize_publish_transaction


def _published_article(*, article_id: int, rank: int, title: str) -> PublishedArticle:
    return PublishedArticle(
        article_id=article_id,
        section="模型发布",
        rank=rank,
        title=title,
        url=f"https://example.com/{article_id}",
        rendered_summary=f"{title} 摘要",
        dedupe_key=f"dedupe-{article_id}",
        source_url=f"https://example.com/{article_id}",
        article_score=99.0 - rank,
    )


def _published_issue(issue_number: int, title: str, published_at: str) -> PublishedIssue:
    article = _published_article(article_id=issue_number, rank=1, title=title)
    return PublishedIssue(
        issue_id=issue_number,
        issue_number=issue_number,
        report_date="2026-04-15",
        title=title,
        status="published",
        markdown_path=f"data/staging/draft_{issue_number}.md",
        github_url=f"https://github.com/example/repo/issues/{issue_number}",
        published_at=published_at,
        article_count=1,
        articles=[article],
    )


def _seed_published_issues(database: Database) -> None:
    repo = ArticleRepository(database)
    first_issue_articles: list[int] = []
    for article_id, title in [(101, "Release A"), (102, "Release B")]:
        first_issue_articles.append(
            repo.upsert(
                Article(
                    source_id=f"src-{article_id}",
                    source_name="Test Source",
                    source_type="rss",
                    author="Alice",
                    title=title,
                    url=f"https://example.com/{article_id}",
                    canonical_url=f"https://example.com/{article_id}",
                    raw_text=f"{title} raw text",
                    summary="",
                    category="模型发布",
                    score=99.0,
                    dedupe_key=f"dedupe-{article_id}",
                    metadata_snapshot={"source_weight": 1.0},
                    status="selected",
                )
            )
        )

    with database.connect() as connection:
        finalize_publish_transaction(
            connection,
            "2026-04-15",
            "AI 早报 2026-04-15",
            "https://github.com/example/repo/issues/88",
            88,
            first_issue_articles,
            markdown_path="data/staging/draft_2026-04-15.md",
        )

    second_article_id = repo.upsert(
        Article(
            source_id="src-201",
            source_name="Test Source",
            source_type="rss",
            author="Alice",
            title="Tooling C",
            url="https://example.com/201",
            canonical_url="https://example.com/201",
            raw_text="Tooling C raw text",
            summary="",
            category="模型发布",
            score=99.0,
            dedupe_key="dedupe-201",
            metadata_snapshot={"source_weight": 1.0},
            status="selected",
        )
    )

    with database.connect() as connection:
        finalize_publish_transaction(
            connection,
            "2026-04-15",
            "AI 早报 2026-04-15",
            "https://github.com/example/repo/issues/99",
            99,
            [second_article_id],
            markdown_path="data/staging/draft_2026-04-15.md",
        )


def test_render_assets_are_deterministic_and_traceable(monkeypatch) -> None:
    monkeypatch.setenv("AI_DAILY_GITHUB_REPO", "example/repo")
    settings = AppSettings(site_title="AI 早报")
    issue = _published_issue(88, "AI 早报 2026-04-15", "2026-04-15T08:00:00+00:00")

    backup = render_backup_markdown(issue)
    readme = render_readme(settings, [issue])
    rss = render_rss_xml(settings, [issue])
    rss_again = render_rss_xml(settings, [issue])
    empty_rss = render_rss_xml(settings, [])

    assert "<!-- Repository license: MIT -->" in backup
    assert "<!-- Content license: CC BY-NC 4.0 -->" in backup
    assert "<!-- article_id:88" in backup

    assert "## 最近发布" in readme
    assert "docs/AI早报MVP开发规划.md" in readme
    assert "最后更新" not in readme

    assert "<link>https://github.com/example/repo/issues/88</link>" in rss
    assert rss == rss_again
    assert "<lastBuildDate>" not in empty_rss


def test_generate_assets_cli_rebuilds_and_full_regenerates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_DAILY_GITHUB_REPO", "example/repo")
    root = tmp_path / "repo"
    db_path = root / "data" / "ai_daily.db"
    database = Database(db_path)
    database.initialize()
    _seed_published_issues(database)

    runner = CliRunner()

    rebuild_result = runner.invoke(
        app,
        [
            "rebuild",
            "--issue-number",
            "88",
            "--db-path",
            str(db_path),
            "--root",
            str(root),
        ],
    )
    assert rebuild_result.exit_code == 0, rebuild_result.output
    rebuild_payload = json.loads(rebuild_result.stdout)
    assert rebuild_payload["published_issue_count"] == 2
    assert rebuild_payload["backup_issue_count"] == 1
    assert Path(rebuild_payload["paths"]["backup_paths"][0]).name == "issue_88.md"

    backup_88 = (root / "BACKUP" / "issue_88.md").read_text(encoding="utf-8")
    assert "AI 早报 2026-04-15" in backup_88
    assert "CC BY-NC 4.0" in backup_88

    assert not (root / "BACKUP" / "issue_99.md").exists()

    generate_result = runner.invoke(
        app,
        [
            "generate-assets",
            "--db-path",
            str(db_path),
            "--root",
            str(root),
        ],
    )
    assert generate_result.exit_code == 0, generate_result.output
    generate_payload = json.loads(generate_result.stdout)
    assert generate_payload["published_issue_count"] == 2
    assert generate_payload["backup_issue_count"] == 2

    readme = (root / "README.md").read_text(encoding="utf-8")
    rss = (root / "site" / "generated" / "rss.xml").read_text(encoding="utf-8")
    index_html = (root / "site" / "generated" / "index.html").read_text(encoding="utf-8")
    custom_css = (root / "site" / "generated" / "custom.css").read_text(encoding="utf-8")

    assert "最近发布" in readme
    assert "issue_88.md" in readme
    assert "issue_99.md" in readme
    assert "https://github.com/example/repo/issues/88" in rss
    assert "https://github.com/example/repo/issues/99" in rss
    assert "Markdown 备份" in index_html
    assert "--bg:" in custom_css

    assert (root / "site" / "generated" / ".nojekyll").exists()
    assert (root / "BACKUP" / "issue_99.md").exists()
