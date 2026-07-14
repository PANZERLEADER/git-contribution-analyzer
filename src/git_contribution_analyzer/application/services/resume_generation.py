from __future__ import annotations

import json
from collections import Counter
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
from git_contribution_analyzer.domain.models.resume import (
    ClaimStrength,
    OmittedClaim,
    ResumeClaim,
    ResumeLanguage,
    ResumeStyle,
    SkillEvidence,
    VerifiedOutcome,
)
from git_contribution_analyzer.domain.models.snapshot import EvidenceSnapshot, SnapshotSubject
from git_contribution_analyzer.domain.models.work_assessment import CompletionBucket
from git_contribution_analyzer.domain.services.resume_claim_rules import (
    claim_strength_ceiling,
    validate_resume_claim,
)
from git_contribution_analyzer.domain.services.workload_rules import classify_completion


class _ResumeClaimOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    text: str = Field(min_length=1)
    claim_strength: ClaimStrength = Field(alias="claimStrength")
    contribution_item_ids: list[str] = Field(alias="contributionItemIds", min_length=1)
    evidence_ids: list[str] = Field(alias="evidenceIds", min_length=1)
    verified_outcome_ids: list[str] = Field(alias="verifiedOutcomeIds")
    confidence: str
    pending: bool = False


class ResumeLlmOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project_summary_candidates: list[_ResumeClaimOutput] = Field(
        alias="projectSummaryCandidates"
    )
    experience_bullets: list[_ResumeClaimOutput] = Field(alias="experienceBullets")


@dataclass(frozen=True, slots=True)
class ResumeEnhancementResult:
    content: dict[str, Any]
    completion: LlmCompletion
    task: LlmTask


def enhance_resume(
    *,
    report: dict[str, Any],
    snapshot: EvidenceSnapshot,
    provider: LlmProvider,
    outcomes: tuple[VerifiedOutcome, ...],
    max_bullets: int,
) -> ResumeEnhancementResult:
    task = build_resume_task(report, snapshot, outcomes, max_bullets)
    completion = provider.complete(task)
    try:
        output = ResumeLlmOutput.model_validate(completion.content)
    except ValidationError as exc:
        raise LlmOutputError("LLM output does not match resume-v1 schema") from exc
    allowed_items = {
        item_id
        for claim in report["experienceBullets"]
        for item_id in claim["contributionItemIds"]
    }
    allowed_evidence = set(task.allowed_evidence_ids)
    strength_ceilings = {
        item_id: ClaimStrength(claim["claimStrength"])
        for claim in report["experienceBullets"]
        for item_id in claim["contributionItemIds"]
    }
    claims = [*output.project_summary_candidates, *output.experience_bullets]
    for value in claims:
        validate_resume_claim(
            _to_domain_claim(value),
            allowed_item_ids=allowed_items,
            allowed_evidence_ids=allowed_evidence,
            strength_ceilings=strength_ceilings,
            outcomes=outcomes,
        )
    content = output.model_dump(by_alias=True, mode="json")
    content["experienceBullets"] = content["experienceBullets"][:max_bullets]
    return ResumeEnhancementResult(content=content, completion=completion, task=task)


def build_resume_task(
    report: dict[str, Any],
    snapshot: EvidenceSnapshot,
    outcomes: tuple[VerifiedOutcome, ...],
    max_bullets: int,
) -> LlmTask:
    allowed_evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for claim in report["experienceBullets"]
                for evidence_id in claim["evidenceIds"]
            }
        )
    )
    context = {
        "snapshotId": snapshot.id,
        "person": report.get(
            "person",
            {
                "id": snapshot.subjects[0].person.id,
                "name": snapshot.subjects[0].person.name,
            },
        ),
        "targetRole": report.get("targetRole", ""),
        "language": report.get("language", "zh-CN"),
        "style": report.get("style", "concise"),
        "maxBullets": max_bullets,
        "allowedClaims": report["experienceBullets"],
        "verifiedOutcomes": [
            {
                "id": outcome.id,
                "text": outcome.text,
                "source": outcome.source,
                "verifiedBy": outcome.verified_by,
                "verifiedAt": outcome.verified_at.isoformat(),
                "kind": outcome.kind,
            }
            for outcome in outcomes
        ],
    }
    root = files("git_contribution_analyzer.prompts.resume.v1")
    prompt = "\n\n".join(
        (
            root.joinpath("system.txt").read_text(encoding="utf-8").strip(),
            root.joinpath(f"style-{context['style']}.txt").read_text(encoding="utf-8").strip(),
        )
    )
    return LlmTask(
        task_id="resume-generation",
        prompt_version="resume-v1",
        schema_version="resume-v1",
        system_prompt=prompt,
        user_prompt=json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        output_schema=ResumeLlmOutput.model_json_schema(by_alias=True),
        allowed_evidence_ids=allowed_evidence_ids,
    )


def _to_domain_claim(value: _ResumeClaimOutput) -> ResumeClaim:
    return ResumeClaim(
        text=value.text,
        claim_strength=value.claim_strength,
        contribution_item_ids=tuple(value.contribution_item_ids),
        evidence_ids=tuple(value.evidence_ids),
        verified_outcome_ids=tuple(value.verified_outcome_ids),
        confidence=value.confidence,
        pending=value.pending,
    )


def build_deterministic_resume(
    subject: SnapshotSubject,
    *,
    language: ResumeLanguage,
    style: ResumeStyle,
    max_bullets: int,
    include_pending: bool,
    outcomes: tuple[VerifiedOutcome, ...],
) -> dict[str, Any]:
    claims: list[ResumeClaim] = []
    omitted: list[OmittedClaim] = []
    ceilings: dict[str, ClaimStrength] = {}
    allowed_evidence_ids = {entry.id for entry in subject.evidence}
    for item in subject.contribution_items:
        completion = classify_completion(item)
        work_types = {commit.commit_type for commit in item.commits}
        ceiling = claim_strength_ceiling(
            confirmed=subject.person.confirmed,
            completion=completion,
            work_types=work_types,
        )
        ceilings[item.id] = ceiling
        if completion not in (CompletionBucket.COMPLETED, CompletionBucket.PENDING):
            omitted.append(
                OmittedClaim(item.title, "NOT_COMPLETED", ("LANDED_OR_RELEASED",))
            )
            continue
        if completion is CompletionBucket.PENDING and not include_pending:
            omitted.append(
                OmittedClaim(item.title, "PENDING_EXCLUDED", ("DELIVERY_EVIDENCE",))
            )
            continue
        claim = ResumeClaim(
            text=_claim_text(item.modules, work_types, ceiling, language, style),
            claim_strength=(
                ClaimStrength.CONTRIBUTED
                if completion is CompletionBucket.PENDING
                else ceiling
            ),
            contribution_item_ids=(item.id,),
            evidence_ids=item.evidence_ids,
            verified_outcome_ids=(),
            confidence="HIGH" if item.confidence == "HIGH" else "MEDIUM",
            pending=completion is CompletionBucket.PENDING,
        )
        validate_resume_claim(
            claim,
            allowed_item_ids={value.id for value in subject.contribution_items},
            allowed_evidence_ids=allowed_evidence_ids,
            strength_ceilings=ceilings,
            outcomes=outcomes,
        )
        claims.append(claim)
    claims = claims[:max_bullets]
    item_ids = {item_id for claim in claims for item_id in claim.contribution_item_ids}
    skills = [
        SkillEvidence(
            skill=capability.capability,
            evidence_ids=capability.evidence_ids,
            contribution_item_ids=tuple(
                item.id
                for item in subject.contribution_items
                if item.id in item_ids
                and set(item.evidence_ids).intersection(capability.evidence_ids)
            ),
        )
        for capability in subject.capabilities
        if set(capability.evidence_ids) <= allowed_evidence_ids
    ]
    modules = Counter(
        module
        for item in subject.contribution_items
        if item.id in item_ids
        for module in item.modules
    )
    domains = sorted(
        {
            item.group_key.split(":", maxsplit=1)[0]
            for item in subject.contribution_items
            if item.id in item_ids
        }
    )
    return {
        "projectSummaryCandidates": [_serialize_claim(claim) for claim in claims[:1]],
        "experienceBullets": [_serialize_claim(claim) for claim in claims],
        "skillEvidence": [_serialize_skill(value) for value in skills],
        "omittedClaims": [_serialize_omitted(value) for value in omitted],
        "technicalSummary": {
            "headline": f"Evidence supports work across {len(modules)} technical modules.",
            "modules": [name for name, _count in modules.most_common()],
        },
        "businessSummary": {
            "headline": f"Evidence supports contributions in {len(domains)} project domains.",
            "domains": domains,
        },
    }


def _claim_text(
    modules: tuple[str, ...],
    work_types: set[str],
    strength: ClaimStrength,
    language: ResumeLanguage,
    style: ResumeStyle,
) -> str:
    module_text = ", ".join(modules) or "the project"
    work_text = "/".join(sorted(value.casefold() for value in work_types)) or "engineering"
    if language is ResumeLanguage.ZH_CN:
        verb = "实现并交付" if strength is ClaimStrength.IMPLEMENTED else "参与"
        suffix = ", 覆盖完整交付链路" if style is ResumeStyle.STAR else ""
        return f"{verb}{module_text}模块的{work_text}工作{suffix}"
    verb = (
        "Implemented and delivered"
        if strength is ClaimStrength.IMPLEMENTED
        else "Contributed to"
    )
    suffix = " with supporting delivery evidence" if style is ResumeStyle.STAR else ""
    return f"{verb} {work_text} work across {module_text}{suffix}."


def _serialize_claim(claim: ResumeClaim) -> dict[str, Any]:
    return {
        "text": claim.text,
        "claimStrength": claim.claim_strength.value,
        "contributionItemIds": list(claim.contribution_item_ids),
        "evidenceIds": list(claim.evidence_ids),
        "verifiedOutcomeIds": list(claim.verified_outcome_ids),
        "confidence": claim.confidence,
        "pending": claim.pending,
    }


def _serialize_skill(value: SkillEvidence) -> dict[str, Any]:
    return {
        "skill": value.skill,
        "evidenceIds": list(value.evidence_ids),
        "contributionItemIds": list(value.contribution_item_ids),
    }


def _serialize_omitted(value: OmittedClaim) -> dict[str, Any]:
    return {
        "candidate": value.candidate,
        "reasonCode": value.reason_code,
        "missingEvidence": list(value.missing_evidence),
    }
