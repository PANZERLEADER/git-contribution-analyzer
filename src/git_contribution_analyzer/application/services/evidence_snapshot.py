from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.models.snapshot import (
    EvidenceSnapshot,
    SnapshotPerson,
    SnapshotSubject,
)
from git_contribution_analyzer.domain.services.capability_rules import assess_capabilities
from git_contribution_analyzer.domain.services.contribution_clustering import (
    cluster_contributions,
)
from git_contribution_analyzer.domain.services.contribution_rules import build_evidence


def build_snapshot_subject(
    person: dict[str, object],
    commits: tuple[ContributionCommit, ...],
) -> SnapshotSubject:
    items = cluster_contributions(tuple(commit for commit in commits if not commit.merge))
    evidence = build_evidence(items)
    capabilities = assess_capabilities(items, evidence)
    return SnapshotSubject(
        person=SnapshotPerson(
            id=str(person["id"]),
            name=str(person["name"]),
            email=str(person["email"]),
            kind=str(person["kind"]),
            confirmed=bool(person["confirmed"]),
        ),
        commits=commits,
        contribution_items=items,
        evidence=evidence,
        capabilities=capabilities,
    )


def build_evidence_snapshot(
    *,
    repository_root: Path,
    baseline_commit: str | None,
    filters: AnalysisFilters,
    scope_type: str,
    subjects: tuple[SnapshotSubject, ...],
    identity_warnings: tuple[str, ...],
    created_at: datetime,
) -> EvidenceSnapshot:
    resolved_root = repository_root.resolve()
    return EvidenceSnapshot.create(
        repository_id=str(uuid5(NAMESPACE_URL, resolved_root.as_uri())),
        repository_root=str(resolved_root),
        baseline_commit=baseline_commit,
        filters=filters,
        scope_type=scope_type,
        subjects=subjects,
        identity_warnings=identity_warnings,
        rule_versions=(("evidence", "rules-v1"),),
        created_at=created_at,
    )
