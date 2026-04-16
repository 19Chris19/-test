from __future__ import annotations

from ai_daily.llm.client import LlmClient


def summarize_text(client: LlmClient, prompt: str, text: str) -> str:
    return client.complete(task_type="summary", prompt=prompt, input_text=text).output_text

