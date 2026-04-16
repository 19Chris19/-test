from __future__ import annotations

import os
import tomllib
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


class AppSettings(BaseModel):
    app_name: str = "AI 早报"
    environment: str = "development"
    timezone: str = "Asia/Shanghai"
    database_path: str = "data/ai_daily.db"
    github_repo: str = ""
    site_title: str = "AI 早报"
    site_base_url: str = ""
    llm_model: str = "Qwen2.5-72B-Instruct"
    llm_base_url: str = "https://api.edgefn.net/v1"
    draft_trigger_label: str = "trigger-draft"
    publish_label: str = "published"
    classify_score_threshold: float = 45.0
    fetch_timeout_seconds: int = 20

    @property
    def resolved_database_path(self) -> Path:
        env_override = os.getenv("AI_DAILY_DATABASE_PATH")
        raw_path = env_override or self.database_path
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path

    @property
    def resolved_github_repo(self) -> str:
        env_override = os.getenv("AI_DAILY_GITHUB_REPO") or os.getenv("GITHUB_REPOSITORY")
        return env_override or self.github_repo

    @property
    def resolved_site_base_url(self) -> str:
        env_override = os.getenv("AI_DAILY_SITE_BASE_URL")
        return env_override or self.site_base_url

    @property
    def resolved_llm_model(self) -> str:
        env_override = os.getenv("LLM_MODEL") or os.getenv("AI_DAILY_LLM_MODEL")
        return env_override or self.llm_model

    @property
    def resolved_llm_base_url(self) -> str:
        env_override = os.getenv("LLM_BASE_URL") or os.getenv("AI_DAILY_LLM_BASE_URL")
        return env_override or self.llm_base_url

    @property
    def resolved_llm_api_key(self) -> str:
        env_override = os.getenv("LLM_API_KEY") or os.getenv("AI_DAILY_LLM_API_KEY")
        return env_override or ""


class SourceDefinition(BaseModel):
    id: str
    name: str
    type: str
    url: str
    enabled: bool = True
    weight: float = 1.0
    fetch_interval_minutes: int = 60
    parser: str = "rss"


class CategoryDefinition(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)


def _load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_settings(path: Path | None = None) -> AppSettings:
    raw = _load_toml(path or CONFIG_DIR / "settings.toml")
    return AppSettings(**raw)


def load_sources(path: Path | None = None) -> list[SourceDefinition]:
    raw = _load_yaml(path or CONFIG_DIR / "sources.yaml")
    return [SourceDefinition(**item) for item in raw.get("sources", [])]


def load_categories(path: Path | None = None) -> list[CategoryDefinition]:
    raw = _load_yaml(path or CONFIG_DIR / "categories.yaml")
    return [CategoryDefinition(**item) for item in raw.get("categories", [])]


def load_prompt(name: str) -> str:
    prompt_path = CONFIG_DIR / "prompts" / name
    return prompt_path.read_text(encoding="utf-8").strip()
