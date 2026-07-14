from __future__ import annotations

import hashlib
import json
from time import perf_counter
from typing import Any, Protocol

from git_contribution_analyzer.application.ports.llm import (
    LlmCompletion,
    LlmProvider,
    LlmTask,
    ProviderCapabilities,
)
from git_contribution_analyzer.domain.errors import LlmProviderError


class LlmAuditStore(Protocol):
    def get_cached(self, request_hash: str) -> dict[str, Any] | None: ...

    def put_cached(
        self,
        *,
        request_hash: str,
        provider_id: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        response: dict[str, Any],
    ) -> None: ...

    def record_invocation(
        self,
        *,
        run_id: str | None,
        request_hash: str,
        provider_id: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        attempts: int,
        latency_ms: int,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        cache_hit: bool = False,
    ) -> None: ...


def llm_request_hash(task: LlmTask, provider_id: str, model: str) -> str:
    payload = {
        "providerId": provider_id,
        "model": model,
        "promptVersion": task.prompt_version,
        "schemaVersion": task.schema_version,
        "systemPrompt": task.system_prompt,
        "userPrompt": task.user_prompt,
        "outputSchema": task.output_schema,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CachedAuditedProvider:
    def __init__(
        self,
        delegate: LlmProvider,
        store: LlmAuditStore,
        *,
        run_id: str | None = None,
    ) -> None:
        self._delegate = delegate
        self._store = store
        self._run_id = run_id
        self.provider_id = delegate.provider_id
        self.model = delegate.model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._delegate.capabilities

    def health_check(self) -> bool:
        return self._delegate.health_check()

    def complete(self, task: LlmTask) -> LlmCompletion:
        request_hash = llm_request_hash(task, self.provider_id, self.model)
        cached = self._store.get_cached(request_hash)
        if cached is not None:
            self._record(
                task,
                request_hash=request_hash,
                attempts=0,
                latency_ms=0,
                status="COMPLETED",
                cache_hit=True,
            )
            return LlmCompletion(
                provider_id=self.provider_id,
                model=self.model,
                content=cached,
                attempts=0,
                input_chars=0,
                output_chars=len(json.dumps(cached, ensure_ascii=False)),
            )

        started = perf_counter()
        try:
            completion = self._delegate.complete(task)
        except LlmProviderError as exc:
            self._record(
                task,
                request_hash=request_hash,
                attempts=exc.attempts,
                latency_ms=_elapsed_ms(started),
                status="FAILED",
                error_code=exc.code,
                error_message=str(exc),
            )
            raise
        self._store.put_cached(
            request_hash=request_hash,
            provider_id=self.provider_id,
            model=self.model,
            prompt_version=task.prompt_version,
            schema_version=task.schema_version,
            response=completion.content,
        )
        self._record(
            task,
            request_hash=request_hash,
            attempts=completion.attempts,
            latency_ms=_elapsed_ms(started),
            status="COMPLETED",
        )
        return completion

    def _record(self, task: LlmTask, **values: Any) -> None:
        self._store.record_invocation(
            run_id=self._run_id,
            provider_id=self.provider_id,
            model=self.model,
            prompt_version=task.prompt_version,
            schema_version=task.schema_version,
            **values,
        )


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
