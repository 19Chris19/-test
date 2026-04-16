from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ai_daily.models.publication import PublishedArticle, PublishedIssue


@dataclass(slots=True)
class CardIssueMeta:
    issue_id: int
    issue_number: int
    report_date: str
    title: str
    status: str
    markdown_path: str
    github_url: str
    published_at: str | None
    article_count: int
    backup_filename: str


@dataclass(slots=True)
class CardArticlePayload:
    article_id: int
    section: str
    rank: int
    title: str
    url: str
    rendered_summary: str
    source_url: str
    dedupe_key: str
    article_score: float


@dataclass(slots=True)
class CardSectionPayload:
    name: str
    articles: list[CardArticlePayload] = field(default_factory=list)


@dataclass(slots=True)
class CardRenderPayload:
    issue: CardIssueMeta
    sections: list[CardSectionPayload] = field(default_factory=list)
    featured_articles: list[CardArticlePayload] = field(default_factory=list)
    layout_hint: str = "poster"
    schema_version: str = field(default="card-render.v1", init=False)


def _article_payload(article: PublishedArticle) -> CardArticlePayload:
    rendered_summary = article.rendered_summary.strip() or "待补充摘要"
    return CardArticlePayload(
        article_id=article.article_id,
        section=article.section or "未分类",
        rank=article.rank,
        title=article.title,
        url=article.url,
        rendered_summary=rendered_summary,
        source_url=article.source_url or article.url,
        dedupe_key=article.dedupe_key,
        article_score=article.article_score,
    )


def _group_articles(issue: PublishedIssue) -> OrderedDict[str, list[CardArticlePayload]]:
    grouped: OrderedDict[str, list[CardArticlePayload]] = OrderedDict()
    for article in sorted(issue.articles, key=lambda item: item.rank):
        payload = _article_payload(article)
        grouped.setdefault(payload.section, []).append(payload)
    return grouped


def build_card_payload(
    issue: PublishedIssue,
    *,
    layout_hint: str = "poster",
) -> CardRenderPayload:
    grouped = _group_articles(issue)
    featured_articles = [
        _article_payload(article)
        for article in sorted(issue.articles, key=lambda item: item.rank)
    ][:3]
    sections = [
        CardSectionPayload(name=section_name, articles=articles)
        for section_name, articles in grouped.items()
    ]
    return CardRenderPayload(
        issue=CardIssueMeta(
            issue_id=issue.issue_id,
            issue_number=issue.issue_number,
            report_date=issue.report_date,
            title=issue.title,
            status=issue.status,
            markdown_path=issue.markdown_path,
            github_url=issue.github_url,
            published_at=issue.published_at,
            article_count=issue.article_count,
            backup_filename=issue.backup_filename,
        ),
        sections=sections,
        featured_articles=featured_articles,
        layout_hint=layout_hint,
    )


def card_payload_to_dict(payload: CardRenderPayload) -> dict[str, object]:
    return asdict(payload)


def card_payload_to_json(payload: CardRenderPayload) -> str:
    return json.dumps(card_payload_to_dict(payload), ensure_ascii=False, indent=2)


def write_card_payload(payload: CardRenderPayload, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(card_payload_to_json(payload) + "\n", encoding="utf-8")
    return output_path
