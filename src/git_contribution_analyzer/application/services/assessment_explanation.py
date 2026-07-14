from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from git_contribution_analyzer.application.ports.llm import (
    LlmCompletion,
    LlmProvider,
    LlmTask,
)
from git_contribution_analyzer.domain.errors import LlmOutputError
from git_contribution_analyzer.domain.models.snapshot import EvidenceSnapshot

PERCENTAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*%")


class _ExplanationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(alias="evidenceIds", min_length=1)
    confidence: str


class _ItemExplanation(_ExplanationClaim):
    contribution_item_id: str = Field(alias="contributionItemId")


class AssessmentExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    overall_explanation: list[_ExplanationClaim] = Field(alias="overallExplanation")
    item_explanations: list[_ItemExplanation] = Field(alias="itemExplanations")


@dataclass(frozen=True, slots=True)
class AssessmentExplanationResult:
    explanation: dict[str, Any]
    completion: LlmCompletion
    task: LlmTask


def explain_assessment(
    report: dict[str, Any],
    snapshot: EvidenceSnapshot,
    provider: LlmProvider,
) -> AssessmentExplanationResult:
    task = build_assessment_explanation_task(report, snapshot)
    completion = provider.complete(task)
    try:
        explanation = AssessmentExplanation.model_validate(completion.content)
    except ValidationError as exc:
        raise LlmOutputError(
            "LLM output does not match assessment-explanation-v1 schema"
        ) from exc
    allowed_evidence = set(task.allowed_evidence_ids)
    allowed_items = {
        item["contributionItemId"]
        for subject in report["subjects"]
        for item in subject["itemAssessments"]
    }
    claims = [*explanation.overall_explanation, *explanation.item_explanations]
    if any(not set(claim.evidence_ids) <= allowed_evidence for claim in claims):
        raise LlmOutputError("Assessment explanation references unknown Evidence IDs")
    if any(PERCENTAGE_PATTERN.search(claim.text) for claim in claims):
        raise LlmOutputError("Assessment explanation contains an unsupported percentage")
    if any(
        claim.contribution_item_id not in allowed_items
        for claim in explanation.item_explanations
    ):
        raise LlmOutputError("Assessment explanation references an unknown item")
    return AssessmentExplanationResult(
        explanation=explanation.model_dump(by_alias=True, mode="json"),
        completion=completion,
        task=task,
    )


def build_assessment_explanation_task(
    report: dict[str, Any], snapshot: EvidenceSnapshot
) -> LlmTask:
    allowed_evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for subject in report["subjects"]
                for item in subject["itemAssessments"]
                for evidence_id in item["evidenceIds"]
            }
        )
    )
    context = {
        "snapshotId": snapshot.id,
        "scopeType": report["scopeType"],
        "workloadSummary": report["workloadSummary"],
        "difficultyDistribution": report["difficultyDistribution"],
        "technicalSummary": report["technicalSummary"],
        "businessSummary": report["businessSummary"],
        "items": [
            {
                "contributionItemId": item["contributionItemId"],
                "completionBucket": item["completionBucket"],
                "size": item["size"],
                "difficulty": item["difficulty"],
                "evidenceIds": item["evidenceIds"],
            }
            for subject in report["subjects"]
            for item in subject["itemAssessments"]
        ],
    }
    prompt = files("git_contribution_analyzer.prompts.assessment.v1").joinpath(
        "explanation.txt"
    ).read_text(encoding="utf-8")
    return LlmTask(
        task_id="assessment-explanation",
        prompt_version="assessment-explanation-v1",
        schema_version="assessment-explanation-v1",
        system_prompt=prompt,
        user_prompt=json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        output_schema=AssessmentExplanation.model_json_schema(by_alias=True),
        allowed_evidence_ids=allowed_evidence_ids,
    )
