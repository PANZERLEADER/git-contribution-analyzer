from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.native_git import NativeGitHistory
from git_contribution_analyzer.adapters.git.repository_discovery import (
    discover_repository,
    git_version,
)
from git_contribution_analyzer.adapters.storage.sqlite.database import (
    check_database,
    initialize_database,
)
from git_contribution_analyzer.adapters.storage.sqlite.structural_baseline import (
    SqliteStructuralBaselineStore,
)
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import can_acquire_lock
from git_contribution_analyzer.domain.errors import WorkspaceError


def run_doctor(path: Path) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    if layout.database.is_file():
        initialize_database(layout.database)
    database_healthy = check_database(layout.database)
    checks = [
        {"name": "git", "healthy": bool(git_version()), "detail": git_version()},
        {
            "name": "workspace",
            "healthy": (
                layout.root.is_dir() and layout.config.is_file() and layout.metadata.is_file()
            ),
            "detail": str(layout.root),
        },
        {
            "name": "database",
            "healthy": database_healthy,
            "detail": str(layout.database),
        },
        {
            "name": "lock",
            "healthy": can_acquire_lock(layout.locks / "workspace.lock"),
            "detail": str(layout.locks / "workspace.lock"),
        },
    ]
    if database_healthy:
        structural_store = SqliteStructuralBaselineStore(
            layout.database, str(repository.root)
        )
        structural = structural_store.status()
        history = NativeGitHistory(repository.root)
        stale = int(structural["staleBaselines"])
        for baseline in structural_store.completed_baseline_refs():
            baseline_commit = baseline["baselineCommit"]
            try:
                reachable = baseline_commit is None or history.is_ancestor(
                    baseline_commit, str(baseline["branch"])
                )
            except WorkspaceError:
                reachable = False
            if not reachable:
                stale += 1
        checks.append(
            {
                "name": "structural",
                "healthy": structural["unhealthyBaselines"] == 0 and stale == 0,
                "detail": (
                    f"{structural['baselineCount']} baseline(s), "
                    f"{structural['processedCommits']} processed commit(s), "
                    f"{structural['orphanBaselines']} orphan baseline(s), "
                    f"{stale} stale baseline(s)"
                ),
            }
        )
    if layout.config.is_file():
        load_config(layout.config)
    return {"healthy": all(bool(item["healthy"]) for item in checks), "checks": checks}
