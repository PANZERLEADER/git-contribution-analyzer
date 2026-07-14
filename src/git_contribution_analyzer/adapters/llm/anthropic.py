from __future__ import annotations

from typing import Any

import httpx

from git_contribution_analyzer.adapters.llm.base import JsonHttpProvider
from git_contribution_analyzer.application.ports.llm import LlmTask


class AnthropicProvider(JsonHttpProvider):
    provider_id = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            transport=transport,
        )
        self._api_key = api_key

    def _request(self, task: LlmTask) -> dict[str, Any]:
        return {
            "url": f"{self.base_url}/v1/messages",
            "headers": {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            "json": {
                "model": self.model,
                "max_tokens": 4096,
                "system": task.system_prompt,
                "messages": [{"role": "user", "content": task.user_prompt}],
            },
        }

    def _health_request(self) -> dict[str, Any]:
        return {"url": self.base_url, "headers": {"x-api-key": self._api_key}}

    def _extract_text(self, payload: dict[str, Any]) -> str:
        return str(payload["content"][0]["text"])
