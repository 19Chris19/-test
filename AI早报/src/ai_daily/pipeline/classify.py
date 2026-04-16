from __future__ import annotations

from ai_daily.config import CategoryDefinition, load_prompt
from ai_daily.llm.client import LlmClient
from ai_daily.models.article import Article
from ai_daily.storage.article_repo import ArticleRepository


def classify_with_rules(text: str, categories: list[CategoryDefinition]) -> str:
    lowered = text.lower()
    best_name = "行业动态"
    best_hits = 0
    for category in categories:
        hits = sum(1 for keyword in category.keywords if keyword.lower() in lowered)
        if hits > best_hits:
            best_name = category.name
            best_hits = hits
    return best_name


def run_classify(
    repo: ArticleRepository,
    *,
    categories: list[CategoryDefinition],
    llm_client: LlmClient,
    threshold: float,
) -> dict[str, int]:
    prompt = load_prompt("classify.txt")
    stats = {"selected": 0, "filtered": 0, "degraded": 0}
    articles = repo.list_by_status(statuses=["new"], min_score=0)

    for article in articles:
        if article.score <= threshold:
            repo.update_classification(article.id or 0, category="", status="filtered")
            stats["filtered"] += 1
            continue

        rule_category = classify_with_rules(_article_text(article), categories)
        if _has_rule_hit(article, categories):
            repo.update_classification(article.id or 0, category=rule_category, status="selected")
            stats["selected"] += 1
            continue

        llm_result = llm_client.complete(
            task_type="classify",
            prompt=prompt,
            input_text=_article_text(article),
        )
        category = _normalize_category(llm_result.output_text, categories)
        status = "selected" if llm_result.status == "success" else "degraded"
        repo.update_classification(article.id or 0, category=category, status=status)
        stats[status] += 1

    return stats


def _article_text(article: Article) -> str:
    return "\n".join(part for part in [article.title, article.raw_text] if part).strip()


def _has_rule_hit(article: Article, categories: list[CategoryDefinition]) -> bool:
    lowered = _article_text(article).lower()
    return any(any(keyword.lower() in lowered for keyword in cat.keywords) for cat in categories)


def _normalize_category(value: str, categories: list[CategoryDefinition]) -> str:
    allowed = {category.name for category in categories}
    return value if value in allowed else "行业动态"
