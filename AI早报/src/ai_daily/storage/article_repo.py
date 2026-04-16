from __future__ import annotations

import json

from ai_daily.models.article import Article
from ai_daily.storage.db import Database


class ArticleRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, article: Article) -> int:
        payload = article.model_dump(exclude={"id"})
        payload["metadata_snapshot"] = json.dumps(payload["metadata_snapshot"], ensure_ascii=False)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO articles (
                    source_id, source_name, source_type, author, title, url, canonical_url,
                    published_at, fetched_at, raw_text, summary, category, score,
                    dedupe_key, metadata_snapshot, status
                ) VALUES (
                    :source_id, :source_name, :source_type, :author, :title, :url, :canonical_url,
                    :published_at, :fetched_at, :raw_text, :summary, :category, :score,
                    :dedupe_key, :metadata_snapshot, :status
                )
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    author = excluded.author,
                    title = excluded.title,
                    url = excluded.url,
                    canonical_url = excluded.canonical_url,
                    raw_text = excluded.raw_text,
                    summary = excluded.summary,
                    category = excluded.category,
                    score = excluded.score,
                    metadata_snapshot = excluded.metadata_snapshot,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                payload,
            )
            row = connection.execute(
                "SELECT id FROM articles WHERE dedupe_key = ?", (article.dedupe_key,)
            ).fetchone()
            return int(row["id"])

    def list_by_status(
        self,
        *,
        statuses: list[str],
        limit: int | None = None,
        source_type: str | None = None,
        min_score: float | None = None,
    ) -> list[Article]:
        query = """
            SELECT id, source_id, source_name, source_type, author, title, url, canonical_url,
                   published_at, fetched_at, raw_text, summary, category, score,
                   dedupe_key, metadata_snapshot, status
            FROM articles
            WHERE status IN ({placeholders})
        """.format(placeholders=", ".join("?" for _ in statuses))
        params: list = list(statuses)
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)
        if min_score is not None:
            query += " AND score > ?"
            params.append(min_score)
        query += " ORDER BY COALESCE(published_at, fetched_at, created_at) DESC, id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._row_to_article(row) for row in rows]

    def update_status(self, article_id: int, status: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE articles SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, article_id),
            )

    def update_after_dedupe(self, article_id: int, *, canonical_url: str, status: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE articles
                SET canonical_url = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (canonical_url, status, article_id),
            )

    def update_score(self, article_id: int, score: float) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE articles SET score = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (score, article_id),
            )

    def update_classification(self, article_id: int, *, category: str, status: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE articles
                SET category = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (category, status, article_id),
            )

    def count_by_status(self) -> dict[str, int]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM articles
                GROUP BY status
                ORDER BY status
                """
            ).fetchall()
        return {row["status"]: row["total"] for row in rows}

    def list_draft_candidates(self) -> list[Article]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, source_id, source_name, source_type, author, title, url, canonical_url,
                       published_at, fetched_at, raw_text, summary, category, score,
                       dedupe_key, metadata_snapshot, status
                FROM articles
                WHERE status = 'selected'
                ORDER BY category ASC, score DESC, COALESCE(published_at, fetched_at) DESC, id DESC
                """
            ).fetchall()
        return [self._row_to_article(row) for row in rows]

    @staticmethod
    def _row_to_article(row) -> Article:
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
