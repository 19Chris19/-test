from __future__ import annotations

from pydantic import BaseModel


class SourceRecord(BaseModel):
    id: str
    name: str
    type: str
    url: str
    enabled: bool = True
    weight: float = 1.0
    fetch_interval_minutes: int = 60
    parser: str = "rss"

