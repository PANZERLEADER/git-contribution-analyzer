from __future__ import annotations

from typing import Any

import httpx

from git_contribution_analyzer.adapters.llm.base import JsonHttpProvider
from git_contribution_analyzer.application.ports.llm import LlmTask


class OpenAiCompatibleProvider(JsonHttpProvider):
    provider_id = "openai-compatible"

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
            "url": f"{self.base_url}/chat/completions",
            "headers": {"Authorization": f"Bearer {self._api_key}"},
            "json": {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": task.system_prompt},
                    {"role": "user", "content": task.user_prompt},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "gca_semantic_report",
                        "strict": True,
                        "schema": task.output_schema,
                    },
                },
            },
        }

    def _health_request(self) -> dict[str, Any]:
        return {
            "url": f"{self.base_url}/models",
            "headers": {"Authorization": f"Bearer {self._api_key}"},
        }

    def _extract_text(self, payload: dict[str, Any]) -> str:
        return str(payload["choices"][0]["message"]["content"])
