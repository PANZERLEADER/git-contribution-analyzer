from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from pydantic import ValidationError

from git_contribution_analyzer.application.ports.llm import (
    LlmCompletion,
    LlmProvider,
    LlmTask,
)
from git_contribution_analyzer.domain.errors import LlmOutputError
from git_contribution_analyzer.domain.models.semantic import SemanticEnhancement

PERCENTAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*%")
PROMPT_NAMES = (
    "overall_summary.txt",
    "contribution_summary.txt",
    "capability_explanation.txt",
    "resume_bullet.txt",
)


@dataclass(frozen=True, slots=True)
class SemanticEnhancementResult:
    semantic: dict[str, Any]
    completion: LlmCompletion
    task: LlmTask


def enhance_report(
    report: dict[str, Any],
    provider: LlmProvider,
) -> SemanticEnhancementResult:
    task = build_semantic_task(report)
    completion = provider.complete(task)
    try:
        semantic = SemanticEnhancement.model_validate(completion.content)
    except ValidationError as exc:
        raise LlmOutputError("LLM output does not match semantic-v1 schema") from exc
    _validate_claims(report, semantic, set(task.allowed_evidence_ids))
    return SemanticEnhancementResult(
        semantic=semantic.model_dump(by_alias=True, mode="json"),
        completion=completion,
        task=task,
    )


def build_semantic_task(report: dict[str, Any]) -> LlmTask:
    selected_items = report["contributionItems"][:80]
    requested_evidence = {
        evidence_id
        for item in selected_items
        for evidence_id in item["evidenceIds"]
    }
    requested_evidence.update(
        evidence_id
        for capability in report["capabilities"]
        for evidence_id in capability["evidenceIds"]
    )
    selected_evidence = [
        entry for entry in report["evidence"] if entry["id"] in requested_evidence
    ][:200]
    allowed_evidence_ids = tuple(entry["id"] for entry in selected_evidence)
    allowed_set = set(allowed_evidence_ids)
    context = {
        "summary": report["summary"],
        "commitTypes": report["commitTypes"],
        "deliveryStatuses": report["deliveryStatuses"],
        "modules": report["modules"],
        "contributionItems": [
            {
                "id": item["id"],
                "title": item["title"],
                "confidence": item["confidence"],
                "commitTypes": item["commitTypes"],
                "deliveryStatuses": item["deliveryStatuses"],
                "modules": item["modules"],
                "paths": item["paths"][:20],
                "evidenceIds": [
                    value for value in item["evidenceIds"] if value in allowed_set
                ],
            }
            for item in selected_items
        ],
        "capabilities": [
            {
                "capability": capability["capability"],
                "confidence": capability["confidence"],
                "rationale": capability["rationale"],
                "evidenceIds": [
                    value for value in capability["evidenceIds"] if value in allowed_set
                ],
                "gaps": capability["gaps"],
            }
            for capability in report["capabilities"]
        ],
        "evidence": [
            {
                "id": entry["id"],
                "type": entry["type"],
                "summary": entry["summary"],
                "metrics": entry["metrics"],
            }
            for entry in selected_evidence
        ],
    }
    prompt_root = files("git_contribution_analyzer.prompts.v1")
    instructions = [
        prompt_root.joinpath(name).read_text(encoding="utf-8").strip()
        for name in PROMPT_NAMES
    ]
    system_prompt = (
        "You enhance deterministic Git evidence. Return only JSON matching the supplied schema. "
        "Never invent outcomes, percentages, ownership, or Evidence IDs.\n\n"
        + "\n\n".join(instructions)
    )
    return LlmTask(
        task_id="semantic-report",
        prompt_version="semantic-v1",
        schema_version="semantic-v1",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        output_schema=SemanticEnhancement.model_json_schema(by_alias=True),
        allowed_evidence_ids=allowed_evidence_ids,
    )


def _validate_claims(
    report: dict[str, Any],
    semantic: SemanticEnhancement,
    allowed_evidence_ids: set[str],
) -> None:
    item_ids = {item["id"] for item in report["contributionItems"]}
    capabilities = {entry["capability"] for entry in report["capabilities"]}
    claims = [
        *semantic.overall_summary,
        *semantic.contribution_summaries,
        *semantic.capability_explanations,
        *semantic.resume_bullets,
    ]
    for claim in claims:
        if not set(claim.evidence_ids) <= allowed_evidence_ids:
            raise LlmOutputError("LLM output references unknown Evidence IDs")
        if PERCENTAGE_PATTERN.search(claim.text):
            raise LlmOutputError("LLM output contains an unsupported percentage claim")
    if any(item.contribution_item_id not in item_ids for item in semantic.contribution_summaries):
        raise LlmOutputError("LLM output references an unknown Contribution Item")
    if any(
        explanation.capability not in capabilities
        for explanation in semantic.capability_explanations
    ):
        raise LlmOutputError("LLM output references an unknown capability")
