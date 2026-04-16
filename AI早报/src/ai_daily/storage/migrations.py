from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3


def _apply_v1(connection: sqlite3.Connection) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL DEFAULT '',
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            published_at TEXT,
            fetched_at TEXT,
            raw_text TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0,
            dedupe_key TEXT NOT NULL,
            metadata_snapshot TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'new'
                CHECK(
                    status IN (
                        'new',
                        'filtered',
                        'selected',
                        'published',
                        'degraded',
                        'archived'
                    )
                ),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_number INTEGER,
            report_date TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft', 'published')),
            markdown_path TEXT NOT NULL DEFAULT '',
            github_url TEXT NOT NULL DEFAULT '',
            published_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            url TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            weight REAL NOT NULL DEFAULT 1,
            fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,
            parser TEXT NOT NULL DEFAULT 'rss',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS issue_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            section TEXT NOT NULL,
            rank INTEGER NOT NULL,
            title_snapshot TEXT NOT NULL,
            source_url_snapshot TEXT NOT NULL,
            article_score_snapshot REAL NOT NULL DEFAULT 0,
            rendered_summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(issue_id) REFERENCES issues(id) ON DELETE CASCADE,
            FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS llm_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('success', 'degraded', 'failed')),
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_dedupe_key ON articles(dedupe_key);",
        "CREATE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles(canonical_url);",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_issue_articles_unique
        ON issue_articles(issue_id, article_id);
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_cache_lookup
        ON llm_cache(task_type, model, prompt_hash, input_hash);
        """,
    ]
    for statement in statements:
        connection.execute(statement)


def _apply_v2(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(articles)").fetchall()
    }
    if "author" not in existing_columns:
        try:
            connection.execute("ALTER TABLE articles ADD COLUMN author TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise


def _apply_v3(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'articles'"
    ).fetchone()
    current_sql = (row[0] if row else "").lower()
    if "archived" in current_sql:
        return

    connection.execute("PRAGMA foreign_keys = OFF;")
    try:
        connection.execute("ALTER TABLE articles RENAME TO articles_v3_backup;")
        connection.execute(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                published_at TEXT,
                fetched_at TEXT,
                raw_text TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                score REAL NOT NULL DEFAULT 0,
                dedupe_key TEXT NOT NULL,
                metadata_snapshot TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK(
                        status IN (
                            'new',
                            'filtered',
                            'selected',
                            'published',
                            'degraded',
                            'archived'
                        )
                    ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.execute(
            """
            INSERT INTO articles (
                id, source_id, source_name, source_type, author, title, url, canonical_url,
                published_at, fetched_at, raw_text, summary, category, score, dedupe_key,
                metadata_snapshot, status, created_at, updated_at
            )
            SELECT
                id, source_id, source_name, source_type, author, title, url, canonical_url,
                published_at, fetched_at, raw_text, summary, category, score, dedupe_key,
                metadata_snapshot, status, created_at, updated_at
            FROM articles_v3_backup;
            """
        )
        connection.execute("DROP TABLE articles_v3_backup;")
        sequence_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
        ).fetchone()
        if sequence_exists:
            connection.execute("DELETE FROM sqlite_sequence WHERE name = 'articles';")
            connection.execute(
                """
                INSERT INTO sqlite_sequence(name, seq)
                SELECT 'articles', COALESCE(MAX(id), 0)
                FROM articles;
                """
            )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_dedupe_key ON articles(dedupe_key);"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles(canonical_url);"
        )
    finally:
        connection.execute("PRAGMA foreign_keys = ON;")


def apply_migrations(connection: sqlite3.Connection) -> None:
    current_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if current_version < 1:
        _apply_v1(connection)
        connection.execute("PRAGMA user_version = 1")
        current_version = 1
    if current_version < 2:
        _apply_v2(connection)
        connection.execute("PRAGMA user_version = 2")
        current_version = 2
    if current_version < 3:
        _apply_v3(connection)
        connection.execute("PRAGMA user_version = 3")
