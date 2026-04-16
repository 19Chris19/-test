from __future__ import annotations

from ai_daily.models.source import SourceRecord
from ai_daily.storage.db import Database


class SourceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_many(self, sources: list[SourceRecord]) -> int:
        with self.database.connect() as connection:
            for item in sources:
                payload = item.model_dump()
                connection.execute(
                    """
                    INSERT INTO sources (
                        id, name, type, url, enabled, weight, fetch_interval_minutes, parser
                    ) VALUES (
                        :id, :name, :type, :url, :enabled, :weight, :fetch_interval_minutes, :parser
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        type = excluded.type,
                        url = excluded.url,
                        enabled = excluded.enabled,
                        weight = excluded.weight,
                        fetch_interval_minutes = excluded.fetch_interval_minutes,
                        parser = excluded.parser,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    payload,
                )
        return len(sources)

    def list_all(self) -> list[SourceRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, type, url, enabled, weight, fetch_interval_minutes, parser
                FROM sources
                ORDER BY id
                """
            ).fetchall()
            return [
                SourceRecord(
                    id=row["id"],
                    name=row["name"],
                    type=row["type"],
                    url=row["url"],
                    enabled=bool(row["enabled"]),
                    weight=row["weight"],
                    fetch_interval_minutes=row["fetch_interval_minutes"],
                    parser=row["parser"],
                )
                for row in rows
            ]

    def list_enabled(self, source_type: str | None = None) -> list[SourceRecord]:
        query = """
            SELECT id, name, type, url, enabled, weight, fetch_interval_minutes, parser
            FROM sources
            WHERE enabled = 1
        """
        params: tuple = ()
        if source_type and source_type != "all":
            query += " AND type = ?"
            params = (source_type,)
        query += " ORDER BY id"
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            SourceRecord(
                id=row["id"],
                name=row["name"],
                type=row["type"],
                url=row["url"],
                enabled=bool(row["enabled"]),
                weight=row["weight"],
                fetch_interval_minutes=row["fetch_interval_minutes"],
                parser=row["parser"],
            )
            for row in rows
        ]
