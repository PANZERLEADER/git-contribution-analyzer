from __future__ import annotations

import json
from typing import Any

from git_contribution_analyzer.application.ports.llm import (
    LlmCompletion,
    LlmTask,
    ProviderCapabilities,
)
from git_contribution_analyzer.domain.errors import LlmOutputError


class MockLlmProvider:
    provider_id = "mock"
    model = "deterministic"

    def __init__(
        self,
        *,
        response: dict[str, Any] | None = None,
        raw_response: str | None = None,
    ) -> None:
        self.response = response
        self.raw_response = raw_response

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(structured_output=True, local_execution=True)

    def complete(self, task: LlmTask) -> LlmCompletion:
        evidence_id = task.allowed_evidence_ids[0] if task.allowed_evidence_ids else "EV-000"
        semantic_default = {
            "overallSummary": [
                {
                    "text": "Delivered evidence-backed repository changes.",
                    "evidenceIds": [evidence_id],
                    "confidence": "MEDIUM",
                }
            ],
            "contributionSummaries": [],
            "capabilityExplanations": [],
            "resumeBullets": [],
        }
        if task.task_id == "assessment-explanation":
            default = {
                "overallExplanation": [
                    {
                        "text": "The assessment is supported by deterministic evidence.",
                        "evidenceIds": [evidence_id],
                        "confidence": "MEDIUM",
                    }
                ],
                "itemExplanations": [],
            }
        elif task.task_id == "resume-generation":
            context = json.loads(task.user_prompt)
            allowed_claim = context["allowedClaims"][0]
            default = {
                "projectSummaryCandidates": [],
                "experienceBullets": [allowed_claim],
            }
        else:
            default = semantic_default
        raw = self.raw_response or json.dumps(self.response or default)
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise LlmOutputError() from exc
        if not isinstance(parsed, dict):
            raise LlmOutputError()
        return LlmCompletion(
            provider_id=self.provider_id,
            model=self.model,
            content=parsed,
            attempts=1,
            input_chars=len(task.system_prompt) + len(task.user_prompt),
            output_chars=len(raw),
        )

    def health_check(self) -> bool:
        return True
