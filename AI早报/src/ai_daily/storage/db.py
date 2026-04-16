from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ai_daily.storage.migrations import SCHEMA_VERSION, apply_migrations


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            apply_migrations(connection)

    @contextmanager
    def connect(self) -> sqlite3.Connection:
        connection = _connect(self.path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def inspect(self) -> dict:
        with self.connect() as connection:
            tables = [
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                )
            ]
            return {
                "path": str(self.path),
                "schema_version": connection.execute("PRAGMA user_version").fetchone()[0],
                "expected_schema_version": SCHEMA_VERSION,
                "tables": tables,
            }

