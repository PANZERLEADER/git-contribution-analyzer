from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.storage.sqlite.database import check_database
from git_contribution_analyzer.adapters.storage.sqlite.git_index import SqliteGitIndexStore
from git_contribution_analyzer.adapters.storage.sqlite.structural_baseline import (
    SqliteStructuralBaselineStore,
)
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout


def get_status(path: Path) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    initialized = layout.root.is_dir()
    metadata: dict[str, Any] = {}
    default_branch: str | None = None
    if initialized and layout.metadata.is_file():
        metadata = json.loads(layout.metadata.read_text(encoding="utf-8"))
    if initialized and layout.config.is_file():
        default_branch = load_config(layout.config).default_branch
    stats = {
        "indexedCommits": 0,
        "identities": 0,
        "unresolvedIdentities": 0,
        "refs": 0,
    }
    database_healthy = check_database(layout.database) if initialized else False
    if database_healthy:
        store = SqliteGitIndexStore(layout.database, str(repository.root))
        stats = store.stats()
    structural = (
        SqliteStructuralBaselineStore(layout.database, str(repository.root)).status()
        if database_healthy
        else {
            "baselineCount": 0,
            "latestBaselineId": None,
            "processedCommits": 0,
            "unhealthyBaselines": 0,
            "orphanBaselines": 0,
        }
    )
    return {
        "repository": str(repository.root),
        "gitDir": str(repository.git_dir),
        "workspace": str(layout.root),
        "workspaceInitialized": initialized,
        "databaseHealthy": database_healthy,
        "defaultBranch": default_branch,
        "toolVersion": metadata.get("toolVersion"),
        "schemaVersion": metadata.get("schemaVersion"),
        "indexedCommit": metadata.get("indexedCommit"),
        **stats,
        "lastSync": metadata.get("lastSync"),
        "indexStatus": metadata.get(
            "indexStatus", "not-indexed" if initialized else "not-initialized"
        ),
        "structural": structural,
    }
