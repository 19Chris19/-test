from __future__ import annotations

import sqlite3

from ai_daily.storage.db import Database


def test_init_db_creates_expected_tables(tmp_path) -> None:
    db_path = tmp_path / "ai_daily.db"
    database = Database(db_path)
    database.initialize()

    connection = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert {"articles", "issues", "sources", "issue_articles", "llm_cache"} <= tables


def test_articles_table_contains_author_column(tmp_path) -> None:
    db_path = tmp_path / "ai_daily.db"
    database = Database(db_path)
    database.initialize()

    connection = sqlite3.connect(db_path)
    try:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(articles)").fetchall()
        }
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()

    assert "author" in columns
    assert version == 3
