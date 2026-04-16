from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from ai_daily.models.article import Article
from ai_daily.models.issue import IssueRecord
from ai_daily.pipeline.draft import rendered_summary
from ai_daily.storage.db import Database


@dataclass(slots=True)
class PublishTransactionResult:
    issue_id: int
    article_ids: list[int]
    archived_count: int


class IssueRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, issue: IssueRecord) -> int:
        payload = issue.model_dump(exclude={"id"})
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO issues (
                    issue_number,
                    report_date,
                    title,
                    status,
                    markdown_path,
                    github_url,
                    published_at
                ) VALUES (
                    :issue_number,
                    :report_date,
                    :title,
                    :status,
                    :markdown_path,
                    :github_url,
                    :published_at
                )
                """,
                payload,
            )
            return int(cursor.lastrowid)

    def list_published(self) -> list[IssueRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, issue_number, report_date, title, status, markdown_path,
                       github_url, published_at
                FROM issues
                WHERE status = 'published'
                ORDER BY COALESCE(published_at, created_at) DESC, issue_number DESC, id DESC
                """
            ).fetchall()
        return [
            IssueRecord(
                id=row["id"],
                issue_number=row["issue_number"],
                report_date=row["report_date"],
                title=row["title"],
                status=row["status"],
                markdown_path=row["markdown_path"],
                github_url=row["github_url"],
                published_at=row["published_at"],
            )
            for row in rows
        ]

    def get_published_by_number(self, issue_number: int) -> IssueRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, issue_number, report_date, title, status, markdown_path,
                       github_url, published_at
                FROM issues
                WHERE issue_number = ? AND status = 'published'
                LIMIT 1
                """,
                (issue_number,),
            ).fetchone()
        if row is None:
            return None
        return IssueRecord(
            id=row["id"],
            issue_number=row["issue_number"],
            report_date=row["report_date"],
            title=row["title"],
            status=row["status"],
            markdown_path=row["markdown_path"],
            github_url=row["github_url"],
            published_at=row["published_at"],
        )


def _normalize_article_ids(article_ids: list[int]) -> list[int]:
    seen: set[int] = set()
    normalized: list[int] = []
    for article_id in article_ids:
        if article_id in seen:
            continue
        seen.add(article_id)
        normalized.append(article_id)
    return normalized


def _article_from_row(row: sqlite3.Row) -> Article:
    return Article(
        id=row["id"],
        source_id=row["source_id"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        author=row["author"],
        title=row["title"],
        url=row["url"],
        canonical_url=row["canonical_url"],
        published_at=row["published_at"],
        fetched_at=row["fetched_at"],
        raw_text=row["raw_text"],
        summary=row["summary"],
        category=row["category"],
        score=row["score"],
        dedupe_key=row["dedupe_key"],
        metadata_snapshot=json.loads(row["metadata_snapshot"] or "{}"),
        status=row["status"],
    )


def finalize_publish_transaction(
    db_conn: sqlite3.Connection,
    report_date: str,
    title: str,
    github_url: str,
    issue_number: int,
    article_ids: list[int],
    *,
    markdown_path: str = "",
) -> PublishTransactionResult:
    normalized_ids = _normalize_article_ids(article_ids)
    if not normalized_ids:
        raise ValueError("Cannot publish an issue without article ids")

    placeholders = ", ".join("?" for _ in normalized_ids)
    rows = db_conn.execute(
        f"""
        SELECT id, source_id, source_name, source_type, author, title, url, canonical_url,
               published_at, fetched_at, raw_text, summary, category, score,
               dedupe_key, metadata_snapshot, status
        FROM articles
        WHERE id IN ({placeholders})
        """,
        tuple(normalized_ids),
    ).fetchall()
    article_map = {int(row["id"]): row for row in rows}
    missing_ids = [article_id for article_id in normalized_ids if article_id not in article_map]
    if missing_ids:
        raise ValueError(f"Missing article ids in publish transaction: {missing_ids}")

    selected_rows = [article_map[article_id] for article_id in normalized_ids]
    for row in selected_rows:
        if row["status"] != "selected":
            raise ValueError(
                f"Article {row['id']} is not selectable for publish: status={row['status']}"
            )

    published_at = datetime.now(UTC).isoformat(timespec="seconds")

    with db_conn:
        cursor = db_conn.execute(
            """
            INSERT INTO issues (
                issue_number,
                report_date,
                title,
                status,
                markdown_path,
                github_url,
                published_at
            ) VALUES (?, ?, ?, 'published', ?, ?, ?)
            """,
            (issue_number, report_date, title, markdown_path, github_url, published_at),
        )
        issue_internal_id = int(cursor.lastrowid)

        mapping_rows = []
        for rank, row in enumerate(selected_rows, start=1):
            article = _article_from_row(row)
            mapping_rows.append(
                (
                    issue_internal_id,
                    article.id or 0,
                    article.category or "未分类",
                    rank,
                    article.title,
                    article.url,
                    article.score,
                    rendered_summary(article),
                )
            )

        db_conn.executemany(
            """
            INSERT INTO issue_articles (
                issue_id, article_id, section, rank, title_snapshot,
                source_url_snapshot, article_score_snapshot, rendered_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(issue_id, article_id) DO UPDATE SET
                section = excluded.section,
                rank = excluded.rank,
                title_snapshot = excluded.title_snapshot,
                source_url_snapshot = excluded.source_url_snapshot,
                article_score_snapshot = excluded.article_score_snapshot,
                rendered_summary = excluded.rendered_summary
            """,
            mapping_rows,
        )

        db_conn.execute(
            f"""
            UPDATE articles
            SET status = 'published', updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
            """,
            tuple(normalized_ids),
        )
        archived_count = db_conn.execute(
            """
            UPDATE articles
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'selected'
            """
        ).rowcount

    return PublishTransactionResult(
        issue_id=issue_internal_id,
        article_ids=normalized_ids,
        archived_count=archived_count,
    )
