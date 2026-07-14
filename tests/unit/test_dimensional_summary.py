from __future__ import annotations

from datetime import UTC, datetime

from git_contribution_analyzer.domain.models.assessment import CapabilityAssessment
from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)
from git_contribution_analyzer.domain.services.dimensional_summary import (
    build_dimensional_summaries,
)


def _commit(
    commit_hash: str,
    subject: str,
    commit_type: str,
    modules: tuple[str, ...],
) -> ContributionCommit:
    return ContributionCommit(
        hash=commit_hash,
        subject=subject,
        authored_at=datetime(2026, 1, 1, tzinfo=UTC),
        commit_type=commit_type,
        delivery_status="LANDED",
        paths=tuple(f"{module}/App.java" for module in modules),
        modules=modules,
        insertions=10,
        deletions=2,
        files_changed=len(modules),
        merge=False,
        binary_files=0,
        generated_files=0,
    )


def test_should_build_deterministic_technical_and_business_dimensions() -> None:
    room_commit = _commit(
        "a" * 40,
        "feat(room): add room flow",
        "FEATURE",
        ("simi-api", "simi-service"),
    )
    recharge_commit = _commit(
        "b" * 40,
        "fix(recharge): handle empty order",
        "FIX",
        ("simi-service",),
    )
    items = (
        ContributionItem(
            id="CI-001",
            group_key="scope:room:1",
            title="room: add room flow",
            confidence="MEDIUM",
            commits=(room_commit,),
            evidence_ids=("EV-001",),
        ),
        ContributionItem(
            id="CI-002",
            group_key="scope:recharge:1",
            title="recharge: handle empty order",
            confidence="MEDIUM",
            commits=(recharge_commit,),
            evidence_ids=("EV-002",),
        ),
    )
    capabilities = (
        CapabilityAssessment(
            capability="API_DESIGN",
            confidence="HIGH",
            rationale="API paths changed",
            evidence_ids=("EV-001",),
        ),
    )

    technical, business = build_dimensional_summaries(
        (room_commit, recharge_commit), items, capabilities
    )

    assert technical["dominantModules"][0] == {"name": "simi-service", "commits": 2}
    assert technical["changeProfile"] == [
        {"type": "FEATURE", "commits": 1},
        {"type": "FIX", "commits": 1},
    ]
    assert technical["capabilities"][0]["capability"] == "API_DESIGN"
    assert technical["highlights"][0]["evidenceIds"]
    assert [domain["name"] for domain in business["domains"]] == ["recharge", "room"]
    assert all(domain["landedCommits"] == 1 for domain in business["domains"])
    assert business["highlights"][0]["evidenceIds"]
