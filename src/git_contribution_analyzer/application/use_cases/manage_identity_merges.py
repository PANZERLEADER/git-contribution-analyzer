from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.database import initialize_database
from git_contribution_analyzer.adapters.storage.sqlite.identity_merge import (
    SqliteIdentityMergeStore,
)
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock


def preview_identity_merge(
    path: Path, sources: tuple[str, ...], target: str
) -> dict[str, Any]:
    store, _layout = _store(path)
    return store.preview(sources, target)


def merge_identities(
    path: Path, sources: tuple[str, ...], target: str
) -> dict[str, Any]:
    store, layout = _store(path)
    with workspace_lock(layout.locks / "workspace.lock"):
        return store.merge(sources, target)


def list_identity_merges(path: Path, status: str) -> dict[str, Any]:
    store, _layout = _store(path)
    return {"merges": store.list_events(status)}


def unmerge_identities(path: Path, merge_id: str) -> dict[str, Any]:
    store, layout = _store(path)
    with workspace_lock(layout.locks / "workspace.lock"):
        return store.unmerge(merge_id)


def _store(path: Path) -> tuple[SqliteIdentityMergeStore, WorkspaceLayout]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    initialize_database(layout.database)
    return (
        SqliteIdentityMergeStore(layout.database, str(repository.root)),
        layout,
    )
