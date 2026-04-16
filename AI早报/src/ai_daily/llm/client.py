from __future__ import annotations

import random
import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel

from ai_daily.config import load_settings
from ai_daily.storage.db import Database
from ai_daily.storage.llm_cache_repo import LlmCacheRepository
from ai_daily.utils.hashes import sha256_text


class LlmResult(BaseModel):
    task_type: str
    model: str
    output_text: str
    status: str
    cached: bool = False
    error_message: str = ""


@dataclass
class LlmClient:
    database: Database

    def __post_init__(self) -> None:
        self.settings = load_settings()
        self.cache_repo = LlmCacheRepository(self.database)

    def complete(self, *, task_type: str, prompt: str, input_text: str) -> LlmResult:
        model = self.settings.resolved_llm_model
        prompt_hash = sha256_text(prompt)
        input_hash = sha256_text(input_text)
        cached = self.cache_repo.get(task_type, model, prompt_hash, input_hash)
        if cached:
            return LlmResult(
                task_type=task_type,
                model=model,
                output_text=cached["output_text"],
                status=cached["status"],
                cached=True,
                error_message=cached.get("error_message", ""),
            )

        result = self._attempt_remote(task_type=task_type, prompt=prompt, input_text=input_text)
        self.cache_repo.put(
            task_type=task_type,
            model=model,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            response_json={"output_text": result.output_text},
            status=result.status,
            error_message=result.error_message,
        )
        return result

    def _attempt_remote(self, *, task_type: str, prompt: str, input_text: str) -> LlmResult:
        api_key = self.settings.resolved_llm_api_key
        base_url = self.settings.resolved_llm_base_url.rstrip("/")
        model = self.settings.resolved_llm_model
        max_attempts = 3

        if not api_key or not base_url:
            return self._degraded_result(task_type=task_type, input_text=input_text)

        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": input_text},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        last_error = "unknown llm error"
        for attempt in range(max_attempts):
            try:
                response = httpx.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.fetch_timeout_seconds,
                )
                if 200 <= response.status_code < 300:
                    output_text = self._extract_output_text(response.json())
                    if output_text:
                        return LlmResult(
                            task_type=task_type,
                            model=model,
                            output_text=output_text,
                            status="success",
                        )
                    last_error = "Empty LLM response"
                else:
                    last_error = f"{response.status_code}: {getattr(response, 'text', '')[:200]}"
                    if response.status_code in {429, 500, 502, 503, 504}:
                        if attempt < max_attempts - 1:
                            self._sleep_with_backoff(attempt)
                            continue
                    degraded = self._degraded_result(task_type=task_type, input_text=input_text)
                    degraded.error_message = last_error
                    return degraded
            except httpx.HTTPError as exc:
                last_error = str(exc)
                if attempt < max_attempts - 1:
                    self._sleep_with_backoff(attempt)
                    continue

        degraded = self._degraded_result(task_type=task_type, input_text=input_text)
        degraded.error_message = last_error
        return degraded

    @staticmethod
    def _sleep_with_backoff(attempt: int) -> None:
        backoff_seconds = (2**attempt) + random.uniform(0, 0.25)
        time.sleep(backoff_seconds)

    @staticmethod
    def _extract_output_text(response_json: dict) -> str:
        choices = response_json.get("choices") or []
        if choices:
            first_choice = choices[0] or {}
            message = first_choice.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                return "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                ).strip()
            text = first_choice.get("text")
            if isinstance(text, str):
                return text.strip()
        output_text = response_json.get("output_text")
        if isinstance(output_text, str):
            return output_text.strip()
        return ""

    def _degraded_result(self, *, task_type: str, input_text: str) -> LlmResult:
        text = " ".join(input_text.split())
        if task_type == "classify":
            output_text = "行业动态"
        else:
            output_text = text[:140]
        return LlmResult(
            task_type=task_type,
            model=self.settings.llm_model,
            output_text=output_text,
            status="degraded",
        )
