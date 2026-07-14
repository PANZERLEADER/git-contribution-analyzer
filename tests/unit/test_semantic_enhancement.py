from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import validate

from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.application.services.semantic_enhancement import enhance_report
from git_contribution_analyzer.domain.errors import LlmOutputError


def _report() -> dict[str, Any]:
    return {
        "person": {
            "id": "person-1",
            "name": "Alice",
            "email": "alice@example.com",
            "kind": "HUMAN",
            "confirmed": True,
        },
        "summary": {"commits": 2, "insertions": 20, "deletions": 5},
        "commitTypes": {"FEATURE": 1, "TEST": 1},
        "deliveryStatuses": {"LANDED": 2},
        "modules": [{"name": "api", "commits": 2}],
        "contributionItems": [
            {
                "id": "CI-001",
                "title": "PROJ-1: add API",
                "confidence": "HIGH",
                "commitTypes": {"FEATURE": 1, "TEST": 1},
                "deliveryStatuses": {"LANDED": 2},
                "modules": ["api", "tests"],
                "paths": ["api/app.py", "tests/test_app.py"],
                "evidenceIds": ["EV-001"],
            }
        ],
        "capabilities": [
            {
                "capability": "API_DESIGN",
                "confidence": "HIGH",
                "rationale": "API paths changed",
                "evidenceIds": ["EV-001"],
                "gaps": [],
            }
        ],
        "evidence": [
            {
                "id": "EV-001",
                "type": "CONTRIBUTION_ITEM",
                "summary": "2 landed commits",
                "metrics": {"commits": 2},
            }
        ],
    }


def _response(evidence_id: str = "EV-001", text: str = "Contributed an API change.") -> dict:
    return {  # type: ignore[type-arg]
        "overallSummary": [
            {"text": text, "evidenceIds": [evidence_id], "confidence": "HIGH"}
        ],
        "contributionSummaries": [
            {
                "contributionItemId": "CI-001",
                "text": "Implemented and tested the API change.",
                "evidenceIds": [evidence_id],
                "confidence": "HIGH",
            }
        ],
        "capabilityExplanations": [
            {
                "capability": "API_DESIGN",
                "text": "API evidence is present.",
                "evidenceIds": [evidence_id],
                "confidence": "HIGH",
            }
        ],
        "resumeBullets": [
            {
                "text": "Contributed an evidence-backed API change.",
                "evidenceIds": [evidence_id],
                "confidence": "HIGH",
            }
        ],
    }


def test_should_validate_semantic_output_and_remove_personal_email_from_prompt() -> None:
    provider = MockLlmProvider(response=_response())

    result = enhance_report(_report(), provider)

    assert result.semantic["resumeBullets"][0]["evidenceIds"] == ["EV-001"]
    assert result.completion.provider_id == "mock"
    assert "alice@example.com" not in result.task.user_prompt
    assert "api/app.py" in result.task.user_prompt

    schema_path = Path(__file__).parents[2] / "schemas" / "llm" / "semantic-v1.json"
    validate(result.semantic, json.loads(schema_path.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "response",
    [
        _response("EV-999"),
        _response(text="Improved conversion by 42%."),
        {"overallSummary": [], "resumeBullets": []},
    ],
    ids=("unknown-evidence", "unsupported-percentage", "invalid-schema"),
)
def test_should_reject_unsupported_or_invalid_semantic_claims(response: dict) -> None:  # type: ignore[type-arg]
    provider = MockLlmProvider(response=response)

    with pytest.raises(LlmOutputError):
        enhance_report(_report(), provider)
