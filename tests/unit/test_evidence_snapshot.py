from __future__ import annotations

from datetime import UTC, datetime

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


def _subject() -> SnapshotSubject:
    commit = ContributionCommit(
        hash="abc123",
        subject="feat(api): add users",
        authored_at=datetime(2026, 1, 1, tzinfo=UTC),
        commit_type="FEATURE",
        delivery_status="LANDED",
        paths=("api/users.py",),
        modules=("api",),
        insertions=10,
        deletions=2,
        files_changed=1,
        merge=False,
        binary_files=0,
        generated_files=0,
    )
    item = ContributionItem(
        id="CI-001",
        group_key="users",
        title="Add users",
        confidence="HIGH",
        commits=(commit,),
        evidence_ids=("EV-001",),
    )
    evidence = Evidence(
        id="EV-001",
        evidence_type="CHANGE",
        summary="User API change",
        commit_hashes=(commit.hash,),
        paths=commit.paths,
        metrics=(("files", 1),),
    )
    return SnapshotSubject(
        person=SnapshotPerson(
            id="person-1",
            name="Alice",
            email="alice@example.com",
            kind="HUMAN",
            confirmed=True,
        ),
        commits=(commit,),
        contribution_items=(item,),
        evidence=(evidence,),
        capabilities=(
            CapabilityAssessment(
                capability="API",
                confidence="HIGH",
                rationale="API path evidence",
                evidence_ids=("EV-001",),
            ),
        ),
    )


def test_should_generate_same_snapshot_id_when_input_order_or_time_changes() -> None:
    subject = _subject()
    first = EvidenceSnapshot.create(
        repository_id="repo-1",
        repository_root="C:/repo",
        baseline_commit="abc123",
        filters=AnalysisFilters(branch="main"),
        scope_type="PERSON",
        subjects=(subject,),
        identity_warnings=("warning-b", "warning-a"),
        rule_versions=(("evidence", "rules-v1"),),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = EvidenceSnapshot.create(
        repository_id="repo-1",
        repository_root="C:/repo",
        baseline_commit="abc123",
        filters=AnalysisFilters(branch="main"),
        scope_type="PERSON",
        subjects=(subject,),
        identity_warnings=("warning-a", "warning-b"),
        rule_versions=(("evidence", "rules-v1"),),
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )

    assert first.id == second.id
    assert len(first.id) == 64


def test_should_change_snapshot_id_when_filter_changes() -> None:
    common = dict(
        repository_id="repo-1",
        repository_root="C:/repo",
        baseline_commit="abc123",
        scope_type="PERSON",
        subjects=(_subject(),),
        identity_warnings=(),
        rule_versions=(("evidence", "rules-v1"),),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    main = EvidenceSnapshot.create(filters=AnalysisFilters(branch="main"), **common)
    release = EvidenceSnapshot.create(filters=AnalysisFilters(release="v1.0.0"), **common)

    assert main.id != release.id


def test_should_not_include_email_or_source_paths_in_llm_context() -> None:
    snapshot = EvidenceSnapshot.create(
        repository_id="repo-1",
        repository_root="C:/private/repo",
        baseline_commit="abc123",
        filters=AnalysisFilters(),
        scope_type="PERSON",
        subjects=(_subject(),),
        identity_warnings=(),
        rule_versions=(("evidence", "rules-v1"),),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    context = snapshot.as_llm_context()
    rendered = str(context)

    assert "alice@example.com" not in rendered
    assert "C:/private/repo" not in rendered
    assert context["subjects"][0]["person"] == {"id": "person-1", "name": "Alice"}
