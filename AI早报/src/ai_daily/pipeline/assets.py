from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ai_daily.config import PROJECT_ROOT, AppSettings, load_settings
from ai_daily.models.publication import PublishedArticle, PublishedIssue
from ai_daily.render.backup import render_backup_markdown
from ai_daily.render.readme import render_readme
from ai_daily.render.rss import render_rss_xml
from ai_daily.render.site import render_site_index
from ai_daily.storage.db import Database
from ai_daily.storage.issue_repo import IssueRepository


@dataclass(slots=True)
class AssetPaths:
    readme_path: Path
    rss_path: Path
    site_index_path: Path
    site_css_path: Path
    nojekyll_path: Path
    backup_paths: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class AssetResult:
    paths: AssetPaths
    published_issue_count: int
    backup_issue_count: int


def _resolve_root(root: Path | None) -> Path:
    settings = load_settings()
    if root is not None:
        return root
    return Path(settings.resolved_database_path).parent.parent


def _site_generated_dir(root: Path) -> Path:
    return root / "site" / "generated"


def _site_link(settings: AppSettings) -> str:
    if settings.resolved_site_base_url:
        return settings.resolved_site_base_url.rstrip("/")
    if settings.resolved_github_repo:
        return f"https://github.com/{settings.resolved_github_repo}"
    return "https://github.com"


def _backup_base_url(settings: AppSettings) -> str:
    if settings.resolved_github_repo:
        return f"https://github.com/{settings.resolved_github_repo}/blob/main/BACKUP"
    return ""


def _read_published_issues(database: Database) -> list[PublishedIssue]:
    issue_repo = IssueRepository(database)
    issue_rows = issue_repo.list_published()
    issues: list[PublishedIssue] = []

    with database.connect() as connection:
        for issue_row in issue_rows:
            article_rows = connection.execute(
                """
                SELECT
                    ia.article_id,
                    ia.section,
                    ia.rank,
                    ia.title_snapshot,
                    ia.source_url_snapshot,
                    ia.article_score_snapshot,
                    ia.rendered_summary,
                    a.dedupe_key
                FROM issue_articles AS ia
                JOIN articles AS a ON a.id = ia.article_id
                WHERE ia.issue_id = ?
                ORDER BY ia.rank ASC, ia.article_id ASC
                """,
                (issue_row.id,),
            ).fetchall()

            articles = [
                PublishedArticle(
                    article_id=row["article_id"],
                    section=row["section"],
                    rank=row["rank"],
                    title=row["title_snapshot"],
                    url=row["source_url_snapshot"],
                    rendered_summary=row["rendered_summary"],
                    dedupe_key=row["dedupe_key"],
                    source_url=row["source_url_snapshot"],
                    article_score=row["article_score_snapshot"],
                )
                for row in article_rows
            ]
            issues.append(
                PublishedIssue(
                    issue_id=issue_row.id or 0,
                    issue_number=issue_row.issue_number or 0,
                    report_date=issue_row.report_date,
                    title=issue_row.title,
                    status=issue_row.status,
                    markdown_path=issue_row.markdown_path,
                    github_url=issue_row.github_url,
                    published_at=issue_row.published_at,
                    article_count=len(articles),
                    articles=articles,
                )
            )
    return issues


def _read_issue_by_number(database: Database, issue_number: int) -> PublishedIssue:
    for issue in _read_published_issues(database):
        if issue.issue_number == issue_number:
            return issue
    raise ValueError(f"Published issue #{issue_number} not found")


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _copy_site_css(root: Path) -> Path:
    source = PROJECT_ROOT / "site" / "static" / "custom.css"
    target = _site_generated_dir(root) / "custom.css"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def _write_nojekyll(root: Path) -> Path:
    path = _site_generated_dir(root) / ".nojekyll"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def _write_backups(root: Path, issues: list[PublishedIssue]) -> list[Path]:
    return [
        _write_text(root / "BACKUP" / issue.backup_filename, render_backup_markdown(issue))
        for issue in issues
    ]


def generate_assets(
    database: Database,
    *,
    root: Path | None = None,
    issue_number: int | None = None,
    rebuild_all_backups: bool = True,
) -> tuple[AssetResult, list[PublishedIssue]]:
    resolved_root = _resolve_root(root)
    settings = load_settings()
    published_issues = _read_published_issues(database)

    if issue_number is not None:
        backup_issues = [_read_issue_by_number(database, issue_number)]
    elif rebuild_all_backups:
        backup_issues = published_issues
    else:
        backup_issues = []

    readme_path = _write_text(
        resolved_root / "README.md",
        render_readme(
            settings,
            published_issues,
            site_path="site/generated/index.html",
            rss_path="site/generated/rss.xml",
        ),
    )
    site_dir = _site_generated_dir(resolved_root)
    rss_path = _write_text(site_dir / "rss.xml", render_rss_xml(settings, published_issues))
    site_index_path = _write_text(
        site_dir / "index.html",
        render_site_index(
            settings,
            published_issues,
            rss_href="rss.xml",
            backup_url_base=_backup_base_url(settings),
        ),
    )
    site_css_path = _copy_site_css(resolved_root)
    nojekyll_path = _write_nojekyll(resolved_root)
    backup_paths = _write_backups(resolved_root, backup_issues)

    return (
        AssetResult(
            paths=AssetPaths(
                readme_path=readme_path,
                rss_path=rss_path,
                site_index_path=site_index_path,
                site_css_path=site_css_path,
                nojekyll_path=nojekyll_path,
                backup_paths=backup_paths,
            ),
            published_issue_count=len(published_issues),
            backup_issue_count=len(backup_issues),
        ),
        published_issues,
    )
