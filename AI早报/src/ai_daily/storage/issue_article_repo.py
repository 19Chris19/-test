from __future__ import annotations

from ai_daily.models.issue import IssueArticleLink
from ai_daily.storage.db import Database


class IssueArticleRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def link(self, item: IssueArticleLink) -> None:
        payload = item.model_dump()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO issue_articles (
                    issue_id, article_id, section, rank, title_snapshot,
                    source_url_snapshot, article_score_snapshot, rendered_summary
                ) VALUES (
                    :issue_id, :article_id, :section, :rank, :title_snapshot,
                    :source_url_snapshot, :article_score_snapshot, :rendered_summary
                )
                ON CONFLICT(issue_id, article_id) DO UPDATE SET
                    section = excluded.section,
                    rank = excluded.rank,
                    title_snapshot = excluded.title_snapshot,
                    source_url_snapshot = excluded.source_url_snapshot,
                    article_score_snapshot = excluded.article_score_snapshot,
                    rendered_summary = excluded.rendered_summary
                """,
                payload,
            )

