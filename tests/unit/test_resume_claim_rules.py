from __future__ import annotations

from datetime import date

import pytest

from git_contribution_analyzer.domain.errors import LlmOutputError
from git_contribution_analyzer.domain.models.resume import (
    ClaimStrength,
    ResumeClaim,
    VerifiedOutcome,
)
from git_contribution_analyzer.domain.services.resume_claim_rules import validate_resume_claim


def _claim(
    text: str = "Implemented an evidence-backed API change",
    *,
    strength: ClaimStrength = ClaimStrength.IMPLEMENTED,
    outcome_ids: tuple[str, ...] = (),
) -> ResumeClaim:
    return ResumeClaim(
        text=text,
        claim_strength=strength,
        contribution_item_ids=("CI-001",),
        evidence_ids=("EV-001",),
        verified_outcome_ids=outcome_ids,
        confidence="HIGH",
        pending=False,
    )


def test_should_require_item_and_evidence_references() -> None:
    claim = ResumeClaim(
        text="Implemented a change",
        claim_strength=ClaimStrength.CONTRIBUTED,
        contribution_item_ids=(),
        evidence_ids=(),
        verified_outcome_ids=(),
        confidence="LOW",
        pending=False,
    )

    with pytest.raises(LlmOutputError):
        validate_resume_claim(
            claim,
            allowed_item_ids={"CI-001"},
            allowed_evidence_ids={"EV-001"},
            strength_ceilings={"CI-001": ClaimStrength.IMPLEMENTED},
            outcomes=(),
        )


def test_should_reject_percentage_without_verified_outcome() -> None:
    with pytest.raises(LlmOutputError):
        validate_resume_claim(
            _claim("Reduced API latency by 35%"),
            allowed_item_ids={"CI-001"},
            allowed_evidence_ids={"EV-001"},
            strength_ceilings={"CI-001": ClaimStrength.IMPLEMENTED},
            outcomes=(),
        )


def test_should_allow_result_number_with_verified_outcome() -> None:
    outcome = VerifiedOutcome(
        id="OUT-001",
        text="API latency reduced by 35%",
        source="benchmark.md",
        verified_by="team-lead",
        verified_at=date(2026, 1, 1),
    )

    validate_resume_claim(
        _claim("Reduced API latency by 35%", outcome_ids=("OUT-001",)),
        allowed_item_ids={"CI-001"},
        allowed_evidence_ids={"EV-001"},
        strength_ceilings={"CI-001": ClaimStrength.IMPLEMENTED},
        outcomes=(outcome,),
    )


def test_should_reject_led_without_verified_ownership() -> None:
    with pytest.raises(LlmOutputError):
        validate_resume_claim(
            _claim(strength=ClaimStrength.LED),
            allowed_item_ids={"CI-001"},
            allowed_evidence_ids={"EV-001"},
            strength_ceilings={"CI-001": ClaimStrength.LED},
            outcomes=(),
        )


@pytest.mark.parametrize(
    ("item_ids", "evidence_ids", "outcome_ids"),
    [
        (("CI-999",), ("EV-001",), ()),
        (("CI-001",), ("EV-999",), ()),
        (("CI-001",), ("EV-001",), ("OUT-999",)),
    ],
)
def test_should_reject_unknown_claim_references(
    item_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    outcome_ids: tuple[str, ...],
) -> None:
    claim = ResumeClaim(
        text="Implemented a change",
        claim_strength=ClaimStrength.IMPLEMENTED,
        contribution_item_ids=item_ids,
        evidence_ids=evidence_ids,
        verified_outcome_ids=outcome_ids,
        confidence="HIGH",
        pending=False,
    )

    with pytest.raises(LlmOutputError):
        validate_resume_claim(
            claim,
            allowed_item_ids={"CI-001"},
            allowed_evidence_ids={"EV-001"},
            strength_ceilings={"CI-001": ClaimStrength.IMPLEMENTED},
            outcomes=(),
        )


def test_should_reject_claim_above_contributed_ceiling() -> None:
    with pytest.raises(LlmOutputError):
        validate_resume_claim(
            _claim(),
            allowed_item_ids={"CI-001"},
            allowed_evidence_ids={"EV-001"},
            strength_ceilings={"CI-001": ClaimStrength.CONTRIBUTED},
            outcomes=(),
        )
