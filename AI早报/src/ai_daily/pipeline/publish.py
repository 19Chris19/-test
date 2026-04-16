from __future__ import annotations

import os
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from ai_daily.config import PROJECT_ROOT, AppSettings, load_settings
from ai_daily.pipeline.draft import default_report_date
from ai_daily.render.markdown import extract_article_ids_from_draft
from ai_daily.storage.db import Database
from ai_daily.storage.issue_repo import finalize_publish_transaction


class GitHubIssueResponse(BaseModel):
    number: int
    html_url: str


class PublishResult(BaseModel):
    report_date: str
    draft_path: str
    issue_title: str
    repo_slug: str = ""
    article_ids: list[int] = Field(default_factory=list)
    dry_run: bool = False
    status: str
    issue_number: int | None = None
    github_url: str = ""
    issue_id: int | None = None
    published_article_count: int = 0
    archived_article_count: int = 0


def default_draft_path(report_date: str) -> Path:
    return PROJECT_ROOT / "data" / "staging" / f"draft_{report_date}.md"


def load_draft_content(report_date: str, draft_path: Path | None = None) -> tuple[Path, str]:
    path = draft_path or default_draft_path(report_date)
    return path, path.read_text(encoding="utf-8")


def extract_issue_title(content: str, report_date: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return f"AI 早报 {report_date}"


def resolve_repo_slug(settings: AppSettings, override: str | None = None) -> str:
    if override:
        return override
    env_override = os.getenv("AI_DAILY_GITHUB_REPO") or os.getenv("GITHUB_REPOSITORY")
    return env_override or settings.github_repo


def resolve_github_token() -> str:
    return os.getenv("GITHUB_TOKEN") or os.getenv("AI_DAILY_GITHUB_TOKEN") or ""


def create_github_issue(repo_slug: str, token: str, title: str, body: str) -> GitHubIssueResponse:
    owner, _, repo = repo_slug.partition("/")
    if not owner or not repo:
        raise ValueError(f"Invalid GitHub repository slug: {repo_slug!r}")

    response = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-daily/0.1.0",
        },
        json={"title": title, "body": body},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    return GitHubIssueResponse(number=int(payload["number"]), html_url=str(payload["html_url"]))


def _find_published_issue(database: Database, report_date: str) -> dict | None:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT id, issue_number, github_url
            FROM issues
            WHERE report_date = ? AND status = 'published'
            ORDER BY id DESC
            LIMIT 1
            """,
            (report_date,),
        ).fetchone()
    if row is None:
        return None
    return {
        "issue_id": int(row["id"]),
        "issue_number": int(row["issue_number"]) if row["issue_number"] is not None else None,
        "github_url": row["github_url"],
    }


def publish_draft(
    database: Database,
    *,
    report_date: str | None = None,
    draft_path: Path | None = None,
    repo_slug: str | None = None,
    dry_run: bool = False,
) -> PublishResult:
    settings = load_settings()
    final_report_date = report_date or default_report_date(settings)
    resolved_repo_slug = resolve_repo_slug(settings, override=repo_slug)
    path, content = load_draft_content(final_report_date, draft_path=draft_path)
    article_ids = extract_article_ids_from_draft(content)
    if not article_ids:
        raise ValueError(f"No article ids found in draft: {path}")

    title = extract_issue_title(content, final_report_date)

    if dry_run:
        return PublishResult(
            report_date=final_report_date,
            draft_path=str(path),
            issue_title=title,
            repo_slug=resolved_repo_slug,
            article_ids=article_ids,
            dry_run=True,
            status="dry_run",
            published_article_count=len(article_ids),
        )

    existing = _find_published_issue(database, final_report_date)
    if existing is not None:
        return PublishResult(
            report_date=final_report_date,
            draft_path=str(path),
            issue_title=title,
            repo_slug=resolved_repo_slug,
            article_ids=article_ids,
            dry_run=False,
            status="already_published",
            issue_number=existing["issue_number"],
            github_url=existing["github_url"],
            issue_id=existing["issue_id"],
            published_article_count=len(article_ids),
        )

    token = resolve_github_token()
    if not resolved_repo_slug:
        raise ValueError("Missing GitHub repository slug")
    if not token:
        raise ValueError("Missing GitHub token")

    issue = create_github_issue(resolved_repo_slug, token, title, content)
    with database.connect() as connection:
        transaction = finalize_publish_transaction(
            connection,
            final_report_date,
            title,
            issue.html_url,
            issue.number,
            article_ids,
            markdown_path=str(path),
        )

    return PublishResult(
        report_date=final_report_date,
        draft_path=str(path),
        issue_title=title,
        repo_slug=resolved_repo_slug,
        article_ids=transaction.article_ids,
        dry_run=False,
        status="published",
        issue_number=issue.number,
        github_url=issue.html_url,
        issue_id=transaction.issue_id,
        published_article_count=len(transaction.article_ids),
        archived_article_count=transaction.archived_count,
    )
