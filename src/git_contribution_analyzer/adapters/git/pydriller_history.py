from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydriller import Repository  # type: ignore[import-untyped]

from git_contribution_analyzer.domain.models.git_history import GitFileChange


class PyDrillerChangeReader:
    """Extract file-level changes once per commit batch using PyDriller."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()

    def read_changes(self, commit_hashes: Iterable[str]) -> dict[str, tuple[GitFileChange, ...]]:
        hashes = list(commit_hashes)
        if not hashes:
            return {}
        changes_by_commit: dict[str, tuple[GitFileChange, ...]] = {}
        for start in range(0, len(hashes), 200):
            batch = hashes[start : start + 200]
            repository = Repository(
                str(self.repository_root),
                only_commits=batch,
                include_deleted_files=True,
                num_workers=1,
            )
            for commit in repository.traverse_commits():
                changes_by_commit[commit.hash] = tuple(
                    GitFileChange(
                        old_path=_normalize_path(modified.old_path),
                        new_path=_normalize_path(modified.new_path),
                        change_type=modified.change_type.name,
                        is_binary=_is_binary(modified),
                        insertions=modified.added_lines,
                        deletions=modified.deleted_lines,
                    )
                    for modified in commit.modified_files
                )
        return changes_by_commit


def _normalize_path(path: str | None) -> str | None:
    return path.replace("\\", "/") if path is not None else None


def _is_binary(modified: Any) -> bool:
    diff = getattr(modified, "_c_diff", None)
    if diff is not None and 0o160000 in {
        getattr(diff, "a_mode", None),
        getattr(diff, "b_mode", None),
    }:
        return True
    return isinstance(modified.content, bytes) or isinstance(modified.content_before, bytes)
