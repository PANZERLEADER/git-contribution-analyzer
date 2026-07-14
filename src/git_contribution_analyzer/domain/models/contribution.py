from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ContributionCommit:
    hash: str
    subject: str
    authored_at: datetime
    commit_type: str
    delivery_status: str
    paths: tuple[str, ...]
    modules: tuple[str, ...]
    insertions: int
    deletions: int
    files_changed: int
    merge: bool
    binary_files: int
    generated_files: int
    patch_id: str | None = None
    reverts_hash: str | None = None
    effective_insertions: int | None = None
    effective_deletions: int | None = None
    effective_files_changed: int | None = None


@dataclass(frozen=True, slots=True)
class ContributionItem:
    id: str
    group_key: str
    title: str
    confidence: str
    commits: tuple[ContributionCommit, ...]
    evidence_ids: tuple[str, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(sorted({path for commit in self.commits for path in commit.paths}))

    @property
    def modules(self) -> tuple[str, ...]:
        return tuple(sorted({module for commit in self.commits for module in commit.modules}))


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    evidence_type: str
    summary: str
    commit_hashes: tuple[str, ...]
    paths: tuple[str, ...]
    metrics: tuple[tuple[str, int], ...]
