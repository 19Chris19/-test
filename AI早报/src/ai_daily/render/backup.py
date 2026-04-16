from __future__ import annotations

from collections import OrderedDict

from ai_daily.models.publication import PublishedArticle, PublishedIssue
from ai_daily.render.markdown import article_metadata_comment


def _group_articles(issue: PublishedIssue) -> OrderedDict[str, list[PublishedArticle]]:
    grouped: OrderedDict[str, list[PublishedArticle]] = OrderedDict()
    for article in sorted(issue.articles, key=lambda item: item.rank):
        grouped.setdefault(article.section or "未分类", []).append(article)
    return grouped


def render_backup_markdown(issue: PublishedIssue) -> str:
    grouped = _group_articles(issue)
    lines = [
        "<!-- Repository license: MIT -->",
        "<!-- Content license: CC BY-NC 4.0 -->",
        "",
        f"# {issue.title}",
        "",
        f"> 发布源：{issue.github_url}",
        f"> 报告日期：{issue.report_date}",
        f"> Issue 编号：#{issue.issue_number}",
        "",
    ]

    for section, articles in grouped.items():
        lines.extend([f"## {section}", ""])
        for article in articles:
            lines.extend(
                [
                    f"### [{article.title}]({article.url})",
                    article.rendered_summary or "待补充摘要",
                    article_metadata_comment(
                        article.article_id,
                        article.source_url or article.url,
                        article.dedupe_key,
                    ),
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"
