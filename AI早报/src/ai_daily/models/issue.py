from __future__ import annotations

from pydantic import BaseModel


class IssueRecord(BaseModel):
    id: int | None = None
    issue_number: int | None = None
    report_date: str
    title: str
    status: str = "draft"
    markdown_path: str = ""
    github_url: str = ""
    published_at: str | None = None


class IssueArticleLink(BaseModel):
    issue_id: int
    article_id: int
    section: str
    rank: int
    title_snapshot: str
    source_url_snapshot: str
    article_score_snapshot: float = 0.0
    rendered_summary: str

