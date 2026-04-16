from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ai_daily.config import PROJECT_ROOT, AppSettings
from ai_daily.models.publication import PublishedIssue


def _template_env(template_root: Path | None = None) -> Environment:
    root = template_root or (PROJECT_ROOT / "site" / "templates")
    return Environment(
        loader=FileSystemLoader(str(root)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _site_link(settings: AppSettings) -> str:
    if settings.resolved_site_base_url:
        return settings.resolved_site_base_url.rstrip("/")
    if settings.resolved_github_repo:
        return f"https://github.com/{settings.resolved_github_repo}"
    return "https://github.com"


def render_site_index(
    settings: AppSettings,
    issues: list[PublishedIssue],
    *,
    rss_href: str = "rss.xml",
    backup_url_base: str | None = None,
    template_root: Path | None = None,
) -> str:
    env = _template_env(template_root)
    template = env.get_template("index.html.j2")
    issue_rows = []
    backup_base = backup_url_base or ""
    if not backup_base and settings.resolved_github_repo:
        backup_base = f"https://github.com/{settings.resolved_github_repo}/blob/main/BACKUP"

    for issue in sorted(
        issues,
        key=lambda item: (item.published_at or "", item.issue_number),
        reverse=True,
    ):
        issue_rows.append(
            {
                "issue_number": issue.issue_number,
                "report_date": issue.report_date,
                "title": issue.title,
                "github_url": issue.github_url,
                "article_count": issue.article_count,
                "backup_url": (
                    f"{backup_base}/{issue.backup_filename}" if backup_base else ""
                ),
                "backup_filename": issue.backup_filename,
                "top_titles": [
                    article.title
                    for article in sorted(issue.articles, key=lambda item: item.rank)[:3]
                ],
            }
        )

    return template.render(
        title=settings.site_title,
        subtitle="发布后的 AI 早报静态站点与订阅入口",
        issues=issue_rows[:12],
        rss_href=rss_href,
        site_link=_site_link(settings),
    )
