from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

import httpx

from git_contribution_analyzer.application.ports.llm import (
    LlmCompletion,
    LlmTask,
    ProviderCapabilities,
)
from git_contribution_analyzer.domain.errors import (
    LlmAuthenticationError,
    LlmOutputError,
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)


class JsonHttpProvider(ABC):
    provider_id: str

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.transport = transport

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(structured_output=True, local_execution=False)

    def complete(self, task: LlmTask) -> LlmCompletion:
        attempts = 0
        request_task = task
        repair_attempted = False
        while attempts <= self.max_retries:
            attempts += 1
            try:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                ) as client:
                    response = client.post(**self._request(request_task))
            except httpx.TimeoutException as exc:
                if attempts <= self.max_retries:
                    continue
                timeout_error = LlmTimeoutError()
                timeout_error.attempts = attempts
                raise timeout_error from exc
            error = self._response_error(response)
            if error is not None:
                if error.retriable and attempts <= self.max_retries:
                    continue
                error.attempts = attempts
                raise error
            try:
                raw_text = self._extract_text(response.json())
                content = _parse_json(raw_text)
            except (ValueError, KeyError, TypeError) as exc:
                if not repair_attempted and attempts <= self.max_retries:
                    repair_attempted = True
                    request_task = replace(
                        task,
                        user_prompt=(
                            f"{task.user_prompt}\n\n"
                            "Repair the previous invalid response. Return only a JSON object "
                            "that conforms exactly to the supplied output schema."
                        ),
                    )
                    continue
                output_error = LlmOutputError()
                output_error.attempts = attempts
                raise output_error from exc
            return LlmCompletion(
                provider_id=self.provider_id,
                model=self.model,
                content=content,
                attempts=attempts,
                input_chars=len(task.system_prompt) + len(task.user_prompt),
                output_chars=len(raw_text),
            )
        raise LlmProviderError("LLM provider retry loop exhausted")

    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.get(**self._health_request())
            return response.status_code < 400
        except httpx.HTTPError:
            return False

    def _response_error(self, response: httpx.Response) -> LlmProviderError | None:
        if response.status_code in (401, 403):
            return LlmAuthenticationError()
        if response.status_code == 429:
            return LlmRateLimitError()
        if response.status_code >= 500:
            return LlmProviderError(
                f"LLM provider server error: HTTP {response.status_code}",
                code="SERVER_ERROR",
                retriable=True,
            )
        if response.status_code >= 400:
            return LlmProviderError(
                f"LLM provider request failed: HTTP {response.status_code}",
                code="REQUEST_ERROR",
            )
        return None

    @abstractmethod
    def _request(self, task: LlmTask) -> dict[str, Any]: ...

    @abstractmethod
    def _health_request(self) -> dict[str, Any]: ...

    @abstractmethod
    def _extract_text(self, payload: dict[str, Any]) -> str: ...


def _parse_json(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Structured output must be a JSON object")
    return parsed
