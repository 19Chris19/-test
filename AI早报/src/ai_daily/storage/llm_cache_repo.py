from __future__ import annotations

import json

from ai_daily.storage.db import Database


class LlmCacheRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(
        self, task_type: str, model: str, prompt_hash: str, input_hash: str
    ) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT response_json, status, error_message
                FROM llm_cache
                WHERE task_type = ? AND model = ? AND prompt_hash = ? AND input_hash = ?
                """,
                (task_type, model, prompt_hash, input_hash),
            ).fetchone()
            if row is None:
                return None
            payload = json.loads(row["response_json"])
            payload["status"] = row["status"]
            payload["error_message"] = row["error_message"]
            return payload

    def put(
        self,
        *,
        task_type: str,
        model: str,
        prompt_hash: str,
        input_hash: str,
        response_json: dict,
        status: str,
        error_message: str = "",
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO llm_cache (
                    task_type, model, prompt_hash, input_hash, response_json, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_type, model, prompt_hash, input_hash) DO UPDATE SET
                    response_json = excluded.response_json,
                    status = excluded.status,
                    error_message = excluded.error_message
                """,
                (
                    task_type,
                    model,
                    prompt_hash,
                    input_hash,
                    json.dumps(response_json, ensure_ascii=False),
                    status,
                    error_message,
                ),
            )

    def stats(self) -> dict:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM llm_cache
                GROUP BY status
                ORDER BY status
                """
            ).fetchall()
            return {row["status"]: row["total"] for row in rows}

