from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    structured_output: bool
    local_execution: bool
    health_check: bool = True


@dataclass(frozen=True, slots=True)
class LlmTask:
    task_id: str
    prompt_version: str
    schema_version: str
    system_prompt: str
    user_prompt: str
    output_schema: dict[str, Any]
    allowed_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    provider_id: str
    model: str
    content: dict[str, Any]
    attempts: int
    input_chars: int
    output_chars: int


class LlmProvider(Protocol):
    provider_id: str
    model: str

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def complete(self, task: LlmTask) -> LlmCompletion: ...

    def health_check(self) -> bool: ...
