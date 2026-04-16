from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from ai_daily.models.article import Article


class SourceAdapter(ABC):
    @abstractmethod
    def normalize(self, payload: Any) -> Article:
        raise NotImplementedError


def coerce_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(UTC).replace(microsecond=0).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(
                microsecond=0
            ).isoformat()
        except ValueError:
            return None
