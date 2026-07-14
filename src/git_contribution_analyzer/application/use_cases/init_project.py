from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from git_contribution_analyzer import __version__
from git_contribution_analyzer.adapters.git.repository_discovery import (
    detect_current_branch,
    discover_repository,
)
from git_contribution_analyzer.adapters.storage.sqlite.database import (
    initialize_database,
    upsert_repository,
)
from git_contribution_analyzer.adapters.workspace.config import write_default_config
from git_contribution_analyzer.adapters.workspace.git_exclude import ensure_workspace_excluded
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.locks import workspace_lock
from git_contribution_analyzer.application.use_cases.index_repository import index_repository


def init_project(path: Path) -> WorkspaceLayout:
    repository = discover_repository(path)
    layout = WorkspaceLayout.for_repository(repository.root)
    layout.create_directories()

    with workspace_lock(layout.locks / "workspace.lock"):
        default_branch = detect_current_branch(repository)
        write_default_config(layout.config, default_branch)
        if not layout.identities.exists():
            layout.identities.write_text("schemaVersion: '1.0'\nidentities: []\n", encoding="utf-8")
        initialize_database(layout.database)
        repository_id = upsert_repository(layout.database, repository, default_branch)
        now = datetime.now(UTC).isoformat()
        created_at = now
        if layout.metadata.exists():
            try:
                existing = json.loads(layout.metadata.read_text(encoding="utf-8"))
                created_at = str(existing.get("createdAt", now))
            except (OSError, ValueError, TypeError):
                created_at = now
        metadata = {
            "schemaVersion": "1.0",
            "toolVersion": __version__,
            "repository": str(repository.root),
            "repositoryId": repository_id,
            "gitDir": str(repository.git_dir),
            "createdAt": created_at,
            "updatedAt": now,
        }
        layout.metadata.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        ensure_workspace_excluded(repository.root)
    index_repository(repository.root, full_rebuild=False)
    return layout
