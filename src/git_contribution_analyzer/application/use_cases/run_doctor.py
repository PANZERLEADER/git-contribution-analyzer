from __future__ import annotations

from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import (
    discover_repository,
    git_version,
)
from git_contribution_analyzer.adapters.storage.sqlite.database import check_database
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import can_acquire_lock


def run_doctor(path: Path) -> dict[str, Any]:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
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
            "healthy": check_database(layout.database),
            "detail": str(layout.database),
        },
        {
            "name": "lock",
            "healthy": can_acquire_lock(layout.locks / "workspace.lock"),
            "detail": str(layout.locks / "workspace.lock"),
        },
    ]
    if layout.config.is_file():
        load_config(layout.config)
    return {"healthy": all(bool(item["healthy"]) for item in checks), "checks": checks}
