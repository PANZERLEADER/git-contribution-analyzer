from __future__ import annotations

import re

from git_contribution_analyzer.domain.errors import LlmOutputError
from git_contribution_analyzer.domain.models.resume import (
    ClaimStrength,
    ResumeClaim,
    VerifiedOutcome,
)
from git_contribution_analyzer.domain.models.work_assessment import CompletionBucket

RESULT_NUMBER_PATTERN = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*%|[$€£]\s*\d|\b\d+(?:\.\d+)?\s*(?:ms|qps|rps|users?)\b)",
    re.IGNORECASE,
)
STRENGTH_ORDER = {
    ClaimStrength.CONTRIBUTED: 0,
    ClaimStrength.IMPLEMENTED: 1,
    ClaimStrength.LED: 2,
}


def claim_strength_ceiling(
    *,
    confirmed: bool,
    completion: CompletionBucket,
    work_types: set[str],
) -> ClaimStrength:
    if (
        confirmed
        and completion is CompletionBucket.COMPLETED
        and work_types.intersection({"FEATURE", "FIX", "REFACTOR", "PERFORMANCE"})
    ):
        return ClaimStrength.IMPLEMENTED
    return ClaimStrength.CONTRIBUTED


def validate_resume_claim(
    claim: ResumeClaim,
    *,
    allowed_item_ids: set[str],
    allowed_evidence_ids: set[str],
    strength_ceilings: dict[str, ClaimStrength],
    outcomes: tuple[VerifiedOutcome, ...],
) -> None:
    item_ids = set(claim.contribution_item_ids)
    evidence_ids = set(claim.evidence_ids)
    if not item_ids or not evidence_ids:
        raise LlmOutputError("Resume claims require Item and Evidence references")
    if not item_ids <= allowed_item_ids:
        raise LlmOutputError("Resume claim references an unknown Contribution Item")
    if not evidence_ids <= allowed_evidence_ids:
        raise LlmOutputError("Resume claim references an unknown Evidence ID")
    ceiling = min(
        (strength_ceilings[item_id] for item_id in item_ids),
        key=lambda value: STRENGTH_ORDER[value],
    )
    if STRENGTH_ORDER[claim.claim_strength] > STRENGTH_ORDER[ceiling]:
        raise LlmOutputError("Resume claim exceeds its deterministic strength ceiling")
    outcomes_by_id = {outcome.id: outcome for outcome in outcomes}
    outcome_ids = set(claim.verified_outcome_ids)
    if not outcome_ids <= outcomes_by_id.keys():
        raise LlmOutputError("Resume claim references an unknown verified outcome")
    if RESULT_NUMBER_PATTERN.search(claim.text) and not outcome_ids:
        raise LlmOutputError("Resume result numbers require a verified outcome")
    if claim.claim_strength is ClaimStrength.LED and not any(
        outcomes_by_id[outcome_id].kind == "OWNERSHIP" for outcome_id in outcome_ids
    ):
        raise LlmOutputError("LED claims require verified ownership evidence")
