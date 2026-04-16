from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PublishedArticle:
    article_id: int
    section: str
    rank: int
    title: str
    url: str
    rendered_summary: str
    dedupe_key: str
    source_url: str
    article_score: float


@dataclass(slots=True)
class PublishedIssue:
    issue_id: int
    issue_number: int
    report_date: str
    title: str
    status: str
    markdown_path: str
    github_url: str
    published_at: str | None
    article_count: int
    articles: list[PublishedArticle] = field(default_factory=list)

    @property
    def backup_filename(self) -> str:
        return f"issue_{self.issue_number}.md"
