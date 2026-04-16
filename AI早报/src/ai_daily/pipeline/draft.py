from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_daily.config import PROJECT_ROOT, AppSettings, CategoryDefinition
from ai_daily.models.article import Article
from ai_daily.render.markdown import render_article_block
from ai_daily.storage.article_repo import ArticleRepository


@dataclass
class DraftPlan:
    report_date: str
    output_path: Path
    total_articles: int
    per_section_limit: int
    max_total: int
    sections: dict[str, list[Article]]


def default_report_date(settings: AppSettings) -> str:
    return datetime.now(ZoneInfo(settings.timezone)).date().isoformat()


def select_articles_for_draft(
    articles: list[Article],
    *,
    categories: list[CategoryDefinition],
    per_section_limit: int = 3,
    max_total: int = 15,
) -> OrderedDict[str, list[Article]]:
    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(article.category or "未分类", []).append(article)

    ordered = OrderedDict()
    total = 0
    seen_sections: set[str] = set()

    def take_section(section_name: str) -> None:
        nonlocal total
        if section_name not in grouped or total >= max_total:
            return
        items = sorted(grouped[section_name], key=lambda item: (-item.score, item.title))
        selected_items = items[: max(0, min(per_section_limit, max_total - total))]
        if selected_items:
            ordered[section_name] = selected_items
            total += len(selected_items)
            seen_sections.add(section_name)

    for category in categories:
        take_section(category.name)

    for section_name in sorted(grouped):
        if section_name not in seen_sections:
            take_section(section_name)

    return ordered


def build_draft(report_date: str, grouped_articles: dict[str, list[Article]]) -> str:
    lines = [f"# AI 早报 {report_date}", "", "## 概览", ""]
    total = sum(len(items) for items in grouped_articles.values())
    lines.append(f"- 共选入 {total} 条")
    for section, items in grouped_articles.items():
        lines.append(f"- {section}：{len(items)} 条")
    lines.extend(["", "---", ""])
    for section, items in grouped_articles.items():
        lines.append(f"## {section}")
        lines.append("")
        for item in items:
            lines.append(render_article_block(item, rendered_summary(item)))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def rendered_summary(article: Article, max_chars: int = 160) -> str:
    text = (article.summary or article.raw_text or "").strip()
    if not text:
        return "待补充摘要"
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def build_draft_plan(
    repo: ArticleRepository,
    *,
    settings: AppSettings,
    categories: list[CategoryDefinition],
    report_date: str | None = None,
    per_section_limit: int = 3,
    max_total: int = 15,
) -> DraftPlan:
    final_date = report_date or default_report_date(settings)
    selected = repo.list_draft_candidates()
    sections = select_articles_for_draft(
        selected,
        categories=categories,
        per_section_limit=per_section_limit,
        max_total=max_total,
    )
    output_path = PROJECT_ROOT / "data" / "staging" / f"draft_{final_date}.md"
    return DraftPlan(
        report_date=final_date,
        output_path=output_path,
        total_articles=sum(len(items) for items in sections.values()),
        per_section_limit=per_section_limit,
        max_total=max_total,
        sections=dict(sections),
    )


def write_draft(plan: DraftPlan) -> str:
    content = build_draft(plan.report_date, plan.sections)
    plan.output_path.parent.mkdir(parents=True, exist_ok=True)
    plan.output_path.write_text(content, encoding="utf-8")
    return content
