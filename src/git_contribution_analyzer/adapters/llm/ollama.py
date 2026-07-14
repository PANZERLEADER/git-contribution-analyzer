from __future__ import annotations

from typing import Any

import httpx

from git_contribution_analyzer.adapters.llm.base import JsonHttpProvider
from git_contribution_analyzer.application.ports.llm import LlmTask, ProviderCapabilities


class OllamaProvider(JsonHttpProvider):
    provider_id = "ollama"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        timeout_seconds: float = 60.0,
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

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(structured_output=True, local_execution=True)

    def _request(self, task: LlmTask) -> dict[str, Any]:
        return {
            "url": f"{self.base_url}/api/chat",
            "json": {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": task.system_prompt},
                    {"role": "user", "content": task.user_prompt},
                ],
                "format": task.output_schema,
            },
        }

    def _health_request(self) -> dict[str, Any]:
        return {"url": f"{self.base_url}/api/tags"}

    def _extract_text(self, payload: dict[str, Any]) -> str:
        return str(payload["message"]["content"])
