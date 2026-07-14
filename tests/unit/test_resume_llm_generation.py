from __future__ import annotations

from datetime import UTC, datetime

import pytest

from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.application.services.resume_generation import enhance_resume
from git_contribution_analyzer.domain.errors import LlmOutputError
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.assessment import CapabilityAssessment
from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
    Evidence,
)
from git_contribution_analyzer.domain.models.resume import ClaimStrength
from git_contribution_analyzer.domain.models.snapshot import (
    EvidenceSnapshot,
    SnapshotPerson,
    SnapshotSubject,
)


def _snapshot() -> EvidenceSnapshot:
    commit = ContributionCommit(
        hash="abc",
        subject="feat: api",
        authored_at=datetime(2026, 1, 1, tzinfo=UTC),
        commit_type="FEATURE",
        delivery_status="LANDED",
        paths=("api/user.py",),
        modules=("api",),
        insertions=10,
        deletions=1,
        files_changed=1,
        merge=False,
        binary_files=0,
        generated_files=0,
    )
    item = ContributionItem("CI-001", "api", "API", "HIGH", (commit,), ("EV-001",))
    subject = SnapshotSubject(
        SnapshotPerson("p1", "Alice", "alice@example.com", "HUMAN", True),
        (commit,),
        (item,),
        (Evidence("EV-001", "CHANGE", "API", ("abc",), ("api/user.py",), ()),),
        (CapabilityAssessment("API", "HIGH", "API", ("EV-001",)),),
    )
    return EvidenceSnapshot.create(
        repository_id="repo",
        repository_root="C:/private/repo",
        baseline_commit="abc",
        filters=AnalysisFilters(),
        scope_type="PERSON",
        subjects=(subject,),
        identity_warnings=(),
        rule_versions=(("evidence", "rules-v1"),),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_should_reject_llm_claim_above_strength_ceiling() -> None:
    provider = MockLlmProvider(
        response={
            "projectSummaryCandidates": [],
            "experienceBullets": [
                {
                    "text": "Led the API work",
                    "claimStrength": "LED",
                    "contributionItemIds": ["CI-001"],
                    "evidenceIds": ["EV-001"],
                    "verifiedOutcomeIds": [],
                    "confidence": "HIGH",
                    "pending": False,
                }
            ],
        }
    )

    with pytest.raises(LlmOutputError):
        enhance_resume(
            report={
                "experienceBullets": [
                        {
                            "claimStrength": ClaimStrength.IMPLEMENTED.value,
                            "contributionItemIds": ["CI-001"],
                            "evidenceIds": ["EV-001"],
                        }
                ]
            },
            snapshot=_snapshot(),
            provider=provider,
            outcomes=(),
            max_bullets=6,
        )
