from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from git_contribution_analyzer.adapters.llm.anthropic import AnthropicProvider
from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.adapters.llm.ollama import OllamaProvider
from git_contribution_analyzer.adapters.llm.openai_compatible import (
    OpenAiCompatibleProvider,
)
from git_contribution_analyzer.application.ports.llm import LlmProvider, LlmTask
from git_contribution_analyzer.domain.errors import (
    LlmAuthenticationError,
    LlmOutputError,
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)

VALID_OUTPUT = {
    "overallSummary": [
        {
            "text": "Delivered an evidence-backed API change.",
            "evidenceIds": ["EV-001"],
            "confidence": "HIGH",
        }
    ],
    "contributionSummaries": [],
    "capabilityExplanations": [],
    "resumeBullets": [],
}


def _task() -> LlmTask:
    return LlmTask(
        task_id="semantic-report",
        prompt_version="semantic-v1",
        schema_version="semantic-v1",
        system_prompt="Return JSON only.",
        user_prompt="Summarize evidence EV-001.",
        output_schema={"type": "object"},
        allowed_evidence_ids=("EV-001",),
    )


def _http_provider(provider_id: str) -> tuple[LlmProvider, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        content = json.dumps(VALID_OUTPUT)
        if provider_id == "openai-compatible":
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": content}}]},
            )
        if provider_id == "anthropic":
            return httpx.Response(200, json={"content": [{"type": "text", "text": content}]})
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    transport = httpx.MockTransport(handler)
    if provider_id == "openai-compatible":
        provider: LlmProvider = OpenAiCompatibleProvider(
            model="test-model",
            base_url="https://example.test/v1",
            api_key="secret-key",
            transport=transport,
            max_retries=0,
        )
    elif provider_id == "anthropic":
        provider = AnthropicProvider(
            model="test-model",
            base_url="https://example.test",
            api_key="secret-key",
            transport=transport,
            max_retries=0,
        )
    else:
        provider = OllamaProvider(
            model="test-model",
            base_url="http://example.test",
            transport=transport,
            max_retries=0,
        )
    return provider, requests


@pytest.mark.parametrize(
    "factory",
    [
        lambda: (MockLlmProvider(response=VALID_OUTPUT), []),
        lambda: _http_provider("openai-compatible"),
        lambda: _http_provider("anthropic"),
        lambda: _http_provider("ollama"),
    ],
    ids=("mock", "openai-compatible", "anthropic", "ollama"),
)
def test_should_return_unified_completion_for_all_providers(
    factory: Callable[[], tuple[LlmProvider, list[httpx.Request]]],
) -> None:
    provider, requests = factory()

    completion = provider.complete(_task())

    assert completion.content == VALID_OUTPUT
    assert completion.provider_id == provider.provider_id
    expected_model = "deterministic" if provider.provider_id == "mock" else "test-model"
    assert completion.model == expected_model
    assert completion.attempts == 1
    if requests:
        assert requests[0].method == "POST"
        assert "secret-key" not in str(requests[0].content)


def test_should_reject_non_json_provider_output() -> None:
    provider = MockLlmProvider(raw_response="not-json")

    with pytest.raises(LlmOutputError):
        provider.complete(_task())


def _openai_provider(
    handler: Callable[[httpx.Request], httpx.Response], *, max_retries: int = 2
) -> OpenAiCompatibleProvider:
    return OpenAiCompatibleProvider(
        model="test-model",
        base_url="https://example.test/v1",
        api_key="secret-key",
        transport=httpx.MockTransport(handler),
        max_retries=max_retries,
    )


def test_should_map_timeout_after_retry_budget_is_exhausted() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("slow provider", request=request)

    provider = _openai_provider(handler, max_retries=1)

    with pytest.raises(LlmTimeoutError):
        provider.complete(_task())

    assert attempts == 2


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [(401, LlmAuthenticationError), (403, LlmAuthenticationError)],
)
def test_should_map_non_retriable_http_errors(
    status_code: int, expected_error: type[LlmProviderError]
) -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code)

    provider = _openai_provider(handler)

    with pytest.raises(expected_error):
        provider.complete(_task())

    assert attempts == 1


def test_should_retry_and_map_rate_limit_error() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429)

    provider = _openai_provider(handler, max_retries=1)

    with pytest.raises(LlmRateLimitError):
        provider.complete(_task())

    assert attempts == 2


def test_should_retry_server_error_and_return_successful_completion() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        content = json.dumps(VALID_OUTPUT)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    completion = _openai_provider(handler).complete(_task())

    assert completion.attempts == 2
    assert attempts == 2


def test_should_request_json_repair_once_after_invalid_output() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        content = "not-json" if len(requests) == 1 else json.dumps(VALID_OUTPUT)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    completion = _openai_provider(handler).complete(_task())

    second_payload = json.loads(requests[1].content)
    assert completion.attempts == 2
    assert len(requests) == 2
    assert "repair" in second_payload["messages"][-1]["content"].lower()
