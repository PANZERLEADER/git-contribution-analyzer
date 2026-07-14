from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GitRef:
    name: str
    commit_hash: str
    ref_type: str


@dataclass(frozen=True, slots=True)
class GitIdentity:
    name: str
    email: str
    canonical_name: str
    canonical_email: str
    source: str
    confirmed: bool


@dataclass(frozen=True, slots=True)
class GitFileChange:
    old_path: str | None
    new_path: str | None
    change_type: str
    is_binary: bool
    insertions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class GitCommit:
    hash: str
    parents: tuple[str, ...]
    author: GitIdentity
    committer_name: str
    committer_email: str
    authored_at: datetime
    committed_at: datetime
    tree_hash: str
    subject: str
    body: str
    patch_id: str | None
    changes: tuple[GitFileChange, ...]
    reverts_hash: str | None

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def insertions(self) -> int:
        return sum(change.insertions for change in self.changes)

    @property
    def deletions(self) -> int:
        return sum(change.deletions for change in self.changes)


@dataclass(frozen=True, slots=True)
class CommitDelivery:
    commit_hash: str
    target_ref: str
    status: str
    release_ref: str | None = None
    related_commit_hash: str | None = None
