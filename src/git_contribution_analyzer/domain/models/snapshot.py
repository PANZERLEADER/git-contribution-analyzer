from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Self

from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.assessment import CapabilityAssessment
from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
    Evidence,
)

SNAPSHOT_SCHEMA_VERSION = "snapshot-v1"


@dataclass(frozen=True, slots=True)
class SnapshotPerson:
    id: str
    name: str
    email: str
    kind: str
    confirmed: bool


@dataclass(frozen=True, slots=True)
class SnapshotSubject:
    person: SnapshotPerson
    commits: tuple[ContributionCommit, ...]
    contribution_items: tuple[ContributionItem, ...]
    evidence: tuple[Evidence, ...]
    capabilities: tuple[CapabilityAssessment, ...]


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    id: str
    schema_version: str
    repository_id: str
    repository_root: str
    baseline_commit: str | None
    filters: AnalysisFilters
    scope_type: str
    subjects: tuple[SnapshotSubject, ...]
    identity_warnings: tuple[str, ...]
    rule_versions: tuple[tuple[str, str], ...]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        repository_id: str,
        repository_root: str,
        baseline_commit: str | None,
        filters: AnalysisFilters,
        scope_type: str,
        subjects: tuple[SnapshotSubject, ...],
        identity_warnings: tuple[str, ...],
        rule_versions: tuple[tuple[str, str], ...],
        created_at: datetime,
    ) -> Self:
        candidate = cls(
            id="",
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            repository_id=repository_id,
            repository_root=repository_root,
            baseline_commit=baseline_commit,
            filters=filters,
            scope_type=scope_type,
            subjects=tuple(sorted(subjects, key=lambda value: value.person.id)),
            identity_warnings=tuple(sorted(identity_warnings)),
            rule_versions=tuple(sorted(rule_versions)),
            created_at=created_at,
        )
        encoded = json.dumps(
            candidate._canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return replace(candidate, id=hashlib.sha256(encoded).hexdigest())

    def as_reference(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schemaVersion": self.schema_version,
            "baselineCommit": self.baseline_commit,
            "filters": self.filters.as_dict(),
        }

    def as_llm_context(self) -> dict[str, Any]:
        return {
            "snapshotId": self.id,
            "schemaVersion": self.schema_version,
            "baselineCommit": self.baseline_commit,
            "filters": self.filters.as_dict(),
            "subjects": [
                {
                    "person": {"id": subject.person.id, "name": subject.person.name},
                    "contributionItems": [
                        {
                            "id": item.id,
                            "title": item.title,
                            "confidence": item.confidence,
                            "evidenceIds": list(item.evidence_ids),
                        }
                        for item in sorted(
                            subject.contribution_items, key=lambda value: value.id
                        )
                    ],
                    "evidence": [
                        {
                            "id": entry.id,
                            "type": entry.evidence_type,
                            "summary": entry.summary,
                            "metrics": dict(entry.metrics),
                        }
                        for entry in sorted(subject.evidence, key=lambda value: value.id)
                    ],
                }
                for subject in self.subjects
            ],
        }

    def _canonical_payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "repositoryId": self.repository_id,
            "repositoryRoot": self.repository_root,
            "baselineCommit": self.baseline_commit,
            "filters": self.filters.as_dict(),
            "scopeType": self.scope_type,
            "subjects": [_serialize_subject(subject) for subject in self.subjects],
            "identityWarnings": list(self.identity_warnings),
            "ruleVersions": dict(self.rule_versions),
        }


def _serialize_subject(subject: SnapshotSubject) -> dict[str, Any]:
    return {
        "person": {
            "id": subject.person.id,
            "name": subject.person.name,
            "email": subject.person.email,
            "kind": subject.person.kind,
            "confirmed": subject.person.confirmed,
        },
        "commits": [
            {
                "hash": commit.hash,
                "subject": commit.subject,
                "authoredAt": commit.authored_at.isoformat(),
                "commitType": commit.commit_type,
                "deliveryStatus": commit.delivery_status,
                "paths": sorted(commit.paths),
                "modules": sorted(commit.modules),
                "insertions": commit.insertions,
                "deletions": commit.deletions,
                "filesChanged": commit.files_changed,
                "merge": commit.merge,
                "binaryFiles": commit.binary_files,
                "generatedFiles": commit.generated_files,
                "patchId": commit.patch_id,
                "revertsHash": commit.reverts_hash,
                "effectiveInsertions": commit.effective_insertions,
                "effectiveDeletions": commit.effective_deletions,
                "effectiveFilesChanged": commit.effective_files_changed,
            }
            for commit in sorted(subject.commits, key=lambda value: (value.authored_at, value.hash))
        ],
        "contributionItems": [
            {
                "id": item.id,
                "groupKey": item.group_key,
                "title": item.title,
                "confidence": item.confidence,
                "commitHashes": sorted(commit.hash for commit in item.commits),
                "evidenceIds": sorted(item.evidence_ids),
            }
            for item in sorted(subject.contribution_items, key=lambda value: value.id)
        ],
        "evidence": [
            {
                "id": entry.id,
                "type": entry.evidence_type,
                "summary": entry.summary,
                "commitHashes": sorted(entry.commit_hashes),
                "paths": sorted(entry.paths),
                "metrics": dict(sorted(entry.metrics)),
            }
            for entry in sorted(subject.evidence, key=lambda value: value.id)
        ],
        "capabilities": [
            {
                "capability": capability.capability,
                "confidence": capability.confidence,
                "rationale": capability.rationale,
                "evidenceIds": sorted(capability.evidence_ids),
                "gaps": sorted(capability.gaps),
            }
            for capability in sorted(subject.capabilities, key=lambda value: value.capability)
        ],
    }
