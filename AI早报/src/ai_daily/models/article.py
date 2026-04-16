from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Article(BaseModel):
    id: int | None = None
    source_id: str = ""
    source_name: str
    source_type: str
    author: str = ""
    title: str
    url: str
    canonical_url: str
    published_at: str | None = None
    fetched_at: str | None = None
    raw_text: str = ""
    summary: str = ""
    category: str = ""
    score: float = 0.0
    dedupe_key: str
    metadata_snapshot: dict[str, Any] = Field(default_factory=dict)
    status: str = "new"
