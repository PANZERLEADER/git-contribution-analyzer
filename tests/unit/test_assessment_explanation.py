from __future__ import annotations

from datetime import UTC, datetime

import pytest

from git_contribution_analyzer.adapters.llm.mock import MockLlmProvider
from git_contribution_analyzer.application.services.assessment_explanation import (
    build_assessment_explanation_task,
    explain_assessment,
)
from git_contribution_analyzer.domain.errors import LlmOutputError
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.assessment import CapabilityAssessment
from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
    Evidence,
)
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
        repository_root="C:/repo",
        baseline_commit="abc",
        filters=AnalysisFilters(),
        scope_type="PERSON",
        subjects=(subject,),
        identity_warnings=(),
        rule_versions=(("evidence", "rules-v1"),),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _report() -> dict:
    return {
        "scopeType": "PERSON",
        "workloadSummary": {},
        "difficultyDistribution": {},
        "technicalSummary": {},
        "businessSummary": {},
        "subjects": [
            {
                "itemAssessments": [
                    {
                        "contributionItemId": "CI-001",
                        "completionBucket": "COMPLETED",
                        "size": {},
                        "difficulty": {},
                        "evidenceIds": ["EV-001"],
                    }
                ]
            }
        ],
    }


@pytest.mark.parametrize(
    "response",
    [
        {"invalid": True},
        {
            "overallExplanation": [
                {"text": "Explanation", "evidenceIds": ["EV-999"], "confidence": "HIGH"}
            ],
            "itemExplanations": [],
        },
        {
            "overallExplanation": [
                {"text": "Improved by 35%", "evidenceIds": ["EV-001"], "confidence": "HIGH"}
            ],
            "itemExplanations": [],
        },
        {
            "overallExplanation": [],
            "itemExplanations": [
                {
                    "text": "Explanation",
                    "evidenceIds": ["EV-001"],
                    "confidence": "HIGH",
                    "contributionItemId": "CI-999",
                }
            ],
        },
    ],
)
def test_should_reject_invalid_assessment_explanations(response: dict) -> None:
    with pytest.raises(LlmOutputError):
        explain_assessment(_report(), _snapshot(), MockLlmProvider(response=response))


def test_should_not_send_ranking_values_to_llm_provider() -> None:
    report = _report()
    report["ranking"] = {
        "enabled": True,
        "dimensions": [
            {
                "dimension": "workload",
                "entries": [{"personId": "p1", "rawValue": "10.0000", "rank": 1}],
            }
        ],
    }

    task = build_assessment_explanation_task(report, _snapshot())

    assert "ranking" not in task.user_prompt.casefold()
    assert "rawvalue" not in task.user_prompt.casefold()
    assert '"rank"' not in task.user_prompt.casefold()
