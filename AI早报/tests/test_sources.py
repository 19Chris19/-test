from __future__ import annotations

from ai_daily.config import load_sources
from ai_daily.storage.db import Database
from ai_daily.storage.source_repo import SourceRepository


def test_seed_sources_roundtrip(tmp_path) -> None:
    database = Database(tmp_path / "ai_daily.db")
    database.initialize()

    repo = SourceRepository(database)
    sources = load_sources()
    repo.upsert_many(sources)
    stored = repo.list_all()

    assert len(stored) == len(sources)
    assert stored[0].id == sources[0].id

