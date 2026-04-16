from __future__ import annotations

import re
from datetime import UTC, datetime

from feedgen.feed import FeedGenerator

from ai_daily.config import AppSettings
from ai_daily.models.publication import PublishedIssue


def _site_link(settings: AppSettings) -> str:
    if settings.resolved_site_base_url:
        return settings.resolved_site_base_url.rstrip("/")
    if settings.resolved_github_repo:
        return f"https://github.com/{settings.resolved_github_repo}"
    return "https://github.com"


def _issue_datetime(issue: PublishedIssue) -> datetime:
    if issue.published_at:
        parsed = datetime.fromisoformat(issue.published_at.replace("Z", "+00:00"))
    else:
        parsed = datetime.fromisoformat(f"{issue.report_date}T00:00:00+00:00")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def render_rss_xml(settings: AppSettings, issues: list[PublishedIssue]) -> str:
    feed = FeedGenerator()
    feed.id(_site_link(settings))
    feed.title(settings.site_title)
    feed.link(href=_site_link(settings), rel="alternate")
    feed.description(f"{settings.site_title} 的自动更新订阅源")
    feed.language("zh-CN")

    issue_dates: list[datetime] = []
    for issue in sorted(
        issues,
        key=lambda item: (item.published_at or "", item.issue_number),
        reverse=True,
    ):
        issue_dates.append(_issue_datetime(issue))
        entry = feed.add_entry()
        entry.id(issue.github_url)
        entry.title(issue.title)
        entry.link(href=issue.github_url, rel="alternate")
        summary = "；".join(
            article.title for article in sorted(issue.articles, key=lambda item: item.rank)[:3]
        )
        if summary:
            entry.description(f"{issue.article_count} 篇精选：{summary}")
        else:
            entry.description(f"{issue.article_count} 篇精选")
        if issue.published_at:
            entry.pubDate(_issue_datetime(issue).astimezone(UTC))

    if issue_dates:
        feed.lastBuildDate(max(issue_dates).astimezone(UTC))

    rss_xml = feed.rss_str(pretty=True).decode("utf-8")
    if not issue_dates:
        rss_xml = re.sub(r"\n\s*<lastBuildDate>.*?</lastBuildDate>\n?", "\n", rss_xml)
    return rss_xml
