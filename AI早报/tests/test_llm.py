from __future__ import annotations

from types import SimpleNamespace

from ai_daily.llm.client import LlmClient
from ai_daily.storage.db import Database


def test_llm_client_degrades_and_caches(tmp_path) -> None:
    database = Database(tmp_path / "ai_daily.db")
    database.initialize()
    client = LlmClient(database=database)

    result = client.complete(task_type="summary", prompt="summarize", input_text="hello world")
    cached = client.complete(task_type="summary", prompt="summarize", input_text="hello world")

    assert result.status == "degraded"
    assert cached.cached is True


def test_llm_client_uses_edgefn_env_and_caches_success(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "ai_daily.db")
    database.initialize()

    captured: dict[str, object] = {}

    def fake_post(url, headers, json, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "行业动态"}}]},
        )

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.edgefn.net/v1")
    monkeypatch.setattr("ai_daily.llm.client.httpx.post", fake_post)

    client = LlmClient(database=database)

    result = client.complete(task_type="classify", prompt="classify", input_text="hello world")

    assert result.status == "success"
    assert result.output_text == "行业动态"
    assert captured["url"] == "https://api.edgefn.net/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "Qwen2.5-72B-Instruct"
    assert result.cached is False
