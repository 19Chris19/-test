from __future__ import annotations

import os

import httpx

from ai_daily.fetchers.base import BaseFetcher
from ai_daily.models.article import Article


class GitHubReleaseFetcher(BaseFetcher):
    def fetch(self) -> list[Article]:
        headers = {"User-Agent": "ai-daily/0.1"}
        token = os.getenv("AI_DAILY_GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = httpx.get(
            self.source.url,
            headers=headers,
            timeout=self.settings.fetch_timeout_seconds,
        )
        response.raise_for_status()
        releases = response.json()
        items: list[Article] = []
        for release in releases[: self.limit]:
            raw_text = self.clean_html(release.get("body") or "")
            article = self.build_article(
                title=release.get("name") or release.get("tag_name") or "Untitled Release",
                url=release.get("html_url", ""),
                author=(release.get("author") or {}).get("login", ""),
                raw_text=raw_text,
                published_at=release.get("published_at"),
                metadata_snapshot={
                    "tag_name": release.get("tag_name"),
                    "draft": bool(release.get("draft")),
                    "prerelease": bool(release.get("prerelease")),
                    "author_login": (release.get("author") or {}).get("login", ""),
                },
            )
            items.append(article)
        return items
