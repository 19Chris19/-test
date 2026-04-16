from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from ai_daily.config import load_categories, load_settings, load_sources
from ai_daily.fetchers.factory import create_fetcher
from ai_daily.llm.client import LlmClient
from ai_daily.pipeline.assets import AssetResult, generate_assets
from ai_daily.pipeline.classify import run_classify
from ai_daily.pipeline.dedupe import run_dedupe
from ai_daily.pipeline.draft import build_draft_plan, write_draft
from ai_daily.pipeline.ingest import run_ingest
from ai_daily.pipeline.publish import publish_draft
from ai_daily.pipeline.score import run_score
from ai_daily.storage.article_repo import ArticleRepository
from ai_daily.storage.db import Database
from ai_daily.storage.llm_cache_repo import LlmCacheRepository
from ai_daily.storage.source_repo import SourceRepository

app = typer.Typer(help="AI 早报项目 CLI")


def _database(db_path: str | None = None) -> Database:
    settings = load_settings()
    return Database(Path(db_path) if db_path else settings.resolved_database_path)


def _asset_result_payload(result: AssetResult) -> dict[str, object]:
    payload = asdict(result)
    paths = payload["paths"]
    paths["readme_path"] = str(paths["readme_path"])
    paths["rss_path"] = str(paths["rss_path"])
    paths["site_index_path"] = str(paths["site_index_path"])
    paths["site_css_path"] = str(paths["site_css_path"])
    paths["nojekyll_path"] = str(paths["nojekyll_path"])
    paths["backup_paths"] = [str(path) for path in paths["backup_paths"]]
    return payload


@app.command("show-config")
def show_config() -> None:
    settings = load_settings()
    typer.echo(json.dumps(settings.model_dump(), ensure_ascii=False, indent=2))
    typer.echo(f"resolved_database_path={settings.resolved_database_path}")
    typer.echo(f"resolved_github_repo={settings.resolved_github_repo}")
    typer.echo(f"resolved_site_base_url={settings.resolved_site_base_url}")
    typer.echo(f"resolved_llm_model={settings.resolved_llm_model}")
    typer.echo(f"resolved_llm_base_url={settings.resolved_llm_base_url}")
    typer.echo(f"llm_api_key_present={'yes' if settings.resolved_llm_api_key else 'no'}")


@app.command("init-db")
def init_db(
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    typer.echo(f"Initialized database at {database.path}")


@app.command("seed-sources")
def seed_sources(
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    repo = SourceRepository(database)
    count = repo.upsert_many(load_sources())
    typer.echo(f"Seeded {count} sources into {database.path}")


@app.command("list-sources")
def list_sources(
    from_db: bool = typer.Option(False, "--from-db", help="Read sources from SQLite"),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    if from_db:
        database = _database(db_path)
        database.initialize()
        repo = SourceRepository(database)
        sources = [item.model_dump() for item in repo.list_all()]
    else:
        sources = [item.model_dump() for item in load_sources()]
    typer.echo(json.dumps(sources, ensure_ascii=False, indent=2))


@app.command("db-status")
def db_status(
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    status = database.inspect()
    typer.echo(json.dumps(status, ensure_ascii=False, indent=2))


@app.command("llm-cache-stats")
def llm_cache_stats(
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    repo = LlmCacheRepository(database)
    typer.echo(json.dumps(repo.stats(), ensure_ascii=False, indent=2))


@app.command("llm-smoke")
def llm_smoke(
    prompt: str = typer.Argument(..., help="Prompt text"),
    text: str = typer.Argument(..., help="Input text"),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    client = LlmClient(database=database)
    result = client.complete(task_type="summary", prompt=prompt, input_text=text)
    typer.echo(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


@app.command("fetch")
def fetch(
    source_type: str = typer.Option("all", help="Filter by source type, e.g. arxiv"),
    limit: int | None = typer.Option(default=None, help="Global max articles to ingest"),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    source_repo = SourceRepository(database)
    article_repo = ArticleRepository(database)
    sources = source_repo.list_enabled(source_type=source_type)

    remaining = limit
    summary: list[dict] = []
    for source in sources:
        fetch_limit = remaining if remaining is not None else None
        fetcher = create_fetcher(source, limit=fetch_limit)
        count = run_ingest(fetcher, article_repo)
        summary.append({"source_id": source.id, "type": source.type, "ingested": count})
        if remaining is not None:
            remaining = max(0, remaining - count)
            if remaining == 0:
                break

    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("dedupe")
def dedupe(db_path: str | None = typer.Option(default=None, help="Override database path")) -> None:
    database = _database(db_path)
    database.initialize()
    repo = ArticleRepository(database)
    result = run_dedupe(repo)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("score")
def score(
    dry_run: bool = typer.Option(False, "--dry-run", help="Compute without updating DB"),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    repo = ArticleRepository(database)
    result = run_score(repo, dry_run=dry_run)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("classify")
def classify(
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    settings = load_settings()
    repo = ArticleRepository(database)
    client = LlmClient(database=database)
    result = run_classify(
        repo,
        categories=load_categories(),
        llm_client=client,
        threshold=settings.classify_score_threshold,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    typer.echo(json.dumps(repo.count_by_status(), ensure_ascii=False, indent=2))


@app.command("draft")
def draft(
    report_date: str | None = typer.Option(
        None,
        "--date",
        help="Draft date in YYYY-MM-DD",
    ),
    per_section_limit: int = typer.Option(3, help="Max items per section"),
    max_total: int = typer.Option(15, help="Max total items in the draft"),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    settings = load_settings()
    repo = ArticleRepository(database)
    plan = build_draft_plan(
        repo,
        settings=settings,
        categories=load_categories(),
        report_date=report_date,
        per_section_limit=per_section_limit,
        max_total=max_total,
    )
    content = write_draft(plan)
    typer.echo(
        json.dumps(
            {
                "report_date": plan.report_date,
                "output_path": str(plan.output_path),
                "total_articles": plan.total_articles,
                "sections": {name: len(items) for name, items in plan.sections.items()},
                "bytes": len(content.encode("utf-8")),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("publish")
def publish(
    report_date: str | None = typer.Option(
        None,
        "--date",
        help="Publish date in YYYY-MM-DD",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse and validate only"),
    repo_slug: str | None = typer.Option(
        None,
        "--repo",
        help="Override GitHub repository slug, e.g. owner/repo",
    ),
    draft_path: str | None = typer.Option(
        None,
        "--draft-path",
        help="Override draft markdown path",
    ),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    result = publish_draft(
        database,
        report_date=report_date,
        draft_path=Path(draft_path) if draft_path else None,
        repo_slug=repo_slug,
        dry_run=dry_run,
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("rebuild")
def rebuild(
    issue_number: int = typer.Option(..., "--issue-number", help="Published issue number"),
    root: Path | None = typer.Option(default=None, help="Override project root"),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    result, _ = generate_assets(
        database,
        root=root,
        issue_number=issue_number,
        rebuild_all_backups=False,
    )
    typer.echo(json.dumps(_asset_result_payload(result), ensure_ascii=False, indent=2))


@app.command("generate-assets")
def generate_assets_command(
    root: Path | None = typer.Option(default=None, help="Override project root"),
    db_path: str | None = typer.Option(default=None, help="Override database path"),
) -> None:
    database = _database(db_path)
    database.initialize()
    result, _ = generate_assets(database, root=root, rebuild_all_backups=True)
    typer.echo(json.dumps(_asset_result_payload(result), ensure_ascii=False, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
